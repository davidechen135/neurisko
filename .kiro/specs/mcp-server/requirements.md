# Requirements: Neurisko MCP Server

## Introduction
A game designer edits a ruleset file in Kiro and asks: "Is this balanced?" Kiro answers by calling Neurisko through MCP. It runs battles, scores teams, detects dominant units and verifies a proposed fix, all on the file the designer is editing. Kiro (the IDE's own model) writes the explanation from the measured numbers, so the MCP server itself never calls an LLM.

This is the most direct demonstration of Kiro in the product: steering tells Kiro when to use the tools, a hook offers a check on save, and MCP does the measuring.

## Constraints from Kiro's documentation (checked 2026-10-30)
- Workspace MCP servers are configured in `.kiro/settings/mcp.json`. Entries support `command`, `args`, `env`, `disabled`, `autoApprove` and `disabledTools`; there is no `cwd` field. Servers start with the first workspace folder as their working directory (kiro.dev/docs/mcp/configuration, kiro.dev/docs/ide/editor/multi-root-workspaces).
- The documented default per-call timeout is 120 s (`requestTimeout`, kiro.dev/docs/custom-agents/configuration-reference). It is not documented whether `mcp.json` honours it. A full balance report takes about 3 minutes, so long work must not depend on a long call.
- MCP progress notifications are not documented as shown. Prompts are supported and appear in the `#` menu (kiro.dev/docs/mcp/usage).
- Project `.env` files are not loaded automatically; the server loads its own settings.
- MCP Python SDK is 2.x (`mcp.server.mcpserver.MCPServer`; `FastMCP` was renamed).

## Requirements

### R1. Server and configuration
1. The package SHALL provide a stdio MCP server started with `uv run neurisko-mcp`.
2. The repository SHALL include `.kiro/settings/mcp.json` that registers it as `neurisko`.
3. The server SHALL NOT call an LLM, and SHALL NOT need network access.

### R2. Fast tools (each answers in under 60 s on the dev machine)
1. `check_ruleset(path)`: validate a ruleset file and return either its summary (hash, units, synergies, limits) or the validation errors with field paths.
2. `simulate_battle(path, team_a, team_b, seed)`: the result and a compact battle log.
3. `score_team(path, team)`: the gauntlet score and per-opponent results.
4. `quick_balance(path)`: detection only (4 seeds, 8 generations), returning shares, baseline, lift, ranges and flags as in the balance-report spec, labelled "quick" with its seed count.
5. `verify_patch(path, unit, field, new_value)`: verify one stat change (4 seeds) against the same seeds on the unpatched ruleset, and return before/after shares and the effective/failed verdict.

### R3. Full report as a job
1. `start_report(path)` SHALL start a full balance report in the background and return a job id immediately.
2. `report_status(job_id)` SHALL return the state (queued, running, done or failed), elapsed time, a progress description and, when done, the report summary plus the path of `report.md`.
3. Only one report job SHALL run at a time. A second start SHALL return the running job's id with a message, not an error.

### R4. Safety of inputs
1. `path` SHALL resolve to a `.toml` file inside the workspace root. Anything else SHALL be rejected with a clear message.
2. Teams, units and fields SHALL be validated against the ruleset; `new_value` must be a finite number within the field's own validation range.
3. Tools SHALL NOT modify ruleset files. Reports SHALL be written only under `reports/`.
4. Tool errors SHALL be returned as tool errors with the message, never as crashes of the server.

### R5. Kiro integration
1. A steering file `.kiro/steering/balance.md` with `inclusion: fileMatch` on `rulesets/**/*.toml` SHALL tell Kiro how to answer balance questions with these tools: measure before claiming, quote the numbers and seed counts, verify a fix before recommending it, and say plainly when a result is noisy.
2. An MCP prompt `balance_review(path)` SHALL be available from the `#` menu and run the quick check, propose up to 2 patches, verify them and summarise.
3. A hook on save of `rulesets/**/*.toml` SHALL ask Kiro to run `check_ruleset` and `quick_balance` on the saved file and report changes against the previous check.
4. `rulesets/monster-mash.toml` SHALL be a designer-editable copy of the default ruleset for the demo. The packaged default stays unchanged.
5. `autoApprove` SHALL list only the read-only fast tools (`check_ruleset`, `simulate_battle`, `score_team`). The CPU-heavy tools need approval.

### R6. Tests
1. Tests SHALL call the tools through the SDK's in-memory client, not just as Python functions.
2. Tests SHALL cover path rejection, invalid teams and patches, the job lifecycle (with a tiny config), and the one-job limit.
