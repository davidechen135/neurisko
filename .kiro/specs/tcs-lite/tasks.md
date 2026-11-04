# Tasks: TCS-lite

- [ ] 1. Rules and combat prototype
  - Ruleset model, `tcs-1981.toml` / `tcs-1982.toml`, fleet cost and validation, combat with withdrawal and scuttling; benchmark (≥ 2,000 battles/s).
  - Quick measurement before building the rest: does a swarm beat the archetypes under 1981 rules, and lose under 1982 rules without scuttling? Tune numbers and record every step in the design notes.
  - _Requirements: R1, R2, R3_

- [ ] 2. Engine generality
  - Registry with both games, `--game` flag, game recorded in run/report metadata, replay by game, protocol additions (`seed_rules`, `featured_opponents`, `describe_event`), `Patch` with `target="rules"`; parametrise the protocol conformance test.
  - _Requirements: R5_

- [ ] 3. TCS-lite game class
  - Features, actions, parts, baseline designs, patch candidates, held-out, seed heuristics.
  - _Requirements: R4, R6_

- [ ] 4. Story acceptance
  - Slow tests for R7.1 and R7.2; tune and record if they fail.
  - _Requirements: R7_

- [ ] 5. Demo runs and web view
  - Record `runs/demo/tcs-1981` and `tcs-1982`; TCS tab in the console with the era diff, the notice line and both runs; export and Pages data.
  - _Requirements: R5.3, R8_

- [ ] 6. Checkpoint
  - Tests and ruff pass; README, docs/KIRO_NOTES.md updated; historical text checked against the Gladwell article before it goes in the video.
