# Tasks: Balance Report

- [x] 1. Protocol and patches
  - [x] 1.1 Add `parts`, `part_names`, `baseline_designs`, `patch_candidates`, `with_patch` to the `Game` protocol; `Patch` model.
  - [x] 1.2 Monster Mash implementation (`patches.py`), including dropped-opponent reporting.
  - [x] 1.3 Tests for candidates, hash change, dropped archetypes, multiplier floor.
  - _Requirements: R1.1–R1.4_

- [x] 2. Batch runner and shares
  - [x] 2.1 `RunSpec`/`RunOutcome`, `run_batch` with process pool and in-process mode.
  - [x] 2.2 Share table, lift, champion counts, dominant/underused flags.
  - [x] 2.3 Tests: worker-count independence; flags from hand-built outcomes.
  - _Requirements: R2.1–R2.5_

- [x] 3. Explanation evidence
  - Dependence ablation, evidence heuristics, matchup gains; tests.
  - _Requirements: R3.1–R3.3_

- [x] 4. Verification
  - Patch verification on matched seeds, effectiveness rule with failure reasons, ordering; tests.
  - _Requirements: R4.1–R4.4_

- [x] 5. Summaries
  - Template summary; optional LLM summary with the number check and rejection event; tests with `FakeClient`.
  - _Requirements: R5.1–R5.3, R6.3_

- [x] 6. Artifacts and CLI
  - `report.json` schema model, `report.md` renderer, `neurisko report` with progress output; gitignore `reports/*` except `reports/demo/`.
  - _Requirements: R6.1, R6.2, R7.1_

- [x] 7. Acceptance and demo report
  - Slow acceptance test (R8); generate `reports/demo/default` with `--explain` on local Qwen; check the 5-minute budget (R7.2).
  - _Requirements: R7.2, R8.1_

- [x] 8. Checkpoint
  - Tests and ruff pass; README and `docs/KIRO_NOTES.md` updated.
