"""The protocol every game must implement, plus shared, JSON-friendly result types.

The engine imports only this module, never a concrete game.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Literal, Protocol, TypeVar

Winner = Literal["A", "B", "draw"]


@dataclass(slots=True)
class UnitStats:
    """Per-unit statistics for one battle."""

    label: str  # e.g. "A0:skeleton"; summoned units get the next free index
    unit_id: str
    side: Literal["A", "B"]
    summoned: bool = False
    damage_dealt: int = 0
    damage_taken: int = 0
    kills: int = 0
    healing: int = 0
    summons: int = 0
    survived: bool = False


@dataclass(slots=True)
class Event:
    """One entry of the optional battle log."""

    tick: int
    kind: Literal["attack", "dodge", "heal", "summon", "death", "synergy_on", "synergy_off"]
    actor: str
    target: str = ""
    amount: int = 0


@dataclass(slots=True)
class BattleResult:
    winner: Winner
    ticks: int
    survivors_a: list[str]
    survivors_b: list[str]
    stats: list[UnitStats]
    events: list[Event] | None = None


@dataclass(slots=True)
class MatchupResult:
    """Results of one design against one gauntlet opponent, over all seeds and both sides."""

    opponent: str
    wins: int = 0
    draws: int = 0
    losses: int = 0

    @property
    def games(self) -> int:
        return self.wins + self.draws + self.losses

    @property
    def score(self) -> float:
        return (self.wins + 0.5 * self.draws) / self.games if self.games else 0.0


@dataclass(slots=True)
class ScoreReport:
    score: float  # win rate in [0, 1], draw = 0.5
    battles: int
    matchups: list[MatchupResult] = field(default_factory=list)


D = TypeVar("D")


class Game(Protocol[D]):
    """What the engine needs from a game. `D` is the game's design type."""

    name: str
    ruleset_hash: str

    def random_design(self, rng: random.Random) -> D: ...

    def validate(self, design: D) -> list[str]:
        """Return every violated constraint; an empty list means valid."""
        ...

    def mutations(self, design: D, rng: random.Random) -> list[D]:
        """All valid one-step neighbours of `design`, in a seeded random order."""
        ...

    def simulate(self, a: D, b: D, seed: int, log: bool = False) -> BattleResult: ...

    def score(self, design: D) -> ScoreReport: ...

    def describe(self, design: D) -> str:
        """Compact text form of a design, for LLM prompts and the UI."""
        ...

    def describe_rules(self) -> str:
        """Compact text form of the rules, for LLM prompts."""
        ...
