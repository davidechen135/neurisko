"""Pool scoring shared by the evolution loop and the auditor."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from neurisko.engine.game import Game, weighted_score


def pool_score(game: Game, design: Any, hof: Sequence[Any], hof_weight: float) -> float:
    """Score against gauntlet + hall of fame, with the hall of fame weighted `hof_weight`."""
    return weighted_score(game.score(design, hof), len(hof), hof_weight)
