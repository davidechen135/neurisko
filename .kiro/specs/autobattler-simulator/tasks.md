# Tasks: Auto-battler Simulator ("Monster Mash")

- [x] 1. Tooling
  - Add dependencies: `pydantic` (runtime); `pytest`, `ruff` (dev group).
  - Configure ruff in `pyproject.toml`; create `tests/`.
  - Add Kiro hooks: ruff on save of `*.py`; full pytest after each spec task.
  - _Requirements: tech steering_

- [x] 2. Game protocol and result types
  - `src/neurisko/engine/game.py`: `Game` protocol, `BattleResult`, `UnitStats`, `ScoreReport`, `Event`.
  - _Requirements: R6.1, R3.4_

- [x] 3. Ruleset loading
  - [x] 3.1 Pydantic models with an `Ability` discriminated union; TOML loader; `RulesetError`; hash.
  - [x] 3.2 `data/autobattler/default.toml` with the 12 units, 4 synergies, limits and 6 archetypes from the design.
  - [x] 3.3 Tests: default loads, invalid cases rejected, hash stable and sensitive to changes.
  - _Requirements: R1.1–R1.4_

- [x] 4. Designs
  - [x] 4.1 `validate`, `random_design`, mutations (add/remove/replace/swap).
  - [x] 4.2 Tests: random and mutated designs are always valid across many seeds; all violations are reported.
  - _Requirements: R2.1–R2.4_

- [x] 5. Combat
  - [x] 5.1 Compile the ruleset into a fast representation; tick loop with idle-tick skipping and simultaneous resolution.
  - [x] 5.2 Abilities: lifesteal, dodge, first_strike, heal_lowest_ally, splash, ignore_armor, summon_on_ally_death.
  - [x] 5.3 Synergies, recomputed on spawn/death.
  - [x] 5.4 Per-unit stats and the optional event log.
  - [x] 5.5 Tests: determinism, side symmetry, draws, each ability, the intended-imbalance fixtures.
  - _Requirements: R3.1–R3.5_

- [x] 6. Gauntlet and scoring
  - [x] 6.1 Build the gauntlet from archetypes plus seeded random designs; `score()` with caching.
  - [x] 6.2 Tests: score in [0, 1], reproducible, draw counted as 0.5.
  - _Requirements: R4.1–R4.4_

- [x] 7. MonsterMash game class
  - Implement the `Game` protocol, including `describe` and `describe_rules`; check conformance in a test.
  - _Requirements: R6.2_

- [x] 8. Benchmark
  - `scripts/bench_autobattler.py`: battles/s and time per `score()`. Profile and optimize until ≥ 1,000 battles/s.
  - _Requirements: R5.1, R5.2_

- [x] 9. CLI
  - `neurisko battle` and `neurisko score` with `--seed`, `--ruleset`; readable terminal-style output.
  - _Requirements: R7.1–R7.3_

- [x] 10. Checkpoint
  - Full tests and ruff pass; update README milestone status; record notes on how Kiro helped (for the video and blog).
