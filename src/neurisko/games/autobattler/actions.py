"""Monster Mash vocabulary for heuristics: features (for conditions) and actions."""

from __future__ import annotations

from neurisko.engine.game import Action, ActionSchema, ScoreReport
from neurisko.games.autobattler.design import Design, validate
from neurisko.games.autobattler.rules import Ruleset

SELECTORS = ["@cheapest", "@most_expensive"]
POSITIONS = ["front", "back"]
BASE_FEATURES = ["n_units", "cost", "unspent", "n_ranged", "n_melee", "front_hp", "front_armor"]


def feature_names(rules: Ruleset) -> list[str]:
    factions = sorted({u.faction for u in rules.units})
    return (
        BASE_FEATURES
        + [f"count_{u.id}" for u in rules.units]
        + [f"count_{f}" for f in factions]
        + [f"winrate_vs_{a.name}" for a in rules.archetypes]
    )


def features(rules: Ruleset, design: Design, report: ScoreReport) -> dict[str, float]:
    um = rules.unit_map
    units = [um[u] for u in design]
    front = units[: rules.limits.front_line_size]
    cost = sum(u.cost for u in units)
    out: dict[str, float] = {
        "n_units": len(units),
        "cost": cost,
        "unspent": rules.limits.budget - cost,
        "n_ranged": sum(u.range == "ranged" for u in units),
        "n_melee": sum(u.range == "melee" for u in units),
        "front_hp": sum(u.hp for u in front),
        "front_armor": sum(u.armor for u in front),
    }
    for u in rules.units:
        out[f"count_{u.id}"] = design.count(u.id)
    for f in sorted({u.faction for u in rules.units}):
        out[f"count_{f}"] = sum(u.faction == f for u in units)
    by_name = {m.opponent: m.score for m in report.matchups}
    for a in rules.archetypes:
        out[f"winrate_vs_{a.name}"] = by_name.get(a.name, 0.0)
    return out


def action_schema(rules: Ruleset) -> ActionSchema:
    ids = [u.id for u in rules.units]
    return {
        "add_unit": {"unit": ids, "position": POSITIONS},
        "remove_unit": {"unit": ids + SELECTORS},
        "replace_unit": {"old": ids + SELECTORS, "new": ids},
        "move_unit": {"unit": ids, "to": POSITIONS},
    }


def _resolve(rules: Ruleset, design: Design, unit: str) -> int | None:
    """Index of the unit an action refers to, or None if it is not in the design."""
    if unit == "@cheapest":
        return min(range(len(design)), key=lambda i: (rules.unit_map[design[i]].cost, i))
    if unit == "@most_expensive":
        return max(range(len(design)), key=lambda i: (rules.unit_map[design[i]].cost, -i))
    return design.index(unit) if unit in design else None


def apply_action(rules: Ruleset, design: Design, action: Action) -> Design | None:
    kind = action.get("kind")
    out: Design | None = None
    if kind == "add_unit":
        u = action["unit"]
        out = (u, *design) if action["position"] == "front" else (*design, u)
    elif kind in ("remove_unit", "replace_unit", "move_unit"):
        key = "old" if kind == "replace_unit" else "unit"
        i = _resolve(rules, design, action[key])
        if i is None:
            return None
        rest = design[:i] + design[i + 1 :]
        if kind == "remove_unit":
            out = rest
        elif kind == "replace_unit":
            out = design[:i] + (action["new"],) + design[i + 1 :]
        else:
            out = (design[i], *rest) if action["to"] == "front" else (*rest, design[i])
    if out is None or out == design or validate(rules, out):
        return None
    return out
