"""Deterministic tick-based combat.

Rules (see design.md):
- Each unit acts when its cooldown reaches 0, then waits `speed` ticks.
- Melee units act only from the front line; ranged units act from anywhere.
- Every unit targets the frontmost living enemy.
- All actions in a tick read the state at the start of the tick and are applied together,
  then deaths, summons and synergy changes are resolved.
- Dodge is the only random element and uses a seeded RNG.

The ruleset is compiled once into plain slotted objects; no pydantic in the hot loop.
"""

from __future__ import annotations

import random
from collections import Counter

from neurisko.engine.game import BattleResult, Event, UnitStats
from neurisko.games.autobattler.design import Design
from neurisko.games.autobattler.rules import (
    Dodge,
    FirstStrike,
    HealLowestAlly,
    IgnoreArmor,
    Lifesteal,
    Ruleset,
    Splash,
    SummonOnAllyDeath,
)

SIDES = ("A", "B")


class _Proto:
    __slots__ = (
        "id",
        "faction",
        "hp",
        "atk",
        "armor",
        "speed",
        "ranged",
        "lifesteal",
        "dodge",
        "first_strike",
        "heal",
        "splash",
        "ignore_armor",
        "summon_unit",
        "summon_max",
    )

    def __init__(self, u) -> None:
        self.id = u.id
        self.faction = u.faction
        self.hp = u.hp
        self.atk = u.atk
        self.armor = u.armor
        self.speed = u.speed
        self.ranged = u.range == "ranged"
        ab = u.ability
        self.lifesteal = ab.fraction if isinstance(ab, Lifesteal) else 0.0
        self.dodge = ab.chance if isinstance(ab, Dodge) else 0.0
        self.first_strike = ab.multiplier if isinstance(ab, FirstStrike) else 0.0
        self.heal = ab.amount if isinstance(ab, HealLowestAlly) else 0
        self.splash = ab.fraction if isinstance(ab, Splash) else 0.0
        self.ignore_armor = isinstance(ab, IgnoreArmor)
        self.summon_unit = ab.unit if isinstance(ab, SummonOnAllyDeath) else None
        self.summon_max = ab.max if isinstance(ab, SummonOnAllyDeath) else 0


class _Syn:
    __slots__ = ("threshold", "hp_pct", "atk_pct", "armor_flat", "ability_pct")

    def __init__(self, s) -> None:
        self.threshold = s.threshold
        self.hp_pct = s.hp_pct
        self.atk_pct = s.atk_pct
        self.armor_flat = s.armor_flat
        self.ability_pct = s.ability_pct


class _Fighter:
    __slots__ = (
        "p",
        "side",
        "label",
        "stats",
        "hp",
        "max_hp",
        "atk",
        "armor",
        "ab_mult",
        "cd",
        "alive",
        "struck",
        "summons_left",
    )

    def __init__(self, p: _Proto, side: int, index: int, summoned: bool = False) -> None:
        self.p = p
        self.side = side
        self.label = f"{SIDES[side]}{index}:{p.id}"
        self.stats = UnitStats(self.label, p.id, SIDES[side], summoned=summoned)
        self.hp = p.hp
        self.max_hp = p.hp
        self.atk = p.atk
        self.armor = p.armor
        self.ab_mult = 1.0
        self.cd = p.speed
        self.alive = True
        self.struck = False
        self.summons_left = p.summon_max


class CompiledRules:
    """Fast, read-only view of a ruleset for the combat loop."""

    def __init__(self, rules: Ruleset) -> None:
        self.protos = {u.id: _Proto(u) for u in rules.units}
        self.syn = {s.faction: _Syn(s) for s in rules.synergies}
        self.max_ticks = rules.limits.max_ticks
        self.front = rules.limits.front_line_size


def _apply_synergies(
    c: CompiledRules, team: list[_Fighter], active: set[str], tick: int, events, side: int
) -> None:
    counts = Counter(f.p.faction for f in team if f.alive)
    for faction, s in c.syn.items():
        on = counts[faction] >= s.threshold
        if on != (faction in active):
            if on:
                active.add(faction)
            else:
                active.discard(faction)
            if events is not None:
                kind = "synergy_on" if on else "synergy_off"
                events.append(Event(tick, kind, f"{SIDES[side]}:{faction}"))
    for f in team:
        if not f.alive:
            continue
        p = f.p
        s = c.syn.get(p.faction)
        if s is not None and p.faction in active:
            f.atk = round(p.atk * (1 + s.atk_pct))
            f.armor = p.armor + s.armor_flat
            f.ab_mult = 1 + s.ability_pct
            new_max = round(p.hp * (1 + s.hp_pct))
        else:
            f.atk, f.armor, f.ab_mult, new_max = p.atk, p.armor, 1.0, p.hp
        if new_max != f.max_hp:
            delta = new_max - f.max_hp
            f.max_hp = new_max
            f.hp = f.hp + delta if delta > 0 else min(f.hp, new_max)


