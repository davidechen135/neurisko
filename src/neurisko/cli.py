"""Command-line interface: `neurisko battle` and `neurisko score`."""

from __future__ import annotations

import argparse
import sys

from neurisko.engine.game import BattleResult, Event
from neurisko.games.autobattler import MonsterMash, RulesetError

EXIT_USAGE = 2


def _parse_design(text: str) -> tuple[str, ...]:
    return tuple(p.strip() for p in text.split(",") if p.strip())


def _load_game(args: argparse.Namespace) -> MonsterMash:
    try:
        return MonsterMash.from_file(args.ruleset)
    except RulesetError as err:
        print(f"error: {err}", file=sys.stderr)
        sys.exit(EXIT_USAGE)


def _check(game: MonsterMash, label: str, design: tuple[str, ...]) -> None:
    errors = game.validate(design)
    if errors:
        print(f"error: {label} is invalid:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(EXIT_USAGE)


def _format_event(e: Event) -> str:
    t = f"t{e.tick:>4}"
    match e.kind:
        case "attack":
            return f"{t}  {e.actor:<18} hits   {e.target:<18} {e.amount:>4}"
        case "dodge":
            return f"{t}  {e.actor:<18} dodges {e.target}"
        case "heal":
            return f"{t}  {e.actor:<18} heals  {e.target:<18} {e.amount:>4}"
        case "summon":
            return f"{t}  {e.actor:<18} raises {e.target}"
        case "death":
            return f"{t}  {e.actor:<18} DIES"
        case _:
            state = "ON " if e.kind == "synergy_on" else "OFF"
            return f"{t}  synergy {state} {e.actor}"


def _print_result(r: BattleResult) -> None:
    print()
    banner = "DRAW" if r.winner == "draw" else f"TEAM {r.winner} WINS"
    print(f"== {banner} after {r.ticks} ticks ==")
    print(f"{'unit':<18} {'dealt':>6} {'taken':>6} {'kills':>5} {'heal':>5} {'raise':>5}  alive")
    for s in r.stats:
        alive = "yes" if s.survived else "-"
        print(
            f"{s.label:<18} {s.damage_dealt:>6} {s.damage_taken:>6} {s.kills:>5} "
            f"{s.healing:>5} {s.summons:>5}  {alive}"
        )


def cmd_battle(args: argparse.Namespace) -> int:
    game = _load_game(args)
    a, b = _parse_design(args.a), _parse_design(args.b)
    _check(game, "team A", a)
    _check(game, "team B", b)
    print(f"ruleset {game.ruleset_hash}  seed {args.seed}")
    print(f"A {game.describe(a)}")
    print(f"B {game.describe(b)}")
    result = game.simulate(a, b, args.seed, log=not args.quiet)
    if result.events:
        print()
        for e in result.events:
            print(_format_event(e))
    _print_result(result)
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    game = _load_game(args)
    d = _parse_design(args.design)
    _check(game, "design", d)
    report = game.score(d)
    print(f"ruleset {game.ruleset_hash}  {game.describe(d)}")
    print()
    print(f"{'opponent':<18} {'W':>3} {'D':>3} {'L':>3}  score  design")
    by_name = {o.name: o.design for o in game.gauntlet}
    for m in report.matchups:
        bar = "#" * round(m.score * 10)
        print(
            f"{m.opponent:<18} {m.wins:>3} {m.draws:>3} {m.losses:>3}  {m.score:.2f}  "
            f"{bar:<10} {', '.join(by_name[m.opponent])}"
        )
    print()
    print(f"== SCORE {report.score:.3f} over {report.battles} battles ==")
    return 0


def _print_generation(gen: int, s: dict, ev) -> None:
    calls = [e for e in ev.rec.of_type("llm_call") if e["gen"] == gen]
    llm = f"llm {len(calls)} call {sum(e['latency_s'] for e in calls):.1f}s" if calls else "llm -"
    print(
        f"GEN {gen:02d}  best {s['best_pool']:.3f}  held-out {s['best_held_out_pool']:.3f}  "
        f"hof {len(s['hof'])}/{ev.cfg.hof_cap}  improved {s['improvements']}/{s['applications']}  "
        f"{llm}"
    )
    print(f"  best {s['best_text']}")
    top = sorted(ev.design_heuristics(), key=lambda h: h.worth, reverse=True)[:3]
    for h in top:
        print(f"  {h.id:<5}{h.worth:>4.0f}  {h.name[:32]:<32}  {h.text()[:70]}")
    metas = "  ".join(
        f"{m.id} {m.name} {m.worth:.0f}" + ("!" if m.flags else "") for m in ev.metas.values()
    )
    print(f"  meta  {metas}")
    for a in ev.rec.of_type("audit"):
        if a["gen"] == gen and a["decision"] in ("demoted", "merged"):
            extra = a.get("original") or a.get("tainted_ratio") or a.get("held_out_delta")
            print(f"  AUDIT {a['target']} {a['check']} {a['decision']} ({extra})")
    sys.stdout.flush()


def cmd_evolve(args: argparse.Namespace) -> int:
    from pathlib import Path

    from neurisko.engine.evolve import EvolveConfig
    from neurisko.llm import OpenAICompatClient
    from neurisko.runs.session import RUNS_DIR, new_run_id, replay_run, start_run
    from neurisko.settings import Settings

    if args.replay:
        print(f"replaying {args.replay}")
        ev, problems = replay_run(Path(args.replay), on_generation=_print_generation)
        if problems:
            print("REPLAY MISMATCH:\n  " + "\n  ".join(problems), file=sys.stderr)
            return 1
        print("== replay identical to the recorded run ==")
        return 0

    settings = Settings()
    llm = None
    if not args.no_llm:
        llm = OpenAICompatClient(
            settings.llm_base_url,
            settings.llm_model,
            settings.llm_api_key.get_secret_value(),
            timeout_s=settings.llm_timeout_s,
            seed=args.seed,
        )
    cfg = EvolveConfig(
        generations=args.generations,
        max_generations=settings.max_generations,
        seed=args.seed,
        auditor=not args.no_auditor,
        max_llm_calls_per_generation=settings.max_llm_calls_per_generation,
    )
    run_dir = Path(args.runs_dir or RUNS_DIR) / (args.run_id or new_run_id(args.seed))
    if run_dir.exists():
        print(f"error: {run_dir} already exists", file=sys.stderr)
        return EXIT_USAGE
    print(
        f"NEURISKO  run {run_dir}  seed {args.seed}  "
        f"llm {settings.llm_model if llm else 'off'}  auditor {'on' if cfg.auditor else 'OFF'}"
    )
    try:
        _, result = start_run(
            cfg,
            llm,
            run_dir,
            ruleset=args.ruleset,
            redact=[settings.llm_api_key.get_secret_value()],
            on_generation=_print_generation,
        )
    except RulesetError as err:
        print(f"error: {err}", file=sys.stderr)
        return EXIT_USAGE
    print(
        f"\n== {result.reason.upper()} after {result.generations} generations; "
        f"best {result.best_score:.3f} {list(result.best)} ==\nrecorded in {run_dir}"
    )
    return 130 if result.reason == "interrupted" else 0


def cmd_report(args: argparse.Namespace) -> int:
    from datetime import datetime
    from pathlib import Path

    from neurisko.report import ReportConfig, build_report, write_report
    from neurisko.runs.session import default_seed_rules

    game = _load_game(args)
    out_dir = Path(args.reports_dir) / (args.report_id or f"{datetime.now():%Y%m%d-%H%M%S}")
    if out_dir.exists():
        print(f"error: {out_dir} already exists", file=sys.stderr)
        return EXIT_USAGE
    llm = None
    if args.explain:
        from neurisko.llm import OpenAICompatClient
        from neurisko.settings import Settings

        s = Settings()
        llm = OpenAICompatClient(
            s.llm_base_url, s.llm_model, s.llm_api_key.get_secret_value(), s.llm_timeout_s, seed=0
        )
    cfg = ReportConfig(
        seeds=args.seeds,
        verify_seeds=min(args.verify_seeds, args.seeds),
        generations=args.generations,
        fix_parts=args.fix_parts,
        workers=args.workers,
    )
    print(
        f"NEURISKO BALANCE REPORT  ruleset {game.ruleset_hash}  "
        f"{cfg.seeds} seeds x {cfg.generations} gens"
    )
    report = build_report(
        game,
        default_seed_rules(game),
        cfg,
        llm=llm,
        ruleset_source=args.ruleset,
        progress=lambda m: print(f"  [{m}]", flush=True),
    )
    print()
    for p in report.parts:
        bar = "█" * round(p.evolved * 20)
        flags = "  " + " ".join(p.flags).upper() if p.flags else ""
        print(
            f"  {p.part:<13} {bar:<20} {p.evolved:.2f} ({p.lo:.2f}-{p.hi:.2f})  "
            f"base {p.baseline:.2f}  lift {p.lift:.1f}{flags}"
        )
    print("\n" + report.summary.template)
    if report.summary.llm:
        print(f"\nLLM summary ({report.summary.llm_model}, numbers checked):\n{report.summary.llm}")
    elif report.summary.llm_rejected:
        print(f"\nLLM summary discarded: {report.summary.llm_rejected['reason']}")
    write_report(report, out_dir)
    print(f"\n== report written to {out_dir}/report.md ({report.seconds:.0f}s) ==")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="neurisko", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--ruleset", default=None, help="ruleset TOML (default: packaged v0)")

    p = sub.add_parser("battle", parents=[common], help="simulate one battle")
    p.add_argument("a", help="team A, comma-separated unit ids, front first")
    p.add_argument("b", help="team B, comma-separated unit ids, front first")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--quiet", action="store_true", help="hide the event log")
    p.set_defaults(func=cmd_battle)

    p = sub.add_parser("score", parents=[common], help="score a team against the gauntlet")
    p.add_argument("design", help="comma-separated unit ids, front first")
    p.set_defaults(func=cmd_score)

    p = sub.add_parser("evolve", parents=[common], help="run the Eurisko engine")
    p.add_argument("--generations", type=int, default=20)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--no-llm", action="store_true", help="seed heuristics and code metas only")
    p.add_argument(
        "--no-auditor", action="store_true", help="disable the auditor (shows the H59 pattern)"
    )
    p.add_argument("--run-id", default=None)
    p.add_argument("--runs-dir", default=None, help="parent directory for runs (default: runs)")
    p.add_argument("--replay", default=None, metavar="RUN_DIR", help="re-execute a recorded run")
    p.set_defaults(func=cmd_evolve)

    p = sub.add_parser("report", parents=[common], help="balance report with verified fixes")
    p.add_argument("--seeds", type=int, default=8)
    p.add_argument("--verify-seeds", type=int, default=6)
    p.add_argument("--generations", type=int, default=12)
    p.add_argument("--fix-parts", type=int, default=2)
    p.add_argument("--workers", type=int, default=None, help="processes (default: all cores)")
    p.add_argument("--explain", action="store_true", help="add an LLM summary (number-checked)")
    p.add_argument("--report-id", default=None)
    p.add_argument("--reports-dir", default="reports")
    p.set_defaults(func=cmd_report)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
