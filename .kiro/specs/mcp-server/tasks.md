# Tasks: Neurisko MCP Server

Depends on the balance-report spec (`run_batch`, `Patch`, `with_patch`, `build_report`).

- [x] 1. Dependency and entry point
  - `uv add "mcp>=2.3,<3"`; `neurisko-mcp` script; `MCPServer("neurisko")` skeleton that starts over stdio.
  - _Requirements: R1.1, R1.3_

- [x] 2. Path validation and fast tools
  - `paths.py`; `check_ruleset`, `simulate_battle`, `score_team`; unit tests.
  - _Requirements: R2.1–R2.3, R4.1, R4.2, R4.4_

- [x] 3. Quick balance and patch verification
  - `quick_balance`, `verify_patch` with before-results cached per ruleset hash; slow tests for the 60 s budget.
  - _Requirements: R2.4, R2.5_

- [x] 4. Report jobs
  - `start_report`, `report_status`, one-job limit, progress stages; tests.
  - _Requirements: R3.1–R3.3, R4.3_

- [x] 5. Prompt and in-memory server tests
  - `balance_review` prompt; SDK in-memory client tests.
  - _Requirements: R5.2, R6.1, R6.2_

- [x] 6. Kiro configuration
  - [x] `rulesets/monster-mash.toml`, `.kiro/steering/balance.md`, `balance-on-save` hook, `docs/kiro-mcp.json`.
  - [x] `.kiro/settings/mcp.json` (protected path: created by the user from `docs/kiro-mcp.json`); `.kiro/steering/balance.md`; `balance-on-save` hook via `createHook`; check tool-name form for `autoApprove` in the MCP panel.
  - _Requirements: R1.2, R5.1, R5.3–R5.5_

- [x] 7. End-to-end check in Kiro (2026-11-01; see docs/KIRO_NOTES.md: works, and exposed a quick-check false positive)
  - Run the 5-step demo from the design in a Kiro chat; record timings and any tool-call timeouts in `docs/KIRO_NOTES.md`; adjust quick seed/generation counts if needed.

- [x] 8. Checkpoint
  - Tests and ruff pass; README section on using Neurisko from Kiro.
