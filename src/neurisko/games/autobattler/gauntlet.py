"""The fixed opponent pool used to score designs."""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass

from neurisko.engine.game import BattleResult, MatchupResult, ScoreReport
from neurisko.games.autobattler.design import Design, cost, random_design, validate
from neurisko.games.autobattler.rules import Ruleset, RulesetError


@dataclass(frozen=True, slots=True)
class Opponent:
    name: str
    design: Design


def is_competitive(rules: Ruleset, design: Design) -> bool:
    """A design a real player might field: at least 3 units and at most 1 gold unspent."""
    return len(design) >= min(3, rules.limits.max_team_size) and (
        cost(rules, design) >= rules.limits.budget - 1
    )


def build_gauntlet(rules: Ruleset, seed: int = 1981, n_random: int = 18) -> list[Opponent]:
    """Archetypes plus `n_random` distinct competitive random designs, deterministic in `seed`.

    Weak random opponents (tiny teams, unspent budget) make many designs score 1.0, which
    hides the difference between good and great designs, so they are filtered out.
    """
    pool: list[Opponent] = []
    seen: set[Design] = set()
    for a in rules.archetypes:
        design = tuple(a.units)
        errors = validate(rules, design)
        if errors:
            raise RulesetError(f"archetype {a.name!r} is not a valid design: {'; '.join(errors)}")
        pool.append(Opponent(a.name, design))
        seen.add(design)
    rng = random.Random(seed)
    attempts = 0
    while len(pool) < len(rules.archetypes) + n_random and attempts < n_random * 1000:
        attempts += 1
        d = random_design(rules, rng)
        if d not in seen and is_competitive(rules, d):
            seen.add(d)
            pool.append(Opponent(f"random_{len(pool) - len(rules.archetypes):02d}", d))
    return pool


def score(
    design: Design,
    gauntlet: list[Opponent],
    simulate: Callable[[Design, Design, int], BattleResult],
    n_seeds: int = 3,
) -> ScoreReport:
    """Win rate of `design` against every opponent, on both sides, over `n_seeds` seeds."""
    matchups: list[MatchupResult] = []
    battles = 0
    for i, opp in enumerate(gauntlet):
        m = MatchupResult(opp.name)
        for s in range(n_seeds):
            seed = i * 1000 + s
            for as_a in (True, False):
                r = (
                    simulate(design, opp.design, seed)
                    if as_a
                    else simulate(opp.design, design, seed)
                )
                battles += 1
                me = "A" if as_a else "B"
                if r.winner == "draw":
                    m.draws += 1
                elif r.winner == me:
                    m.wins += 1
                else:
                    m.losses += 1
        matchups.append(m)
    total = sum(m.games for m in matchups)
    value = sum(m.wins + 0.5 * m.draws for m in matchups) / total if total else 0.0
    return ScoreReport(score=value, battles=battles, matchups=matchups)
