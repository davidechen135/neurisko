"""Monster Mash balance patches: candidate single-stat changes and applying them."""

from __future__ import annotations

import copy
import math

from neurisko.engine.game import Patch
from neurisko.games.autobattler.design import validate
from neurisko.games.autobattler.rules import Ruleset, RulesetError, parse_ruleset

STAT_FIELDS = ("cost", "atk", "hp", "armor", "speed")
# Ability parameters that are "magnitudes" (bigger = stronger). `max` is the summon cap.
MAGNITUDES = ("amount", "fraction", "chance", "multiplier", "max")
INT_PARAMS = ("amount", "max")
MAIN_STAT_ATK_THRESHOLD = 6  # units with ATK <= 6 are judged by HP instead


def _lower(old: float, factor: float, integer: bool, floor: float) -> float | None:
    """old * factor, at least one step below old, not below floor; None if impossible."""
    if integer:
        new = min(round(old * factor), int(old) - 1)
        new = max(new, math.ceil(floor))
    else:
        new = round(max(old * factor, floor), 3)
    return new if new < old else None


def candidates(rules: Ruleset, part: str) -> list[Patch]:
    u = rules.unit_map[part]
    out: list[Patch] = []
    if u.cost + 1 <= rules.limits.budget:
        out.append(Patch(target=part, field="cost", old=u.cost, new=u.cost + 1))
    main = "hp" if u.atk <= MAIN_STAT_ATK_THRESHOLD else "atk"
    new = _lower(getattr(u, main), 0.8, integer=True, floor=1)
    if new is not None:
        out.append(Patch(target=part, field=main, old=getattr(u, main), new=new))
    if u.ability is not None:
        params = u.ability.model_dump(exclude={"kind"})
        for p in MAGNITUDES:
            if p not in params:
                continue
            old = params[p]
            if p == "multiplier":  # shrink the bonus above 1 by 30%, never below 1
                new = round(1 + (old - 1) * 0.7, 3) if old > 1 else None
            else:
                new = _lower(
                    old, 0.7, integer=p in INT_PARAMS, floor=1 if p in INT_PARAMS else 0.01
                )
            if new is not None and new < old:
                out.append(Patch(target=part, field=f"ability.{p}", old=old, new=new))
            break  # one magnitude per ability
    return out


def apply(rules: Ruleset, patch: Patch) -> tuple[Ruleset, list[str]]:
    """Patched ruleset and the archetypes dropped because they became invalid."""
    data = copy.deepcopy(rules.model_dump())
    unit = next((u for u in data["units"] if u["id"] == patch.target), None)
    if unit is None:
        raise RulesetError(f"patch targets unknown unit {patch.target!r}")
    value: float = patch.new
    if patch.field in STAT_FIELDS:
        if not float(value).is_integer():
            raise RulesetError(f"{patch.field} must be a whole number, got {value}")
        unit[patch.field] = int(value)
    elif patch.field.startswith("ability."):
        param = patch.field.split(".", 1)[1]
        if not unit.get("ability") or param not in unit["ability"] or param == "kind":
            raise RulesetError(f"{patch.target} has no ability parameter {param!r}")
        unit["ability"][param] = int(value) if param in INT_PARAMS else float(value)
    else:
        raise RulesetError(f"unknown patch field {patch.field!r}")
    patched = parse_ruleset(data, source=f"<patch {patch.text()}>")
    keep, dropped = [], []
    for a in data["archetypes"]:
        (dropped if validate(patched, tuple(a["units"])) else keep).append(a)
    if dropped:
        data["archetypes"] = keep
        patched = parse_ruleset(data, source=f"<patch {patch.text()}>")
    return patched, [a["name"] for a in dropped]
