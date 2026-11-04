"""TCS-lite combat: rounds of simultaneous fire.

Each round, every ship that can fire takes `shots` shots. Each shot targets a uniformly random
enemy ship that is not destroyed (disabled ships still draw fire). A shot hits unless the
target evades (drive) and does 1 damage unless armour deflects it. All damage is applied at
the end of the round; then ships that have taken half their hit points are disabled and ships
at full hit points are destroyed.

Era rules after each round: a fleet with `scuttle_disabled` (where allowed) removes its
disabled ships; then a fleet in which more than `max_disabled_fraction` of its remaining ships
are disabled withdraws. A fleet that withdraws or has no ship able to fire is out.
"""

from __future__ import annotations

import random

from neurisko.engine.game import BattleResult, Event, UnitStats
from neurisko.games.tcs_lite.fleet import Fleet, level_text
from neurisko.games.tcs_lite.rules import TcsRuleset

SIDES = ("A", "B")


class Compiled:
    def __init__(self, rules: TcsRuleset) -> None:
        c = rules.components
        self.hp = c.hull.hp
        self.shots = c.guns.shots
        self.deflect = c.armour.deflect
        self.evade = c.drive.evade
        self.max_rounds = rules.limits.max_rounds
        self.max_disabled = rules.era.max_disabled_fraction
        self.allow_scuttle = rules.era.allow_scuttle


class _Side:
    __slots__ = ("cls", "hp", "dmg", "shots", "hitp", "alive", "stats", "scuttle", "labels")

    def __init__(self, c: Compiled, fleet: Fleet, side: int) -> None:
        classes, doctrine = fleet
        self.cls: list[int] = []
        self.hp: list[int] = []
        self.shots: list[int] = []
        self.hitp: list[float] = []  # chance that a shot at this ship does damage
        self.stats: list[UnitStats] = []
        self.labels: list[str] = []
        for k, (levels, count) in enumerate(classes):
            h, a, g, d = levels
            label = f"{SIDES[side]}{k}:{count}x{level_text(levels)}"
            self.labels.append(label)
            self.stats.append(UnitStats(label, level_text(levels), SIDES[side]))
            for _ in range(count):
                self.cls.append(k)
                self.hp.append(c.hp[h])
                self.shots.append(c.shots[g])
                self.hitp.append((1 - c.evade[d]) * (1 - c.deflect[a]))
        self.dmg = [0] * len(self.cls)
        self.alive = list(range(len(self.cls)))  # not destroyed or scuttled
        self.scuttle = "scuttle_disabled" in doctrine and c.allow_scuttle

    def able(self) -> list[int]:
        return [i for i in self.alive if 2 * self.dmg[i] < self.hp[i]]


def simulate(c: Compiled, a: Fleet, b: Fleet, seed: int, log: bool = False) -> BattleResult:
    rng = random.Random(seed)
    rand = rng.random
    sides = (_Side(c, a, 0), _Side(c, b, 1))
    events: list[Event] | None = [] if log else None
    out = [False, False]
    rnd = 0
    while rnd < c.max_rounds:
        rnd += 1
        hits = ([0] * len(sides[0].cls), [0] * len(sides[1].cls))
        for s in (0, 1):
            me, foe = sides[s], sides[1 - s]
            targets = foe.alive
            nt = len(targets)
            if not nt:
                continue
            fired = landed = 0
            got = hits[1 - s]
            for i in me.able():
                for _ in range(me.shots[i]):
                    t = targets[int(rand() * nt)]
                    fired += 1
                    if rand() < foe.hitp[t]:
                        got[t] += 1
                        landed += 1
                        me.stats[me.cls[i]].damage_dealt += 1
            if events is not None and fired:
                events.append(
                    Event(rnd, "attack", f"{SIDES[s]}:fleet", f"{SIDES[1 - s]}:fleet", landed)
                )
        for s in (0, 1):
            me = sides[s]
            disabled_now = destroyed_now = 0
            keep = []
            for i in me.alive:
                h = hits[s][i]
                if h:
                    me.stats[me.cls[i]].damage_taken += h
                    was_able = 2 * me.dmg[i] < me.hp[i]
                    me.dmg[i] += h
                    if me.dmg[i] >= me.hp[i]:
                        destroyed_now += 1
                        continue
                    if was_able and 2 * me.dmg[i] >= me.hp[i]:
                        disabled_now += 1
                keep.append(i)
            me.alive = keep
            if events is not None:
                if disabled_now:
                    events.append(Event(rnd, "disabled", f"{SIDES[s]}:fleet", amount=disabled_now))
                if destroyed_now:
                    events.append(Event(rnd, "death", f"{SIDES[s]}:fleet", amount=destroyed_now))
            if me.scuttle:
                able = [i for i in me.alive if 2 * me.dmg[i] < me.hp[i]]
                gone = len(me.alive) - len(able)
                if gone:
                    me.alive = able
                    if events is not None:
                        events.append(Event(rnd, "scuttle", f"{SIDES[s]}:fleet", amount=gone))
        for s in (0, 1):
            me = sides[s]
            able = len(me.able())
            if able == 0:
                out[s] = True
            elif c.max_disabled < 1 and (len(me.alive) - able) > c.max_disabled * len(me.alive):
                out[s] = True
                if events is not None:
                    events.append(
                        Event(rnd, "withdraw", f"{SIDES[s]}:fleet", amount=len(me.alive) - able)
                    )
        if out[0] or out[1]:
            break
    winner = "draw" if out[0] == out[1] else ("B" if out[0] else "A")
    for s in (0, 1):
        me = sides[s]
        alive_cls = {me.cls[i] for i in me.alive}
        for k, st in enumerate(me.stats):
            st.survived = k in alive_cls
    surv = [
        [f"{sides[s].labels[k]}" for k in sorted({sides[s].cls[i] for i in sides[s].alive})]
        for s in (0, 1)
    ]
    return BattleResult(
        winner=winner,
        ticks=rnd,
        survivors_a=surv[0],
        survivors_b=surv[1],
        stats=sides[0].stats + sides[1].stats,
        events=events,
    )
