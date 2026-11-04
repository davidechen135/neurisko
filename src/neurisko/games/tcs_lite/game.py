"""TCS-lite as an implementation of the engine's `Game` protocol."""

from __future__ import annotations

import copy
import random
from collections.abc import Sequence
from importlib import resources
from pathlib import Path
from typing import Any

from neurisko.engine.game import Action, ActionSchema, BattleResult, Event, Patch, ScoreReport
from neurisko.games.autobattler.gauntlet import Opponent
from neurisko.games.autobattler.gauntlet import score as gauntlet_score
from neurisko.games.tcs_lite import NOTICE
from neurisko.games.tcs_lite import fleet as F
from neurisko.games.tcs_lite.combat import Compiled, simulate
from neurisko.games.tcs_lite.rules import (
    COMPONENTS,
    LEVELS,
    TcsRuleset,
    load_ruleset,
    parse_ruleset,
)

SEEDS = "seed_heuristics.toml"
SELECTORS = ["@largest", "@smallest", "@cheapest", "@most_expensive"]
CHANGES = ["+1", "+5", "+20", "-1", "-5", "max"]
ADD_COUNTS = ["1", "5", "20", "max"]
SWARM_SHIPS = 30
ELITE_SHIPS = 4
COMPETITIVE = 0.85  # random fleets spending less than this share of the budget are skipped
PARTS = [
    "swarm",
    "elite",
    "armour_max",
    "armour_none",
    "guns_max",
    "drive_max",
    "drive_none",
    "scuttle",
]