def simulate(c: CompiledRules, a: Design, b: Design, seed: int, log: bool = False) -> BattleResult:
    rng = random.Random(seed)
    events: list[Event] | None = [] if log else None
    teams = (
        [_Fighter(c.protos[u], 0, i) for i, u in enumerate(a)],
        [_Fighter(c.protos[u], 1, i) for i, u in enumerate(b)],
    )
    everyone = teams[0] + teams[1]  # grows with summons; keeps stats for the result
    next_index = [len(a), len(b)]
    active: tuple[set[str], set[str]] = (set(), set())
    for side in (0, 1):
        _apply_synergies(c, teams[side], active[side], 0, events, side)

    tick = 0
    winner = "draw"
    front_size = c.front
    while True:
        # Who may act this step: ranged anywhere, melee only in the front line.
        actable: list[_Fighter] = []
        for team in teams:
            pos = 0
            for f in team:
                if f.alive:
                    if f.p.ranged or pos < front_size:
                        actable.append(f)
                    pos += 1
        dt = max(1, min(f.cd for f in actable))
        if tick + dt > c.max_ticks:
            tick = c.max_ticks
            break
        tick += dt
        for f in everyone:
            if f.alive:
                f.cd = f.cd - dt if f.cd > dt else 0

        # Plan all actions from the start-of-tick state.
        hits: list[tuple[_Fighter, _Fighter, float, bool]] = []
        heals: list[tuple[_Fighter, _Fighter, int]] = []
        for f in actable:
            if f.cd:
                continue
            p = f.p
            f.cd = p.speed
            enemies = [e for e in teams[1 - f.side] if e.alive]
            target = enemies[0]
            raw = float(f.atk)
            if p.first_strike and not f.struck:
                raw *= p.first_strike
                f.struck = True
            hits.append((f, target, raw, p.ignore_armor))
            if p.splash and len(enemies) > 1:
                hits.append((f, enemies[1], f.atk * p.splash * f.ab_mult, p.ignore_armor))
            if p.heal:
                ally = min((x for x in teams[f.side] if x.alive), key=lambda x: x.hp / x.max_hp)
                heals.append((f, ally, round(p.heal * f.ab_mult)))

        # Apply hits together.
        credit: dict[_Fighter, dict[_Fighter, int]] = {}
        for f, t, raw, ignore in hits:
            if t.p.dodge and rng.random() < t.p.dodge:
                if events is not None:
                    events.append(Event(tick, "dodge", t.label, f.label))
                continue
            dmg = max(1, round(raw) - (0 if ignore else t.armor))
            applied = min(dmg, t.hp) if t.hp > 0 else 0
            t.hp -= dmg
            f.stats.damage_dealt += applied
            t.stats.damage_taken += applied
            by = credit.setdefault(t, {})
            by[f] = by.get(f, 0) + applied
            if f.p.lifesteal and applied:
                heals.append((f, f, round(applied * f.p.lifesteal)))
            if events is not None:
                events.append(Event(tick, "attack", f.label, t.label, dmg))

        # Heals land only on units that survived this tick's damage.
        for healer, t, amount in heals:
            if t.hp > 0:
                real = min(amount, t.max_hp - t.hp)
                if real > 0:
                    t.hp += real
                    healer.stats.healing += real
                    if events is not None:
                        events.append(Event(tick, "heal", healer.label, t.label, real))

        # Deaths, kill credit, summons.
        dead = [f for f in everyone if f.alive and f.hp <= 0]
        if dead:
            for f in dead:
                f.alive = False
                by = credit.get(f)
                if by:
                    max(by, key=by.__getitem__).stats.kills += 1
                if events is not None:
                    events.append(Event(tick, "death", f.label))
            for f in dead:
                team = teams[f.side]
                for n in list(team):
                    if n.alive and n.summons_left and n.p.summon_unit:
                        n.summons_left -= 1
                        n.stats.summons += 1
                        new = _Fighter(
                            c.protos[n.p.summon_unit], n.side, next_index[n.side], summoned=True
                        )
                        next_index[n.side] += 1
                        team.append(new)
                        everyone.append(new)
                        if events is not None:
                            events.append(Event(tick, "summon", n.label, new.label))
            for side in {f.side for f in dead}:
                _apply_synergies(c, teams[side], active[side], tick, events, side)

        a_alive = any(f.alive for f in teams[0])
        b_alive = any(f.alive for f in teams[1])
        if not (a_alive and b_alive):
            winner = "A" if a_alive else "B" if b_alive else "draw"
            break

    for f in everyone:
        f.stats.survived = f.alive
    return BattleResult(
        winner=winner,
        ticks=tick,
        survivors_a=[f.label for f in teams[0] if f.alive],
        survivors_b=[f.label for f in teams[1] if f.alive],
        stats=[f.stats for f in everyone],
        events=events,
    )
