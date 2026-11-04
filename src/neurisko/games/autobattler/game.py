"""Monster Mash as an implementation of the engine's `Game` protocol."""

from __future__ import annotations

import random
from collections.abc import Sequence
from importlib import resources
from pathlib import Path

from neurisko.engine.game import Action, ActionSchema, BattleResult, Patch, ScoreReport
from neurisko.games.autobattler import actions as _actions
from neurisko.games.autobattler import design as _design
from neurisko.games.autobattler import patches as _patches
from neurisko.games.autobattler.combat import CompiledRules
from neurisko.games.autobattler.combat import simulate as _simulate
from neurisko.games.autobattler.design import Design
from neurisko.games.autobattler.gauntlet import Opponent, build_gauntlet, is_competitive
from neurisko.games.autobattler.gauntlet import score as _score
from neurisko.games.autobattler.rules import Ruleset, load_ruleset

SEEDS = "seed_heuristics.toml"


class MonsterMash:
    name = "monster-mash"

    def __init__(
        self,
        rules: Ruleset | None = None,
        gauntlet_seed: int = 1981,
        n_random: int = 18,
        n_seeds: int = 3,
        seed_offset: int = 0,
    ) -> None:
        self.rules = rules if rules is not None else load_ruleset()
        self.ruleset_hash = self.rules.hash
        self.gauntlet_seed = gauntlet_seed
        self.n_random = n_random
        self.n_seeds = n_seeds
        self.seed_offset = seed_offset
        self.battles_run = 0  # battles actually simulated (cache misses), for budgets
        self._compiled = CompiledRules(self.rules)
        self.gauntlet: list[Opponent] = build_gauntlet(self.rules, gauntlet_seed, n_random)
        self._cache: dict[tuple[Design, tuple[Design, ...]], ScoreReport] = {}
        self._feature_names = _actions.feature_names(self.rules)
        self._action_schema = _actions.action_schema(self.rules)

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
        self.battles_run += 1
        return _simulate(self._compiled, a, b, seed, log)

    def score(self, design: Design, extra_opponents: Sequence[Design] = ()) -> ScoreReport:
        design = tuple(design)
        extras = tuple(tuple(e) for e in extra_opponents)
        key = (design, extras)
        cached = self._cache.get(key)
        if cached is None:
            pool = self.gauntlet + [Opponent(f"hof_{i:02d}", e) for i, e in enumerate(extras)]
            cached = _score(design, pool, self.simulate, self.n_seeds, self.seed_offset)
            self._cache[key] = cached
        return cached

    def feature_names(self) -> list[str]:
        return list(self._feature_names)

    def features(self, design: Design, report: ScoreReport) -> dict[str, float]:
        return _actions.features(self.rules, tuple(design), report)

    def action_schema(self) -> ActionSchema:
        return {
            k: {p: list(v) for p, v in params.items()} for k, params in self._action_schema.items()
        }

    def apply_action(self, design: Design, action: Action, rng: random.Random) -> Design | None:
        return _actions.apply_action(self.rules, tuple(design), action)

    def held_out(self) -> MonsterMash:
        return MonsterMash(
            self.rules,
            gauntlet_seed=self.gauntlet_seed + 1,
            n_random=self.n_random,
            n_seeds=self.n_seeds,
            seed_offset=self.seed_offset + 1,
        )

    def to_json(self, design: Design) -> list[str]:
        return list(design)

    # --- balance report --------------------------------------------------------------------

    def ruleset_json(self) -> str:
        return self.rules.model_dump_json()

    def parts(self, design: Design) -> set[str]:
        return set(design)

    def part_names(self) -> list[str]:
        return [u.id for u in self.rules.units]

    def baseline_designs(self, rng: random.Random, n: int) -> list[Design]:
        out: list[Design] = []
        for _ in range(n * 1000):
            if len(out) == n:
                break
            d = self.random_design(rng)
            if is_competitive(self.rules, d):
                out.append(d)
        return out

    def patch_candidates(self, part: str) -> list[Patch]:
        return _patches.candidates(self.rules, part)

    def with_patch(self, patch: Patch) -> tuple[MonsterMash, list[str]]:
        rules, dropped = _patches.apply(self.rules, patch)
        game = MonsterMash(
            rules,
            gauntlet_seed=self.gauntlet_seed,
            n_random=self.n_random,
            n_seeds=self.n_seeds,
            seed_offset=self.seed_offset,
        )
        return game, dropped

    # --- generality ---------------------------------------------------------------------------

    def from_json(self, obj) -> Design:
        return tuple(obj)

    def parse_design(self, text: str) -> Design:
        return tuple(p.strip() for p in text.split(",") if p.strip())

    def seed_rules(self) -> list:
        from neurisko.engine.heuristics import load_seed_rules

        path = Path(str(resources.files("neurisko.games.autobattler").joinpath("data", SEEDS)))
        return load_seed_rules(path, self.feature_names(), self.action_schema())

    def featured_opponents(self, design: Design, n: int = 3) -> list[Design]:
        names = {o.name: o.design for o in self.gauntlet}
        worst = sorted(self.score(tuple(design)).matchups, key=lambda m: m.score)[:n]
        return [names[m.opponent] for m in worst if m.opponent in names]

    def describe_event(self, event) -> str:
        e = event
        t = f"t{e.tick:>4}  "
        match e.kind:
            case "attack":
                return f"{t}{e.actor:<18} hits   {e.target:<18} {e.amount:>4}"
            case "dodge":
                return f"{t}{e.actor:<18} dodges {e.target}"
            case "heal":
                return f"{t}{e.actor:<18} heals  {e.target:<18} {e.amount:>4}"
            case "summon":
                return f"{t}{e.actor:<18} raises {e.target}"
            case "death":
                return f"{t}{e.actor:<18} DIES"
            case _:
                return f"{t}synergy {'ON ' if e.kind == 'synergy_on' else 'OFF'} {e.actor}"

    def without_part(self, design: Design, part: str) -> list[Design]:
        """Replace one copy of the unit by every other unit, or remove it."""
        design = tuple(design)
        if part not in design:
            return []
        i = design.index(part)
        out = [design[:i] + (u,) + design[i + 1 :] for u in self.part_names() if u != part]
        out.append(design[:i] + design[i + 1 :])
        return [d for d in out if d and not self.validate(d)]

    def adds_part(self, action: Action, part: str) -> bool:
        kind = action.get("kind")
        return (kind == "add_unit" and action.get("unit") == part) or (
            kind == "replace_unit" and action.get("new") == part
        )

    def settings(self) -> dict:
        """Constructor arguments other than the rules, to rebuild an equivalent game."""
        return {
            "gauntlet_seed": self.gauntlet_seed,
            "n_random": self.n_random,
            "n_seeds": self.n_seeds,
            "seed_offset": self.seed_offset,
        }

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
