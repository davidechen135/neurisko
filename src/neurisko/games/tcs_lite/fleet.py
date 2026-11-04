"""Fleets: canonical form, cost and validation.

A fleet is `(classes, doctrine)`: `classes` is a sorted tuple of `((hull, armour, guns, drive),
count)` with distinct levels, and `doctrine` is a sorted tuple of flags. Equal fleets are equal
tuples, so they hash and cache the same.
"""

from __future__ import annotations

from collections.abc import Iterable

from neurisko.games.tcs_lite.rules import COMPONENTS, LEVELS, TcsRuleset

Levels = tuple[int, int, int, int]
Fleet = tuple[tuple[tuple[Levels, int], ...], tuple[str, ...]]
DOCTRINES = ("scuttle_disabled",)


def make_fleet(classes: Iterable[tuple[Levels, int]], doctrine: Iterable[str] = ()) -> Fleet:
    merged: dict[Levels, int] = {}
    for levels, count in classes:
        if count > 0:
            merged[tuple(levels)] = merged.get(tuple(levels), 0) + count
    return tuple(sorted(merged.items())), tuple(sorted(set(doctrine)))


def build_cost(rules: TcsRuleset, levels: Levels) -> int:
    c = rules.components
    parts = (c.hull, c.armour, c.guns, c.drive)
    return sum(p.cost[lv] for p, lv in zip(parts, levels, strict=True))


def class_cost(rules: TcsRuleset, levels: Levels, count: int) -> float:
    lim = rules.limits
    b = build_cost(rules, levels)
    return lim.design_fee + b + (count - 1) * b * lim.repeat_discount


def cost(rules: TcsRuleset, fleet: Fleet) -> float:
    return round(sum(class_cost(rules, lv, n) for lv, n in fleet[0]), 6)


def slots_used(levels: Levels) -> int:
    return levels[1] + levels[2] + levels[3]


def slots(rules: TcsRuleset, levels: Levels) -> int:
    return (levels[0] + 1) * rules.limits.slots_per_hull_level


def n_ships(fleet: Fleet) -> int:
    return sum(n for _, n in fleet[0])


def validate(rules: TcsRuleset, fleet: Fleet) -> list[str]:
    errors: list[str] = []
    classes, doctrine = fleet
    lim = rules.limits
    if not 1 <= len(classes) <= lim.max_classes:
        errors.append(f"{len(classes)} classes not in 1..{lim.max_classes}")
    seen = set()
    for levels, count in classes:
        tag = level_text(levels)
        if levels in seen:
            errors.append(f"class {tag} listed twice")
        seen.add(levels)
        if len(levels) != 4 or not all(0 <= x < LEVELS for x in levels):
            errors.append(f"class {tag}: component levels must be 0..{LEVELS - 1}")
            continue
        if not 1 <= count <= lim.max_ships_per_class:
            errors.append(f"class {tag}: count {count} not in 1..{lim.max_ships_per_class}")
        if slots_used(levels) > slots(rules, levels):
            errors.append(
                f"class {tag}: armour+guns+drive {slots_used(levels)} exceeds "
                f"{slots(rules, levels)} slots of hull {levels[0]}"
            )
    total = cost(rules, fleet) if not errors else None
    if total is not None and total > lim.budget + 1e-9:
        errors.append(f"cost {total:g} exceeds budget {lim.budget}")
    for d in doctrine:
        if d not in DOCTRINES:
            errors.append(f"unknown doctrine {d!r}")
        elif d == "scuttle_disabled" and not rules.era.allow_scuttle:
            errors.append(f"doctrine {d} is not allowed in the {rules.era.year} era")
    return errors


def level_text(levels: Levels) -> str:
    return "[" + " ".join(f"{c[0]}{lv}" for c, lv in zip(COMPONENTS, levels, strict=False)) + "]"


def describe(rules: TcsRuleset, fleet: Fleet) -> str:
    classes, doctrine = fleet
    body = " + ".join(f"{n}x{level_text(lv)}" for lv, n in sorted(classes, key=lambda x: -x[1]))
    tail = f" · {', '.join(doctrine)}" if doctrine else ""
    return (
        f"{body}{tail} · {n_ships(fleet)} ships, cost {cost(rules, fleet):g}/{rules.limits.budget}"
    )


def max_count(rules: TcsRuleset, fleet: Fleet, levels: Levels) -> int:
    """Largest count for `levels` that keeps the fleet within budget (other classes fixed)."""
    others = [(lv, n) for lv, n in fleet[0] if lv != levels]
    rest = sum(class_cost(rules, lv, n) for lv, n in others)
    lim = rules.limits
    b = build_cost(rules, levels)
    room = lim.budget - rest - lim.design_fee - b
    if room < -1e-9:
        return 0
    extra = int((room + 1e-9) // (b * lim.repeat_discount)) if b > 0 else lim.max_ships_per_class
    return max(0, min(lim.max_ships_per_class, 1 + extra))
