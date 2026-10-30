# Tasks: Eurisko Engine

- [ ] 1. Dependencies and settings
  - `uv add openai pydantic-settings`; `Settings` from `.env` with `SecretStr` key; register the `llm` pytest marker (skipped by default).
  - _Requirements: R6.3, R6.5_

- [ ] 2. Game protocol extension
  - [ ] 2.1 Add `score(extra_opponents)`, `feature_names`, `features`, `action_schema`, `apply_action`, `held_out` to the protocol.
  - [ ] 2.2 Implement them in Monster Mash; cache key includes the opponent-pool version.
  - [ ] 2.3 Tests: feature keys match names; every action result is valid or `None`; held-out gauntlet differs from the main one.
  - _Requirements: R1.1–R1.3_

- [ ] 3. Heuristic model and validation
  - [ ] 3.1 Pydantic models (`Condition`, `Origin`, `Stats`, `Heuristic`), `validate_heuristic`, condition evaluation.
  - [ ] 3.2 Seed heuristic file for Monster Mash and its loader.
  - [ ] 3.3 Tests: rejection messages; the seed set validates.
  - _Requirements: R2.1–R2.3_

- [ ] 4. Run recorder
  - JSONL event writer, `meta.json`, secret filtering; reader for replay.
  - _Requirements: R7.1_

- [ ] 5. Credit assignment and agenda
  - [ ] 5.1 Direct and lineage credit with logged contributions; clamping.
  - [ ] 5.2 Agenda priority with UCB bonus, seeded noise, per-heuristic cap, condition matching.
  - [ ] 5.3 Tests for both.
  - _Requirements: R3.2, R3.3, R4.1–R4.4_

- [ ] 6. Meta-heuristics M2–M5 (code-only)
  - Specialize, Generalize, Retarget, Clone; outputs validated; tests that each produces a valid, attributed heuristic.
  - _Requirements: R2.2, R4.2_

- [ ] 7. Evolution loop (no LLM)
  - [ ] 7.1 Population, hall of fame, generation loop, retirement, generation summary events.
  - [ ] 7.2 Determinism test; `--no-llm` 20-gen run under 60 s.
  - _Requirements: R3.1, R3.4, R8.3_

- [ ] 8. Auditor
  - [ ] 8.1 Replication, duplicate (behaviour signatures on probe designs), parasite checks; credit revocation; audit events.
  - [ ] 8.2 Tests for each check, plus the H59 demo test (M5 top 3 without the auditor, flagged with it).
  - _Requirements: R5.1–R5.5_

- [ ] 9. LLM Invent (M1)
  - [ ] 9.1 Client protocol, `OpenAICompatClient`, `ReplayClient`, `FakeClient`.
  - [ ] 9.2 Prompt builder from game vocabulary and evidence; per-item parsing; one retry with errors; budget enforcement; error handling.
  - [ ] 9.3 Tests with `FakeClient`; key-never-recorded test; optional live Ollama test.
  - _Requirements: R6.1–R6.5_

- [ ] 10. Replay
  - `--replay` re-executes a run using recorded LLM responses; test that generation events match.
  - _Requirements: R3.4, R7.2_

- [ ] 11. CLI `neurisko evolve`
  - Flags and terminal-style per-generation output; Ctrl-C writes `run_end`.
  - _Requirements: R8.1_

- [ ] 12. Baseline comparison
  - `scripts/compare_baseline.py`, equal battle budget, 5 seeds, held-out scoring; write `docs/BASELINE.md` with the actual result.
  - _Requirements: R8.2_

- [ ] 13. Checkpoint
  - Live run with local Qwen (20 gens); keep one good run in `runs/demo/`; tests and ruff pass; update README and `docs/KIRO_NOTES.md`.
