"""Build a balance report and write report.json + report.md."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

from neurisko.engine.evolve import EvolveConfig
from neurisko.engine.game import Game
from neurisko.engine.heuristics import RuleSpec
from neurisko.llm import LLMClient
from neurisko.report import explain, summary
from neurisko.report.detect import Thresholds, baseline_shares, make_specs, run_batch, share_table
from neurisko.report.schema import Champion, DominantEntry, Report, Summary
from neurisko.report.verify import needs_follow_up, order, verify_patches

Progress = Callable[[str], None]


@dataclass(frozen=True)
class ReportConfig:
    seeds: int = 8
    verify_seeds: int = 6
    generations: int = 12
    fix_parts: int = 2
    follow_up: bool = True  # try a second change when the first only shifts dominance
    top_k: int = 5
    baseline_n: int = 3000
    thresholds: Thresholds = field(default_factory=Thresholds)
    engine: dict[str, Any] = field(default_factory=dict)  # EvolveConfig overrides
    workers: int | None = None

    def engine_config(self) -> EvolveConfig:
        return replace(EvolveConfig(generations=self.generations), **self.engine)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("workers")
        return d


def build_report(
    game: Game,
    seed_rules: list[RuleSpec],
    cfg: ReportConfig,
    llm: LLMClient | None = None,
    ruleset_source: str | None = None,
    progress: Progress | None = None,
) -> Report:
    say = progress or (lambda _msg: None)
    t0 = time.perf_counter()
    eng = cfg.engine_config()
    th = cfg.thresholds
    seeds = list(range(cfg.seeds))

    say(f"detect: {cfg.seeds} runs x {cfg.generations} generations")
    outcomes = run_batch(
        make_specs(game, seeds, eng, seed_rules, cfg.top_k),
        cfg.workers,
        lambda o, i, n: say(f"detect {i}/{n} (seed {o.seed}, {o.seconds:.0f}s)"),
    )
    baseline = baseline_shares(game, cfg.baseline_n)
    parts = share_table(game, outcomes, baseline, th)
    dominant_rows = [p for p in parts if "dominant" in p.flags][: cfg.fix_parts]
    underused = [p.part for p in parts if "underused" in p.flags]

    held = game.held_out()
    champions = [
        Champion(
            seed=o.seed, design=o.champion, held_out=round(held.score(tuple(o.champion)).score, 4)
        )
        for o in outcomes
    ]

    dominant: list[DominantEntry] = []
    verify_seeds = seeds[: cfg.verify_seeds]
    for row in dominant_rows:
        part = row.part
        say(f"explain {part}")
        dep = explain.dependence(game, part, outcomes)
        ev = explain.evidence(part, outcomes)
        gains, note = explain.matchup_gains(game, part, outcomes)

        def verify(g, patches, before, base=()):
            say(f"verify: {len(patches)} patches x {len(verify_seeds)} seeds")
            res, by_tag = verify_patches(
                g,
                patches,
                before,
                verify_seeds,
                eng,
                seed_rules,
                th,
                cfg.top_k,
                cfg.baseline_n,
                cfg.workers,
                lambda o, i, n: say(f"verify {i}/{n} ({o.tag}, seed {o.seed})"),
                base_patches=base,
            )
            for r in res:
                mark = "effective" if r.effective else "not effective: " + "; ".join(r.failed)
                say(f"{r.change_text()}: {r.target_before:.2f} -> {r.target_after:.2f}, {mark}")
            return res, by_tag

        results, by_tag = verify(game, game.patch_candidates(part), outcomes)
        best = needs_follow_up(results) if cfg.follow_up else None
        if best is not None:
            nxt = best.new_dominant[0]
            say(f"follow-up: {best.patch.text()} made {nxt} dominant; trying fixes for {nxt}")
            step_game, _ = game.with_patch(best.patch)
            step2, _ = verify(
                step_game,
                step_game.patch_candidates(nxt),
                by_tag[best.patch.text()],
                base=[best.patch],
            )
            for r in step2:  # opponents dropped by step 1 are gone in step 2 as well
                r.dropped_opponents = list(
                    dict.fromkeys(best.dropped_opponents + r.dropped_opponents)
                )
            results += step2
        dominant.append(
            DominantEntry(
                part=part,
                dependence=dep,
                evidence=ev,
                matchups=gains,
                matchups_note=note,
                patches=order(results),
            )
        )

    f = summary.facts(parts, dominant, underused, len(outcomes), cfg.generations)
    summ = Summary(template=summary.template_summary(f))
    if llm is not None:
        say("summary: asking the LLM")
        text, rejected = summary.llm_summary(llm, f)
        summ.llm, summ.llm_rejected = text, rejected
        summ.llm_model = llm.model
    return Report(
        game=game.name,
        ruleset_hash=game.ruleset_hash,
        ruleset_source=ruleset_source,
        config=cfg.to_dict(),
        engine_config=eng.to_dict(),
        seeds=seeds,
        seconds=round(time.perf_counter() - t0, 1),
        baseline_n=cfg.baseline_n,
        parts=parts,
        dominant=dominant,
        underused=underused,
        champions=champions,
        summary=summ,
    )


# --- Markdown ------------------------------------------------------------------------------


def _bar(x: float, width: int = 20) -> str:
    n = round(x * width)
    return "█" * n + "·" * (width - n)


def render_markdown(r: Report) -> str:
    c = r.config
    out = [
        "# Neurisko balance report",
        "",
        f"Game `{r.game}`, ruleset `{r.ruleset_hash}`"
        + (f" (`{r.ruleset_source}`)" if r.ruleset_source else "")
        + f". {len(r.seeds)} engine runs x {c['generations']} generations, top {c['top_k']} "
        f"designs per run, baseline {r.baseline_n} random competitive designs. "
        f"Took {r.seconds:.0f} s.",
        "",
        "## Summary",
        "",
        r.summary.template,
        "",
    ]
    if r.summary.llm:
        out += [
            f"**LLM-written summary** ({r.summary.llm_model}, numbers checked against the "
            "measurements):",
            "",
            f"> {r.summary.llm}",
            "",
        ]
    elif r.summary.llm_rejected:
        out += [f"_The LLM summary was discarded: {r.summary.llm_rejected['reason']}._", ""]
    out += [
        "## Unit shares",
        "",
        "| unit | in top designs | range | in random designs | lift | champions | flags |",
        "|---|---|---|---|---|---|---|",
    ]
    for p in r.parts:
        out.append(
            f"| {p.part} | `{_bar(p.evolved)}` {p.evolved:.2f} | {p.lo:.2f}–{p.hi:.2f} | "
            f"{p.baseline:.2f} | {p.lift:.1f} | {p.champion_runs}/{p.runs} | "
            f"{', '.join(p.flags).upper()} |"
        )
    for d in r.dominant:
        out += ["", f"## {d.part}", ""]
        if d.dependence.mean is not None:
            out.append(
                f"**Dependence**: champions lose {d.dependence.mean:.3f} on average when one "
                f"{d.part} is replaced by the best alternative "
                f"({len(d.dependence.per_champion)} champions)."
            )
        if d.evidence:
            out += ["", "**Heuristics that keep adding it** (highest worth across runs):", ""]
            for e in d.evidence:
                rate = e.improvements / e.applications if e.applications else 0
                out.append(
                    f"- `{e.text}` worth {e.worth:.0f}, {e.applications} applications, "
                    f"{rate:.0%} improved, in {e.runs} run(s)"
                )
        if d.matchups:
            out += ["", "**Where it helps most** (held-out opponents):", ""]
            for m in d.matchups:
                out.append(
                    f"- {m.opponent}: {m.with_part:.2f} with vs {m.without_part:.2f} without "
                    f"({m.gain:+.2f})"
                )
        elif d.matchups_note:
            out += ["", f"_Matchup comparison {d.matchups_note}._"]
        out += [
            "",
            f"**Candidate fixes** (each verified on {c['verify_seeds']} seeds; a second change is "
            "tried when the best single change only moves dominance to another unit):",
            "",
            "| change | changed unit's share before → after | most common after | "
            "held-out champion | verdict |",
            "|---|---|---|---|---|",
        ]
        for p in d.patches:
            verdict = "✅ effective" if p.effective else "❌ " + "; ".join(p.failed)
            if p.dropped_opponents:
                verdict += f" (dropped opponents: {', '.join(p.dropped_opponents)})"
            out.append(
                f"| `{p.change_text()}` | {p.patch.target} {p.target_before:.2f} → "
                f"{p.target_after:.2f} | "
                f"{p.top_after} {p.top_after_share:.2f} | {p.champion_held_out:.3f} | {verdict} |"
            )
    if r.underused:
        out += ["", "## Rarely used", "", ", ".join(r.underused)]
    out += ["", "## Champions", ""]
    for ch in r.champions:
        out.append(f"- seed {ch.seed}: `{' > '.join(ch.design)}` (held-out {ch.held_out:.3f})")
    out.append("")
    return "\n".join(out)


def write_report(report: Report, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=False)
    (out_dir / "report.json").write_text(report.model_dump_json(indent=2) + "\n")
    (out_dir / "report.md").write_text(render_markdown(report))