class TcsLite:
    name = "tcs-lite"

    def __init__(
        self,
        rules: TcsRuleset | None = None,
        gauntlet_seed: int = 1981,
        n_random: int = 12,
        n_seeds: int = 3,
        seed_offset: int = 0,
    ) -> None:
        self.rules = rules if rules is not None else load_ruleset()
        self.ruleset_hash = self.rules.hash
        self.gauntlet_seed = gauntlet_seed
        self.n_random = n_random
        self.n_seeds = n_seeds
        self.seed_offset = seed_offset
        self.battles_run = 0
        self._c = Compiled(self.rules)
        self.templates = {t.name: t.levels() for t in self.rules.templates}
        self.gauntlet = self._build_gauntlet()
        self._cache: dict[tuple, ScoreReport] = {}

    @classmethod
    def from_file(cls, path: str | Path | None = None, era: str = "1981", **kw) -> TcsLite:
        return cls(load_ruleset(path, era=era), **kw)

    # --- designs ------------------------------------------------------------------------------

    def validate(self, design: F.Fleet) -> list[str]:
        return F.validate(self.rules, design)

    def _valid_levels(self, rng: random.Random) -> F.Levels:
        if rng.random() < 0.5:
            return rng.choice(list(self.templates.values()))
        for _ in range(100):
            lv = tuple(rng.randrange(LEVELS) for _ in COMPONENTS)
            if F.slots_used(lv) <= F.slots(self.rules, lv):
                return lv
        return (0, 0, 0, 0)

    def random_design(self, rng: random.Random) -> F.Fleet:
        lim = self.rules.limits
        for _ in range(200):
            levels = list(dict.fromkeys(self._valid_levels(rng) for _ in range(rng.randint(1, 3))))
            counts = dict.fromkeys(levels, 1)
            doctrine = (
                ["scuttle_disabled"]
                if (self.rules.era.allow_scuttle and rng.random() < 0.3)
                else []
            )
            fleet = F.make_fleet(counts.items(), doctrine)
            if self.validate(fleet):
                continue
            # Fill the budget by adding ships to random classes until nothing fits.
            stuck = 0
            while stuck < 8:
                lv = rng.choice(levels)
                step = rng.choice((1, 1, 2, 5, 10))
                trial = F.make_fleet({**counts, lv: counts[lv] + step}.items(), doctrine)
                if counts[lv] + step <= lim.max_ships_per_class and not self.validate(trial):
                    counts[lv] += step
                    fleet = trial
                    stuck = 0
                else:
                    stuck += 1
            return fleet
        return F.make_fleet([((0, 0, 0, 0), 1)])

    def is_competitive(self, fleet: F.Fleet) -> bool:
        return F.cost(self.rules, fleet) >= COMPETITIVE * self.rules.limits.budget

    def mutations(self, design: F.Fleet, rng: random.Random) -> list[F.Fleet]:
        out = []
        for kind, params in self.action_schema().items():
            keys = list(params)
            combos: list[dict[str, str]] = [{}]
            for k in keys:
                combos = [{**c, k: v} for c in combos for v in params[k]]
            for c in combos:
                d = self.apply_action(design, {"kind": kind, **c}, rng)
                if d is not None:
                    out.append(d)
        out = list(dict.fromkeys(out))
        rng.shuffle(out)
        return out

    # --- actions ------------------------------------------------------------------------------

    def action_schema(self) -> ActionSchema:
        flags = ["scuttle_disabled"]
        return {
            "set_count": {"class": SELECTORS, "change": CHANGES},
            "upgrade": {"class": SELECTORS, "component": list(COMPONENTS)},
            "downgrade": {"class": SELECTORS, "component": list(COMPONENTS)},
            "add_class": {"template": list(self.templates), "count": ADD_COUNTS},
            "remove_class": {"class": SELECTORS},
            "toggle_doctrine": {"flag": flags},
        }

    def _select(self, fleet: F.Fleet, sel: str) -> F.Levels | None:
        classes = fleet[0]
        if not classes:
            return None
        key = {
            "@largest": lambda c: (c[1], c[0]),
            "@smallest": lambda c: (-c[1], c[0]),
            "@cheapest": lambda c: (-F.build_cost(self.rules, c[0]), c[0]),
            "@most_expensive": lambda c: (F.build_cost(self.rules, c[0]), c[0]),
        }[sel]
        return max(classes, key=key)[0]

    def _fit(self, counts: dict[F.Levels, int], doctrine, keep: F.Levels) -> F.Fleet | None:
        """Shrink class `keep` until the fleet fits the budget; None if impossible."""
        fleet = F.make_fleet(counts.items(), doctrine)
        if not self.validate(fleet):
            return fleet
        cap = F.max_count(self.rules, fleet, keep)
        if cap < 1:
            return None
        counts = {**counts, keep: min(counts[keep], cap)}
        fleet = F.make_fleet(counts.items(), doctrine)
        return None if self.validate(fleet) else fleet

    def apply_action(self, design: F.Fleet, action: Action, rng: random.Random) -> F.Fleet | None:
        classes, doctrine = design
        counts = dict(classes)
        kind = action.get("kind")
        out: F.Fleet | None = None
        if kind == "toggle_doctrine":
            flag = action["flag"]
            new = [d for d in doctrine if d != flag] if flag in doctrine else [*doctrine, flag]
            out = F.make_fleet(classes, new)
        elif kind == "add_class":
            lv = self.templates[action["template"]]
            if lv in counts:
                return None
            trial = F.make_fleet({**counts, lv: 1}.items(), doctrine)
            n = action["count"]
            want = F.max_count(self.rules, trial, lv) if n == "max" else int(n)
            if want < 1:
                return None
            out = F.make_fleet({**counts, lv: want}.items(), doctrine)
        else:
            lv = self._select(design, action["class"])
            if lv is None:
                return None
            if kind == "remove_class":
                if len(counts) == 1:
                    return None
                counts.pop(lv)
                out = F.make_fleet(counts.items(), doctrine)
            elif kind == "set_count":
                ch = action["change"]
                new = F.max_count(self.rules, design, lv) if ch == "max" else counts[lv] + int(ch)
                if new < 1:
                    return None
                out = F.make_fleet({**counts, lv: new}.items(), doctrine)
            elif kind in ("upgrade", "downgrade"):
                i = COMPONENTS.index(action["component"])
                nl = list(lv)
                nl[i] += 1 if kind == "upgrade" else -1
                nl = tuple(nl)
                if not 0 <= nl[i] < LEVELS or nl in counts:
                    return None
                n = counts.pop(lv)
                counts[nl] = n
                out = self._fit(counts, doctrine, nl)
        if out is None or out == design or self.validate(out):
            return None
        return out

    # --- battles and scores --------------------------------------------------------------------

    def simulate(self, a: F.Fleet, b: F.Fleet, seed: int, log: bool = False) -> BattleResult:
        self.battles_run += 1
        return simulate(self._c, a, b, seed, log)

    def _build_gauntlet(self) -> list[Opponent]:
        pool, seen = [], set()
        for a in self.rules.archetypes:
            d = F.make_fleet([(c.levels(), c.count) for c in a.classes], a.doctrine)
            if not self.validate(d):
                pool.append(Opponent(a.name, d))
                seen.add(d)
        rng = random.Random(self.gauntlet_seed)
        k = 0
        for _ in range(self.n_random * 200):
            if k == self.n_random:
                break
            d = self.random_design(rng)
            if d not in seen and self.is_competitive(d):
                seen.add(d)
                pool.append(Opponent(f"random_{k:02d}", d))
                k += 1
        return pool

    def score(self, design: F.Fleet, extra_opponents: Sequence[F.Fleet] = ()) -> ScoreReport:
        key = (design, tuple(extra_opponents))
        hit = self._cache.get(key)
        if hit is None:
            pool = self.gauntlet + [
                Opponent(f"hof_{i:02d}", e) for i, e in enumerate(extra_opponents)
            ]
            hit = gauntlet_score(design, pool, self.simulate, self.n_seeds, self.seed_offset)
            self._cache[key] = hit
        return hit

    def held_out(self) -> TcsLite:
        return TcsLite(
            self.rules,
            gauntlet_seed=self.gauntlet_seed + 1,
            n_random=self.n_random,
            n_seeds=self.n_seeds,
            seed_offset=self.seed_offset + 1,
        )

    # --- vocabulary ----------------------------------------------------------------------------

    def feature_names(self) -> list[str]:
        base = [
            "n_ships",
            "n_classes",
            "unspent",
            "total_shots",
            "total_hp",
            "mean_armour",
            "mean_drive",
            "max_hull",
            "share_minimal",
            "doctrine_scuttle",
        ]
        return base + [f"winrate_vs_{a.name}" for a in self.rules.archetypes]

    def features(self, design: F.Fleet, report: ScoreReport) -> dict[str, float]:
        classes, doctrine = design
        c = self.rules.components
        n = F.n_ships(design)
        out: dict[str, float] = {
            "n_ships": n,
            "n_classes": len(classes),
            "unspent": round(self.rules.limits.budget - F.cost(self.rules, design), 3),
            "total_shots": sum(c.guns.shots[lv[2]] * k for lv, k in classes),
            "total_hp": sum(c.hull.hp[lv[0]] * k for lv, k in classes),
            "mean_armour": round(sum(lv[1] * k for lv, k in classes) / n, 3),
            "mean_drive": round(sum(lv[3] * k for lv, k in classes) / n, 3),
            "max_hull": max(lv[0] for lv, _ in classes),
            "share_minimal": round(sum(k for lv, k in classes if lv[0] == 0) / n, 3),
            "doctrine_scuttle": float("scuttle_disabled" in doctrine),
        }
        by = {m.opponent: m.score for m in report.matchups}
        for a in self.rules.archetypes:
            out[f"winrate_vs_{a.name}"] = by.get(a.name, 0.0)
        return out

    # --- text and JSON -------------------------------------------------------------------------

    def to_json(self, design: F.Fleet) -> dict[str, Any]:
        return {"classes": [[list(lv), n] for lv, n in design[0]], "doctrine": list(design[1])}

    def from_json(self, obj: Any) -> F.Fleet:
        return F.make_fleet([(tuple(lv), n) for lv, n in obj["classes"]], obj["doctrine"])

    def parse_design(self, text: str) -> F.Fleet:
        """`99x0000,4x3332,scuttle_disabled`: count x hull armour guns drive digits."""
        classes, doctrine = [], []
        for part in (p.strip() for p in text.split(",") if p.strip()):
            if part in F.DOCTRINES:
                doctrine.append(part)
                continue
            n, _, digits = part.partition("x")
            if not (n.isdigit() and len(digits) == 4 and digits.isdigit()):
                raise ValueError(f"bad class {part!r}; expected e.g. 99x0000")
            classes.append((tuple(int(ch) for ch in digits), int(n)))
        return F.make_fleet(classes, doctrine)

    def describe(self, design: F.Fleet) -> str:
        return F.describe(self.rules, design)

    def describe_rules(self) -> str:
        r, lim, c = self.rules, self.rules.limits, self.rules.components
        era = r.era
        lines = [
            f"Game: TCS-lite fleet battle, {era.year} era (ruleset hash {r.hash}). {NOTICE}",
            f"Fleet: 1-{lim.max_classes} ship classes, 1-{lim.max_ships_per_class} ships each, "
            f"total cost <= {lim.budget}. Each class pays a design fee of {lim.design_fee} plus "
            f"its build cost; every further ship of the class costs {lim.repeat_discount:g} x "
            "build cost.",
            "A class has levels 0-3 of hull, armour, guns, drive; armour+guns+drive <= "
            f"(hull+1) x {lim.slots_per_hull_level}.",
            f"  hull: cost {c.hull.cost}, hit points {c.hull.hp}",
            f"  armour: cost {c.armour.cost}, chance to deflect a hit {c.armour.deflect}",
            f"  guns: cost {c.guns.cost}, shots per round {c.guns.shots}",
            f"  drive: cost {c.drive.cost}, chance an enemy shot misses {c.drive.evade}",
            "Combat: each round every ship able to fire shoots at random enemy ships that are "
            "not destroyed; each hit does 1 damage. A ship at half its hit points can no longer "
            "fire (disabled) but still draws fire; at full hit points it is destroyed. The last "
            f"fleet able to fire wins; draw after {lim.max_rounds} rounds.",
        ]
        if era.max_disabled_fraction < 1:
            lines.append(
                f"{era.year} rule: a fleet in which more than {era.max_disabled_fraction:g} of "
                "its remaining ships are disabled withdraws and loses."
            )
        if era.allow_scuttle:
            lines.append(
                "Doctrine scuttle_disabled: the fleet removes its own disabled ships at the end of "
                "each round."
            )
        templates = ", ".join(f"{k}={F.level_text(v)}" for k, v in self.templates.items())
        lines.append(f"Templates for add_class: {templates}.")
        return "\n".join(lines)

    def describe_event(self, event: Event) -> str:
        e = event
        t = f"round {e.tick:>2}  "
        side = e.actor.split(":")[0]
        match e.kind:
            case "attack":
                return f"{t}fleet {side} lands {e.amount} hits"
            case "disabled":
                return f"{t}fleet {side}: {e.amount} ships disabled"
            case "death":
                return f"{t}fleet {side}: {e.amount} ships destroyed"
            case "scuttle":
                return f"{t}fleet {side} SCUTTLES {e.amount} disabled ships"
            case "withdraw":
                return f"{t}fleet {side} WITHDRAWS ({e.amount} ships disabled)"
            case _:
                return f"{t}{e.kind} {e.actor} {e.amount}"

    # --- report and generality -----------------------------------------------------------------

    def ruleset_json(self) -> str:
        return self.rules.model_dump_json()

    def settings(self) -> dict:
        return {
            "gauntlet_seed": self.gauntlet_seed,
            "n_random": self.n_random,
            "n_seeds": self.n_seeds,
            "seed_offset": self.seed_offset,
        }

    def part_names(self) -> list[str]:
        return list(PARTS)

    def parts(self, design: F.Fleet) -> set[str]:
        classes, doctrine = design
        n = F.n_ships(design)
        out = set()
        if n >= SWARM_SHIPS:
            out.add("swarm")
        if n <= ELITE_SHIPS:
            out.add("elite")
        if any(lv[1] == LEVELS - 1 for lv, _ in classes):
            out.add("armour_max")
        if all(lv[1] == 0 for lv, _ in classes):
            out.add("armour_none")
        if any(lv[2] == LEVELS - 1 for lv, _ in classes):
            out.add("guns_max")
        if any(lv[3] == LEVELS - 1 for lv, _ in classes):
            out.add("drive_max")
        if all(lv[3] == 0 for lv, _ in classes):
            out.add("drive_none")
        if "scuttle_disabled" in doctrine and self.rules.era.allow_scuttle:
            out.add("scuttle")
        return out

    def baseline_designs(self, rng: random.Random, n: int) -> list[F.Fleet]:
        out = []
        for _ in range(n * 100):
            if len(out) == n:
                break
            d = self.random_design(rng)
            if self.is_competitive(d):
                out.append(d)
        return out

    def patch_candidates(self, part: str) -> list[Patch]:
        r = self.rules
        lim, c = r.limits, r.components

        def p(path: str, old: float, new: float) -> Patch:
            return Patch(
                target=part, field=path, old=old, new=new, label=f"{path} {old:g}->{new:g}"
            )

        if part in ("swarm", "armour_none", "drive_none"):
            return [
                p("components.hull.cost.0", c.hull.cost[0], c.hull.cost[0] + 1),
                p(
                    "limits.repeat_discount",
                    lim.repeat_discount,
                    min(1.0, lim.repeat_discount + 0.15),
                ),
                p("limits.max_ships_per_class", lim.max_ships_per_class, 40),
            ]
        if part == "scuttle":
            return [
                p(
                    "era.max_disabled_fraction",
                    r.era.max_disabled_fraction,
                    min(1.0, round(r.era.max_disabled_fraction + 0.3, 3)),
                ),
                p("components.hull.cost.0", c.hull.cost[0], c.hull.cost[0] + 1),
            ]
        comp = {
            "armour_max": "armour",
            "guns_max": "guns",
            "drive_max": "drive",
            "elite": "hull",
        }.get(part)
        if comp is None:
            return []
        old = getattr(c, comp).cost[3]
        return [p(f"components.{comp}.cost.3", old, round(old * 1.3))]

    def with_patch(self, patch: Patch) -> tuple[TcsLite, list[str]]:
        data = copy.deepcopy(self.rules.model_dump())
        node: Any = data
        keys = patch.field.split(".")
        for k in keys[:-1]:
            node = node[int(k)] if k.isdigit() else node[k]
        last = keys[-1]
        old = node[int(last)] if last.isdigit() else node[last]
        new = (
            int(patch.new) if isinstance(old, int) and float(patch.new).is_integer() else patch.new
        )
        if last.isdigit():
            node[int(last)] = new
        else:
            node[last] = new
        rules = parse_ruleset(data, source=f"<patch {patch.text()}>")
        game = TcsLite(rules, **self.settings())
        names = {a.name for a in rules.archetypes}
        kept = {o.name for o in game.gauntlet}
        return game, sorted(names - kept)

    def seed_rules(self) -> list:
        from neurisko.engine.heuristics import load_seed_rules

        path = Path(str(resources.files("neurisko.games.tcs_lite").joinpath("data", SEEDS)))
        return load_seed_rules(path, self.feature_names(), self.action_schema())

    def without_part(self, design: F.Fleet, part: str) -> list[F.Fleet]:
        """One-step neighbours that lose the trait."""
        rng = random.Random(0)
        return [d for d in self.mutations(design, rng) if part not in self.parts(d)]

    def adds_part(self, action: Action, part: str) -> bool:
        kind, a = action.get("kind"), action
        if part == "swarm":
            return (kind == "set_count" and a.get("change", "").startswith(("+", "max"))) or (
                kind == "add_class" and a.get("template") == "minimal"
            )
        if part == "elite":
            return kind == "remove_class" or (
                kind == "set_count" and a.get("change", "").startswith("-")
            )
        if part == "scuttle":
            return kind == "toggle_doctrine"
        comp = {"armour_max": "armour", "guns_max": "guns", "drive_max": "drive"}.get(part)
        if comp:
            return kind == "upgrade" and a.get("component") == comp
        comp = {"armour_none": "armour", "drive_none": "drive"}.get(part)
        if comp:
            return kind == "downgrade" and a.get("component") == comp
        return False

    def featured_opponents(self, design: F.Fleet, n: int = 3) -> list[F.Fleet]:
        names = {o.name: o.design for o in self.gauntlet}
        worst = sorted(self.score(design).matchups, key=lambda m: m.score)[:n]
        return [names[m.opponent] for m in worst if m.opponent in names]
