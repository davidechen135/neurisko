"""Run the engine on many seeds (in parallel) and measure part shares."""

from __future__ import annotations

import os
import random
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from neurisko.engine.evolve import Evolution, EvolveConfig
from neurisko.engine.game import Game
from neurisko.engine.heuristics import RuleSpec
from neurisko.games.registry import make_game
from neurisko.report.schema import PartStat


@dataclass(frozen=True)
class Thresholds:
    dominant_share: float = 0.7
    dominant_lift: float = 1.8
    underused_share: float = 0.05
    underused_baseline: float = 0.2


@dataclass(frozen=True)
class RunSpec:
    game: str
    ruleset_json: str
    settings: dict[str, Any]
    seed_rules: list[dict]
    config: EvolveConfig
    top_k: int = 5
    tag: str = ""  # groups runs in one batch (e.g. by patch)


@dataclass
class RunOutcome:
    seed: int
    champion: list[str]
    top: list[list[str]]
    heuristics: list[dict] = field(default_factory=list)
    battles: int = 0
    seconds: float = 0.0
    tag: str = ""


def run_one(spec: RunSpec) -> RunOutcome:
    """One engine run without an LLM. Top-level so worker processes can pickle it."""
    t = time.perf_counter()
    game = make_game(spec.game, spec.ruleset_json, spec.settings)
    seeds = [RuleSpec.model_validate(s) for s in spec.seed_rules]
    ev = Evolution(game, spec.config, seeds)
    result = ev.run()
    heuristics = [
        {
            "text": h.text(),
            "action": dict(h.action),
            "worth": round(h.worth, 1),
            "applications": h.stats.applications,
            "improvements": h.stats.improvements,
        }
        for h in ev.design_heuristics()
    ]
    return RunOutcome(
        seed=spec.config.seed,
        champion=game.to_json(result.best),
        top=[game.to_json(d) for d in ev.population[: spec.top_k]],
        heuristics=heuristics,
        battles=game.battles_run,
        seconds=time.perf_counter() - t,
        tag=spec.tag,
    )


def run_batch(
    specs: Sequence[RunSpec],
    workers: int | None = None,
    on_done: Callable[[RunOutcome, int, int], None] | None = None,
) -> list[RunOutcome]:
    """Run every spec; results sorted by (tag, seed), so they do not depend on `workers`."""
    workers = workers or os.cpu_count() or 1
    outcomes: list[RunOutcome] = []
    if workers <= 1 or len(specs) <= 1:
        for s in specs:
            outcomes.append(run_one(s))
            if on_done:
                on_done(outcomes[-1], len(outcomes), len(specs))
    else:
        with ProcessPoolExecutor(max_workers=min(workers, len(specs))) as ex:
            for o in ex.map(run_one, specs):
                outcomes.append(o)
                if on_done:
                    on_done(o, len(outcomes), len(specs))
    return sorted(outcomes, key=lambda o: (o.tag, o.seed))


def make_specs(
    game: Game,
    seeds: Sequence[int],
    config: EvolveConfig,
    seed_rules: list[RuleSpec],
    top_k: int,
    tag: str = "",
) -> list[RunSpec]:
    rules = [s.model_dump(by_alias=True) for s in seed_rules]
    ruleset = game.ruleset_json()
    return [
        RunSpec(game.name, ruleset, game.settings(), rules, replace(config, seed=s), top_k, tag)
        for s in seeds
    ]


def baseline_shares(game: Game, n: int, seed: int = 1981) -> dict[str, float]:
    designs = game.baseline_designs(random.Random(seed), n)
    return {p: sum(p in game.parts(d) for d in designs) / len(designs) for p in game.part_names()}


def share_table(
    game: Game, outcomes: Sequence[RunOutcome], baseline: dict[str, float], th: Thresholds
) -> list[PartStat]:
    """Per part: mean/min/max share in top designs over runs, lift and flags."""
    rows: list[PartStat] = []
    for p in game.part_names():
        shares = [
            sum(p in game.parts(tuple(d)) for d in o.top) / len(o.top) for o in outcomes if o.top
        ]
        evolved = sum(shares) / len(shares) if shares else 0.0
        base = baseline.get(p, 0.0)
        lift = evolved / max(base, 0.01)
        flags = []
        if evolved >= th.dominant_share and lift >= th.dominant_lift:
            flags.append("dominant")
        if evolved <= th.underused_share and base >= th.underused_baseline:
            flags.append("underused")
        rows.append(
            PartStat(
                part=p,
                evolved=round(evolved, 4),
                lo=round(min(shares), 4) if shares else 0.0,
                hi=round(max(shares), 4) if shares else 0.0,
                baseline=round(base, 4),
                lift=round(lift, 3),
                champion_runs=sum(p in game.parts(tuple(o.champion)) for o in outcomes),
                runs=len(outcomes),
                flags=flags,
            )
        )
    rows.sort(key=lambda r: r.evolved, reverse=True)
    return rows


def outcome_dict(o: RunOutcome) -> dict:
    return asdict(o)
