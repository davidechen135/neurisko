"""Benchmark Monster Mash: battles per second and time per gauntlet score.

Run: uv run python scripts/bench_autobattler.py
Target (R5.2): >= 1,000 battles/s on one core.
"""

import random
import time

from neurisko.games.autobattler import MonsterMash

TARGET = 1_000


def main() -> None:
    game = MonsterMash()
    rng = random.Random(0)
    pairs = [(game.random_design(rng), game.random_design(rng)) for _ in range(5_000)]

    t = time.perf_counter()
    for i, (a, b) in enumerate(pairs):
        game.simulate(a, b, i)
    elapsed = time.perf_counter() - t
    rate = len(pairs) / elapsed

    designs = [game.random_design(rng) for _ in range(20)]
    t = time.perf_counter()
    for d in designs:
        game.score(d)
    per_score = (time.perf_counter() - t) / len(designs)

    battles_per_score = game.score(designs[0]).battles
    print(f"battles/s:        {rate:,.0f}  (target >= {TARGET:,})")
    print(f"score():          {per_score * 1000:.1f} ms  ({battles_per_score} battles)")
    print("PASS" if rate >= TARGET else "FAIL")


if __name__ == "__main__":
    main()
