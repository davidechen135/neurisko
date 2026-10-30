"""Team designs: validation, random generation and one-step mutations.

A design is a tuple of unit ids; index 0 is the front of the team.
"""

from __future__ import annotations

import random
from collections import Counter

from neurisko.games.autobattler.rules import Ruleset

Design = tuple[str, ...]


def validate(rules: Ruleset, design: Design) -> list[str]:
    """Return every violated constraint; empty means valid."""
    errors: list[str] = []
    lim = rules.limits
    if not 1 <= len(design) <= lim.max_team_size:
        errors.append(f"team size {len(design)} not in 1..{lim.max_team_size}")
    unknown = [u for u in design if u not in rules.unit_map]
    if unknown:
        errors.append(f"unknown units: {', '.join(unknown)}")
    cost = sum(rules.unit_map[u].cost for u in design if u in rules.unit_map)
    if cost > lim.budget:
        errors.append(f"cost {cost} exceeds budget {lim.budget}")
    for unit, n in sorted(Counter(design).items()):
        if n > lim.max_copies:
            errors.append(f"{unit} appears {n} times (max {lim.max_copies})")
    return errors


def cost(rules: Ruleset, design: Design) -> int:
    return sum(rules.unit_map[u].cost for u in design)


def _can_add(rules: Ruleset, design: Design, unit: str) -> bool:
    lim = rules.limits
    return (
        len(design) < lim.max_team_size
        and cost(rules, design) + rules.unit_map[unit].cost <= lim.budget
        and design.count(unit) < lim.max_copies
    )


def random_design(rules: Ruleset, rng: random.Random) -> Design:
    """A random valid design. Size is drawn first, then affordable units are added."""
    target = rng.randint(1, rules.limits.max_team_size)
    design: Design = ()
    ids = [u.id for u in rules.units]
    while len(design) < target:
        options = [u for u in ids if _can_add(rules, design, u)]
        if not options:
            break
        design += (rng.choice(options),)
    return design


def neighbours(rules: Ruleset, design: Design) -> list[Design]:
    """All distinct valid designs one add/remove/replace/swap away, in a stable order."""
    ids = [u.id for u in rules.units]
    out: list[Design] = []
    # add, at any position
    for unit in ids:
        if _can_add(rules, design, unit):
            for pos in range(len(design) + 1):
                out.append(design[:pos] + (unit,) + design[pos:])
    # remove
    if len(design) > 1:
        for pos in range(len(design)):
            out.append(design[:pos] + design[pos + 1 :])
    # replace
    for pos, old in enumerate(design):
        for unit in ids:
            if unit != old:
                out.append(design[:pos] + (unit,) + design[pos + 1 :])
    # swap
    for i in range(len(design)):
        for j in range(i + 1, len(design)):
            if design[i] != design[j]:
                d = list(design)
                d[i], d[j] = d[j], d[i]
                out.append(tuple(d))
    seen: set[Design] = {design}
    result: list[Design] = []
    for d in out:
        if d not in seen and not validate(rules, d):
            seen.add(d)
            result.append(d)
    return result


def mutations(rules: Ruleset, design: Design, rng: random.Random) -> list[Design]:
    """Valid neighbours in a seeded random order; empty if none exist."""
    result = neighbours(rules, design)
    rng.shuffle(result)
    return result
