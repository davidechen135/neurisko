# Requirements: Balance Report

## Introduction
The balance report is what a game designer actually gets from Neurisko. It answers four questions, and each answer rests on a measurement:

1. **What dominates?** Parts (units) that strong designs use far more often than random competitive designs do.
2. **Why does it work?** How much champions lose without it, and which high-worth heuristics keep adding it.
3. **What is never used?** Parts that random designs use but strong designs avoid.
4. **What should change?** Candidate stat changes, each verified by re-running the engine on the patched rules, with the before/after numbers.

Spec 2 showed that the engine does not out-search a hill-climb with a hall of fame (`docs/BASELINE.md`). So the report's value is that it measures, explains and verifies; it makes no claim of stronger search. Measurements before this spec (`docs/KIRO_NOTES.md`, 2026-10-30) showed that a single run, or a comparison without a random baseline, can mislead: our own Spec 1 named the wrong unit. The report must therefore always use several seeds, a random baseline and the spread across seeds.

## Glossary
- **Part**: a component of a design (a unit in Monster Mash). Games define it.
- **Share**: the fraction of a set of designs that contain a part.
- **Evolved share**: share in the top-k final designs of each detection run, averaged over runs.
- **Baseline share**: share in a large sample of random competitive designs.
- **Lift**: evolved share / baseline share.
- **Patch**: one numeric change to the ruleset, e.g. `witch.cost 2 → 3`.
- **Verification**: re-running the detection protocol on the patched ruleset.

## Requirements

### R1. Game protocol extension
1. The `Game` protocol SHALL add `parts(design) -> set[str]`, `part_names() -> list[str]`, `baseline_designs(rng, n) -> list[D]` (random designs a real player might field), `patch_candidates(part) -> list[Patch]` and `with_patch(patch) -> Game`.
2. A `Patch` SHALL be data: target part, field, old value, new value and a human-readable label.
3. `with_patch` SHALL return a game whose ruleset hash differs. IF a patch makes a fixed opponent invalid THEN that opponent SHALL be dropped and the drop reported, so the comparison stays honest.
4. Monster Mash SHALL offer, per unit: cost +1, the unit's main stat −20% (ATK, or HP for units with ATK ≤ 6), and ability magnitude −30% when the ability has a magnitude.

### R2. Detection
1. Detection SHALL run the engine (no LLM) on `seeds` different seeds, with the same config for all, in parallel processes.
2. For each part it SHALL report: evolved share (mean and min/max over seeds), baseline share, lift, and the number of runs whose champion contains the part.
3. A part SHALL be flagged **dominant** IF evolved share ≥ `dominant_share` (default 0.7) and lift ≥ `dominant_lift` (default 1.8).
4. A part SHALL be flagged **underused** IF evolved share ≤ `underused_share` (default 0.05) and baseline share ≥ 0.2.
5. Results SHALL be identical for the same ruleset, config and seeds, whatever the number of processes.

### R3. Explanation evidence
1. For each dominant part, the report SHALL give its **dependence**: the mean drop in score when it is replaced, in each champion that contains it, by the best affordable alternative.
2. It SHALL list up to 5 heuristics across detection runs, by final worth, whose action adds or keeps the part, with their worth, applications and improvement rate.
3. It SHALL list the matchups where champions containing the part gain the most over champions without it.

### R4. Fix verification
1. For each dominant part (up to `fix_parts`, default 2), every patch candidate SHALL be verified with `verify_seeds` seeds (default 6).
2. Per patch, the report SHALL give: the target's evolved share before and after, the most common part after the patch and its share, any part that becomes dominant, and the mean champion score on the held-out pool.
3. A patch SHALL be marked **effective** IF the target is no longer dominant, its share stays ≥ 0.1 (not made useless), and no other part becomes dominant. Otherwise the report SHALL say which condition failed.
4. Patches SHALL be ordered: effective ones first, then by how close the target's lift gets to 1.
5. IF no single patch is effective, and the best one failed only because another part became dominant, THEN the system SHALL apply that patch and verify the new dominant part's candidates on top of it (one follow-up step). The result SHALL show both changes. *(Added during implementation: on the default ruleset, every single witch patch either left witch dominant or made flesh_golem dominant.)*

### R5. Optional LLM summary
1. WHERE `--explain` is given, the system SHALL make one LLM call with the measured facts only, asking for a summary of at most 120 words.
2. Every number in the reply SHALL appear in the facts (after rounding as shown). IF any does not THEN the summary SHALL be discarded, the reason recorded and the template summary used.
3. The UI and the Markdown SHALL label the summary as LLM-written.

### R6. Artifacts
1. A report SHALL be written to `reports/<report_id>/report.json` (versioned schema) and `report.md`.
2. The report SHALL record the ruleset hash, the config, the seeds, the run time, and the engine config of the detection and verification runs.
3. The template summary SHALL be generated from the numbers alone and be readable without the LLM.

### R7. CLI
1. `neurisko report [--ruleset PATH] [--seeds 8] [--verify-seeds 6] [--generations 12] [--fix-parts 2] [--workers N] [--explain] [--report-id ID]` SHALL print progress and the summary, and write the artifacts.
2. With the defaults, a report on the default ruleset SHALL finish in under 5 minutes on the dev machine.

### R8. Acceptance on the default ruleset
1. On the default ruleset with default settings, the report SHALL flag witch as dominant and SHALL find at least one effective change for it (a single patch or a follow-up pair that starts with a witch patch). This is a `slow` test. If a future ruleset change breaks it, the test is updated to the new measured facts; it is not loosened to pass.
