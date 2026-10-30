"""The agenda: which heuristic to apply to which design next.

priority = worth/1000 + rank_weight * design_rank + UCB exploration bonus + tiny seeded noise
"""

from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import dataclass
from typing import Any

from neurisko.engine.game import Game
from neurisko.engine.heuristics import Heuristic


@dataclass(slots=True)
class Task:
    heuristic: Heuristic
    parent: Any
    child: Any
    priority: float


def ucb(applications: int, total: int, c: float) -> float:
    return c * math.sqrt(math.log(1 + total) / (1 + applications))


def design_tasks(
    heuristics: list[Heuristic],
    population: list[tuple[Any, dict[str, float]]],
    game: Game,
    rng: random.Random,
    n: int,
    per_heuristic_cap: int,
    ucb_c: float,
    total_applications: int,
    rank_weight: float = 0.5,
    explored: set[Any] | None = None,
) -> tuple[list[Task], set[str]]:
    """Up to `n` tasks, plus the ids of heuristics that had at least one candidate.

    `population` is (design, features), best design first. Transitions in `explored`
    transitions (parent, child) already evaluated earlier are skipped, so the same move cannot be
    credited twice.
    """
    explored = explored or set()
    size = len(population)
    candidates: list[Task] = []
    for h in heuristics:
        if not h.alive or h.level != "design":
            continue
        bonus = h.worth / 1000 + ucb(h.stats.applications, total_applications, ucb_c)
        seen: set[Any] = set()
        for rank, (design, feats) in enumerate(population):
            if not h.matches(feats):
                continue
            child = game.apply_action(design, h.action, rng)
            if child is None or child in seen or (design, child) in explored:
                continue
            seen.add(child)
            rank_score = 1 - rank / (size - 1) if size > 1 else 1.0
            prio = bonus + rank_weight * rank_score + rng.random() * 0.01
            candidates.append(Task(h, design, child, prio))
    active = {t.heuristic.id for t in candidates}
    candidates.sort(key=lambda t: t.priority, reverse=True)
    chosen: list[Task] = []
    per: Counter[str] = Counter()
    for t in candidates:
        if per[t.heuristic.id] < per_heuristic_cap:
            chosen.append(t)
            per[t.heuristic.id] += 1
            if len(chosen) == n:
                break
    return chosen, active


def meta_tasks(
    metas: list[Heuristic],
    rng: random.Random,
    n: int,
    ucb_c: float,
    total_runs: int,
) -> list[Heuristic]:
    """Up to `n` distinct meta-heuristics, by worth plus exploration bonus."""
    scored = [
        (m.worth / 1000 + ucb(m.stats.applications, total_runs, ucb_c) + rng.random() * 0.01, m)
        for m in metas
        if m.alive
    ]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [m for _, m in scored[:n]]
