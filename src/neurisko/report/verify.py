"""Verify patches by re-running detection on each patched ruleset with the same seeds.

All patches of one part run as one parallel batch, so every core is busy.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence

from neurisko.engine.evolve import EvolveConfig
from neurisko.engine.game import Game, Patch
from neurisko.engine.heuristics import RuleSpec
from neurisko.report.detect import (
    RunOutcome,
    Thresholds,
    baseline_shares,
    make_specs,
    run_batch,
    share_table,
)
from neurisko.report.schema import PartStat, PatchResult

MIN_TARGET_SHARE = 0.1


def _row(table: list[PartStat], part: str) -> PartStat:
    return next(r for r in table if r.part == part)


def judge(
    target: str, after: list[PartStat], min_share: float = MIN_TARGET_SHARE
) -> tuple[bool, list[str], list[str]]:
    """(effective, failed conditions, other parts that became dominant)."""
    row = _row(after, target)
    failed = []
    if "dominant" in row.flags:
        failed.append(f"{target} is still dominant (share {row.evolved:.2f}, lift {row.lift:.1f})")
    if row.evolved < min_share:
        failed.append(f"{target} is now barely used (share {row.evolved:.2f} < {min_share})")
    new_dom = [r.part for r in after if r.part != target and "dominant" in r.flags]
    if new_dom:
        failed.append(f"new dominant: {', '.join(new_dom)}")
    return not failed, failed, new_dom


def verify_patches(
    game: Game,
    patches: Sequence[Patch],
    before_outcomes: Sequence[RunOutcome],
    seeds: Sequence[int],
    config: EvolveConfig,
    seed_rules: list[RuleSpec],
    th: Thresholds,
    top_k: int,
    baseline_n: int,
    workers: int | None,
    on_done: Callable[[RunOutcome, int, int], None] | None = None,
    base_patches: Sequence[Patch] = (),
) -> tuple[list[PatchResult], dict[str, list[RunOutcome]]]:
    """Verify each patch on `game`. `game` may already include `base_patches` (step 2).

    Returns the results and each patch's outcomes keyed by its change text.
    """
    t = time.perf_counter()
    games = {}
    specs = []
    prefix = "".join(p.text() + " + " for p in base_patches)
    for patch in patches:
        patched, dropped = game.with_patch(patch)
        tag = prefix + patch.text()
        games[tag] = (patch, patched, dropped)
        specs += make_specs(patched, seeds, config, seed_rules, top_k, tag=tag)
    outcomes = run_batch(specs, workers, on_done)
    seconds = round(time.perf_counter() - t, 1)

    seed_set = set(seeds)
    before = share_table(
        game,
        [o for o in before_outcomes if o.seed in seed_set],
        baseline_shares(game, baseline_n),
        th,
    )
    results = []
    for tag, (patch, patched, dropped) in games.items():
        mine = [o for o in outcomes if o.tag == tag]
        after = share_table(patched, mine, baseline_shares(patched, baseline_n), th)
        effective, failed, new_dom = judge(patch.target, after)
        held = patched.held_out()
        champ = [held.score(patched.from_json(o.champion)).score for o in mine]
        target_after = _row(after, patch.target)
        results.append(
            PatchResult(
                patch=patch,
                base_patches=list(base_patches),
                before=before,
                after=after,
                target_before=_row(before, patch.target).evolved,
                target_after=target_after.evolved,
                target_lift_after=target_after.lift,
                top_after=after[0].part,
                top_after_share=after[0].evolved,
                new_dominant=new_dom,
                champion_held_out=round(sum(champ) / len(champ), 4),
                effective=effective,
                failed=failed,
                dropped_opponents=dropped,
                seconds=seconds,
            )
        )
    by_tag = {tag: [o for o in outcomes if o.tag == tag] for tag in games}
    return results, by_tag


def needs_follow_up(results: list[PatchResult]) -> PatchResult | None:
    """The best single patch if it failed only because another part became dominant."""
    if not results or any(r.effective for r in results):
        return None
    best = order(results)[0]
    target_ok = all("new dominant" in f for f in best.failed)
    return best if target_ok and best.new_dominant else None


def order(results: list[PatchResult]) -> list[PatchResult]:
    """Effective first, then by how close the target's lift is to 1."""
    return sorted(results, key=lambda r: (not r.effective, abs(r.target_lift_after - 1)))
