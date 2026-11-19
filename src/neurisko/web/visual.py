"""Data for the visual battle replay (the arena above the text log).

`steps[i]` belongs to `lines[i]` of the battle view, so the arena and the log advance together.

Monster Mash: the arena state is rebuilt from the log and the ruleset, following combat.py
exactly (damage, heals, deaths, summons, synergy HP changes); tests check the rebuilt
survivors against the simulator's. TCS-lite: the simulator logs a per-ship `status` event each
round, which is attached to the last log line of that round.
"""

from __future__ import annotations

from typing import Any

from neurisko.engine.game import Event

# Step: [kind, actor, target, amount, updates]. Monster Mash updates are [label, hp, max_hp];
# TCS-lite updates are {"A": "aadx…", "B": "…"} per-ship states after the round, or {}.


def monster_visual(game: Any, a: Any, b: Any, events: list[Event]) -> dict[str, Any]:
    rules = game.rules
    protos = {u.id: u for u in rules.units}
    syn = {s.faction: s for s in rules.synergies}
    units: list[dict[str, Any]] = []
    state: dict[str, dict[str, Any]] = {}
    active: dict[str, set[str]] = {"A": set(), "B": set()}

    def base_max(uid: str, side: str) -> int:
        p = protos[uid]
        s = syn.get(p.faction)
        if s is not None and p.faction in active[side]:
            return round(p.hp * (1 + s.hp_pct))
        return p.hp

    def add(label: str, summoned: bool) -> dict[str, Any]:
        side, uid = label[0], label.split(":", 1)[1]
        p = protos[uid]
        st = {"hp": p.hp, "max": p.hp, "alive": True, "side": side, "id": uid}
        state[label] = st
        units.append(
            {
                "label": label,
                "id": uid,
                "side": side,
                "faction": p.faction,
                "ranged": p.range == "ranged",
                "hp": p.hp,
                "summoned": summoned,
            }
        )
        return st

    def set_max(st: dict[str, Any], new_max: int) -> None:
        if new_max != st["max"]:
            delta = new_max - st["max"]
            st["max"] = new_max
            st["hp"] = st["hp"] + delta if delta > 0 else min(st["hp"], new_max)

    for side, design in (("A", a), ("B", b)):
        for i, uid in enumerate(design):
            add(f"{side}{i}:{uid}", False)

    steps: list[list[Any]] = []
    for e in events:
        touched: list[str] = []
        if e.kind == "attack":
            state[e.target]["hp"] -= e.amount
            touched.append(e.target)
        elif e.kind == "heal":
            state[e.target]["hp"] += e.amount
            touched.append(e.target)
        elif e.kind == "death":
            state[e.actor]["alive"] = False
            touched.append(e.actor)
        elif e.kind == "summon":
            st = add(e.target, True)
            set_max(st, base_max(st["id"], st["side"]))  # joins an already-active synergy
            touched.append(e.target)
        elif e.kind in ("synergy_on", "synergy_off"):
            side, faction = e.actor.split(":", 1)
            (active[side].add if e.kind == "synergy_on" else active[side].discard)(faction)
            for label, st in state.items():
                if st["alive"] and st["side"] == side and protos[st["id"]].faction == faction:
                    set_max(st, base_max(st["id"], side))
                    touched.append(label)
        steps.append(
            [
                e.kind,
                e.actor,
                e.target,
                e.amount,
                [[lb, state[lb]["hp"], state[lb]["max"]] for lb in touched],
            ]
        )
    survivors = {
        s: [lb for lb, st in state.items() if st["alive"] and st["side"] == s] for s in "AB"
    }
    return {
        "kind": "monster",
        "front": rules.limits.front_line_size,
        "units": units,
        "steps": steps,
        "survivors": survivors,
    }


def fleet_visual(game: Any, a: Any, b: Any, events: list[Event]) -> tuple[dict, list[Event]]:
    """(visual, events without `status`): the status snapshots ride on the round's last line."""
    sides = {}
    for side, (classes, doctrine) in (("A", a), ("B", b)):
        cls, ships = [], []
        for k, (levels, count) in enumerate(classes):
            cls.append({"label": f"{count}x{''.join(map(str, levels))}", "hull": levels[0]})
            ships += [k] * count
        sides[side] = {"classes": cls, "ships": ships, "doctrine": list(doctrine)}
    shown: list[Event] = []
    steps: list[list[Any]] = []
    for e in events:
        if e.kind == "status":
            if steps:
                steps[-1][4][e.actor[0]] = e.target
            continue
        shown.append(e)
        steps.append([e.kind, e.actor, e.target, e.amount, {}])
    return {"kind": "fleet", "sides": sides, "steps": steps}, shown
