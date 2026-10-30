"""The protocol every game must implement, plus shared, JSON-friendly result types.

The engine imports only this module, never a concrete game.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, TypeVar

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


def weighted_score(report: ScoreReport, n_extra: int, extra_weight: float) -> float:
    """Blend of the win rate against the gauntlet and against the last `n_extra` opponents.

    Without this, a hall of fame of 12 is only a third of a 36-opponent pool, and strong
    designs saturate at 1.0 against the weak fixed gauntlet.
    """
    if n_extra == 0 or not report.matchups:
        return report.score
    base, extra = report.matchups[:-n_extra], report.matchups[-n_extra:]

    def rate(ms: list[MatchupResult]) -> float:
        games = sum(m.games for m in ms)
        return sum(m.wins + 0.5 * m.draws for m in ms) / games if games else 0.0

    return (1 - extra_weight) * rate(base) + extra_weight * rate(extra)


D = TypeVar("D")

# A game-agnostic action: {"kind": ..., <param>: <value>, ...}. All values are strings.
Action = dict[str, str]
# kind -> param -> allowed values
ActionSchema = dict[str, dict[str, list[str]]]


class Game(Protocol[D]):
    """What the engine needs from a game. `D` is the game's design type (hashable)."""

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

    def score(self, design: D, extra_opponents: Sequence[D] = ()) -> ScoreReport:
        """Win rate against the fixed gauntlet plus `extra_opponents` (e.g. a hall of fame).

        Matchups for the extra opponents must come last, in the order given.
        """
        ...

    def feature_names(self) -> list[str]:
        """Names usable in heuristic conditions."""
        ...

    def features(self, design: D, report: ScoreReport) -> dict[str, float]:
        """Feature values of `design`; `report` is its score against the current pool."""
        ...

    def action_schema(self) -> ActionSchema: ...

    def apply_action(self, design: D, action: Action, rng: random.Random) -> D | None:
        """The resulting valid design, or None if the action does not apply or changes nothing."""
        ...

    def held_out(self) -> Game[D]:
        """Same rules, but a gauntlet and battle seeds the engine never optimises against."""
        ...

    def to_json(self, design: D) -> Any:
        """JSON-serialisable form of a design, for run records."""
        ...

    def describe(self, design: D) -> str:
        """Compact text form of a design, for LLM prompts and the UI."""
        ...

    def describe_rules(self) -> str:
        """Compact text form of the rules, for LLM prompts."""
        ...
