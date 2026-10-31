"""Start, record and replay evolution runs. Shared by the CLI and scripts."""

from __future__ import annotations

import subprocess
from dataclasses import replace
from datetime import datetime
from importlib import resources
from pathlib import Path

from neurisko.engine.evolve import Evolution, EvolveConfig, RunResult
from neurisko.engine.heuristics import RuleSpec, load_seed_rules
from neurisko.games.autobattler import MonsterMash
from neurisko.llm import LLMClient, ReplayClient
from neurisko.runs.recorder import Recorder, load_events, load_meta

RUNS_DIR = Path("runs")
SEED_RULES = "seed_heuristics.toml"
# Generation-summary keys that legitimately differ between a run and its replay.
TIMING_KEYS = {"t", "elapsed_s"}


def default_seed_rules(game: MonsterMash) -> list[RuleSpec]:
    path = Path(str(resources.files("neurisko.games.autobattler").joinpath("data", SEED_RULES)))
    return load_seed_rules(path, game.feature_names(), game.action_schema())


def new_run_id(seed: int) -> str:
    return f"{datetime.now():%Y%m%d-%H%M%S}-s{seed}"


def _git_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None


def start_run(
    cfg: EvolveConfig,
    llm: LLMClient | None,
    run_dir: Path | None,
    ruleset: str | None = None,
    redact: list[str] | None = None,
    on_generation=None,
    listeners=None,
    game_settings: dict | None = None,
) -> tuple[Evolution, RunResult]:
    game = MonsterMash.from_file(ruleset, **(game_settings or {}))
    seeds = default_seed_rules(game)
    rec = Recorder(run_dir, redact=redact, listeners=listeners)
    meta = {
        "run_dir": str(run_dir) if run_dir else None,
        "game": game.name,
        "ruleset": ruleset,
        "ruleset_hash": game.ruleset_hash,
        "game_settings": game.settings(),
        "config": cfg.to_dict(),
        "seed_rules": [s.model_dump(by_alias=True) for s in seeds],
        "llm_model": llm.model if llm else None,
        "git_commit": _git_commit(),
        "started": datetime.now().isoformat(timespec="seconds"),
    }
    rec.write_meta(meta)
    ev = Evolution(game, cfg, seeds, llm=llm, recorder=rec, on_generation=on_generation)
    try:
        result = ev.run()
    finally:
        meta.update(
            finished=datetime.now().isoformat(timespec="seconds"),
            battles=game.battles_run,
            llm_calls=len(rec.of_type("llm_call")),
        )
        rec.write_meta(meta)
        rec.close()
    return ev, result


def config_from_meta(meta: dict) -> EvolveConfig:
    from neurisko.engine.auditor import AuditConfig
    from neurisko.engine.credit import CreditConfig

    raw = dict(meta["config"])
    credit = CreditConfig(**raw.pop("credit"))
    audit = AuditConfig(**raw.pop("audit"))
    return replace(EvolveConfig(), **raw, credit=credit, audit=audit)


def replay_run(run_dir: Path, on_generation=None) -> tuple[Evolution, list[str]]:
    """Re-execute a recorded run with its recorded LLM replies. Returns the mismatches."""
    meta = load_meta(run_dir)
    events = load_events(run_dir)
    cfg = config_from_meta(meta)
    game = MonsterMash.from_file(meta.get("ruleset"), **meta.get("game_settings", {}))
    if game.ruleset_hash != meta["ruleset_hash"]:
        return None, [f"ruleset hash {game.ruleset_hash} != recorded {meta['ruleset_hash']}"]
    seeds = [RuleSpec.model_validate(s) for s in meta["seed_rules"]]
    llm = (
        ReplayClient(events, model=meta.get("llm_model") or "replay")
        if meta.get("llm_model")
        else None
    )
    ev = Evolution(game, cfg, seeds, llm=llm, recorder=Recorder(), on_generation=on_generation)
    ev.run()
    return ev, compare_generations(events, ev.rec.events)


def compare_generations(recorded: list[dict], replayed: list[dict]) -> list[str]:
    def gens(events: list[dict]) -> list[dict]:
        return [
            {k: v for k, v in e.items() if k not in TIMING_KEYS}
            for e in events
            if e["type"] == "generation"
        ]

    a, b = gens(recorded), gens(replayed)
    problems = []
    if len(a) != len(b):
        problems.append(f"{len(a)} recorded generations, {len(b)} replayed")
    for x, y in zip(a, b, strict=False):
        if x != y:
            diff = sorted(k for k in set(x) | set(y) if x.get(k) != y.get(k))
            problems.append(f"generation {x['gen']} differs in {diff}")
    return problems
