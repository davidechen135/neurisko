"""Monster Mash as an implementation of the engine's `Game` protocol."""

from __future__ import annotations

import random
from pathlib import Path

from neurisko.engine.game import BattleResult, ScoreReport
from neurisko.games.autobattler import design as _design
from neurisko.games.autobattler.combat import CompiledRules
from neurisko.games.autobattler.combat import simulate as _simulate
from neurisko.games.autobattler.design import Design
from neurisko.games.autobattler.gauntlet import Opponent, build_gauntlet
from neurisko.games.autobattler.gauntlet import score as _score
from neurisko.games.autobattler.rules import Ruleset, load_ruleset


class MonsterMash:
    name = "monster-mash"

    def __init__(
        self,
        rules: Ruleset | None = None,
        gauntlet_seed: int = 1981,
        n_random: int = 18,
        n_seeds: int = 3,
    ) -> None:
        self.rules = rules if rules is not None else load_ruleset()
        self.ruleset_hash = self.rules.hash
        self.n_seeds = n_seeds
        self._compiled = CompiledRules(self.rules)
        self.gauntlet: list[Opponent] = build_gauntlet(self.rules, gauntlet_seed, n_random)
        self._cache: dict[Design, ScoreReport] = {}

    @classmethod
    def from_file(cls, path: str | Path | None = None, **kwargs) -> MonsterMash:
        return cls(load_ruleset(path), **kwargs)

    def random_design(self, rng: random.Random) -> Design:
        return _design.random_design(self.rules, rng)

    def validate(self, design: Design) -> list[str]:
        return _design.validate(self.rules, design)

    def mutations(self, design: Design, rng: random.Random) -> list[Design]:
        return _design.mutations(self.rules, design, rng)

    def simulate(self, a: Design, b: Design, seed: int, log: bool = False) -> BattleResult:
        return _simulate(self._compiled, a, b, seed, log)

    def score(self, design: Design) -> ScoreReport:
        design = tuple(design)
        cached = self._cache.get(design)
        if cached is None:
            cached = _score(design, self.gauntlet, self.simulate, self.n_seeds)
            self._cache[design] = cached
        return cached

    def describe(self, design: Design) -> str:
        cost = _design.cost(self.rules, design)
        return f"[{' > '.join(design)}] cost {cost}/{self.rules.limits.budget}"

    def describe_rules(self) -> str:
        r = self.rules
        lim = r.limits
        lines = [
            f"Game: Monster Mash auto-battler (ruleset {r.name} v{r.version}, hash {r.hash}).",
            f"Team: 1-{lim.max_team_size} units, total cost <= {lim.budget}, "
            f"max {lim.max_copies} copies per unit. Order is front to back.",
            f"Combat: units act every `speed` ticks. Melee acts only from the first "
            f"{lim.front_line_size} living positions; ranged acts from anywhere. Everyone "
            f"targets the frontmost living enemy. Damage = max(1, atk - armor). Actions in a tick "
            f"are simultaneous. Draw after {lim.max_ticks} ticks.",
            "Units (id faction cost hp atk armor speed range ability):",
        ]
        for u in r.units:
            ab = "-"
            if u.ability is not None:
                params = u.ability.model_dump(exclude={"kind"})
                ab = u.ability.kind + (
                    "(" + ", ".join(f"{k}={v}" for k, v in params.items()) + ")" if params else ""
                )
            lines.append(
                f"  {u.id} {u.faction} {u.cost} {u.hp} {u.atk} {u.armor} {u.speed} {u.range} {ab}"
            )
        lines.append("Synergies (active while >= threshold living units of the faction):")
        for s in r.synergies:
            bonus = s.model_dump(exclude={"faction", "threshold"})
            parts = ", ".join(f"{k}={v}" for k, v in bonus.items() if v)
            lines.append(f"  {s.faction} x{s.threshold}: {parts}")
        return "\n".join(lines)
