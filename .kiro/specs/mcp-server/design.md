# Design: Neurisko MCP Server

## The demo this enables
1. The designer opens `rulesets/monster-mash.toml` in Kiro. The `balance.md` steering file is now active.
2. They ask: "Is this ruleset balanced?" Kiro calls `quick_balance` and replies: witch is in about 0.9 of strong teams against 0.32 of random teams, over 4 seeds.
3. "What should I change?" Kiro proposes `witch.cost 2 → 3`, calls `verify_patch` and shows that the share drops to about 0.45 and that nothing else becomes dominant.
4. The designer edits the cost and saves. The hook asks Kiro to re-check. Kiro calls `check_ruleset` and `quick_balance` and reports that flesh_golem is now the most common unit and is not dominant.
5. "Write me the full report" calls `start_report`, then `report_status` until it is done, and links `reports/<id>/report.md`.

## Layout
```
src/neurisko/mcp/
  server.py     # MCPServer("neurisko"), tool and prompt registration, main()
  tools.py      # plain functions with the logic; easy to unit test
  jobs.py       # one background report job at a time
  paths.py      # workspace path validation
rulesets/monster-mash.toml          # copy of the packaged default
.kiro/settings/mcp.json
.kiro/steering/balance.md           # inclusion: fileMatch, fileMatchPattern: rulesets/**/*.toml
.kiro/hooks/balance-on-save.json    # PostFileSave, matcher rulesets/.*\.toml$, agent action
```
`pyproject.toml`: add `mcp>=2.3,<3` and the script `neurisko-mcp = "neurisko.mcp.server:main"`.

## Tools
All tools are sync `def` handlers. MCP SDK 2.x runs sync handlers on a worker thread, so CPU work does not block the protocol loop. Return values are pydantic models, so clients get both structured content and text.

| tool | cost | notes |
|---|---|---|
| `check_ruleset(path)` | ms | `RulesetError` text is returned as the error |
| `simulate_battle(path, team_a, team_b, seed=0)` | ms | log limited to 200 lines, plus `truncated: true` |
| `score_team(path, team)` | ~20 ms | |
| `quick_balance(path)` | ~15–25 s | `run_batch` 4 seeds × 8 gens, `workers = min(4, cpu)` |
| `verify_patch(path, unit, field, new_value)` | ~15–25 s | the "before" numbers reuse the same 4 seeds (cached per ruleset hash) |
| `start_report(path)` / `report_status(job_id)` | instant | |

Teams are lists of unit ids (front first). `field` is one of `cost`, `atk`, `hp`, `armor`, `speed` or `ability.<param>`, and goes through the balance-report spec's `Patch` and `with_patch`, so ruleset validation applies to the new value.

The quick timings are estimates from Spec 3 measurements (one 12-generation run takes about 20 s; runs in parallel take about as long as one). They are checked in task 6, and the seed/generation counts are lowered if a call exceeds 60 s.

## Path validation (paths.py)
```python
def resolve_ruleset(path: str) -> Path:
    root = Path.cwd().resolve()          # Kiro starts the server in the workspace root
    p = (root / path).resolve()          # absolute input paths resolve as given
    if p.suffix != ".toml" or not p.is_relative_to(root) or not p.is_file(): raise ToolError(...)
```
The workspace root can be overridden with `NEURISKO_WORKSPACE` for tests.

## Jobs (jobs.py)
A single `ReportJob` with a lock. `start` launches a thread that calls `build_report(...)` with a progress callback storing the latest stage ("detect 5/8", "verify witch cost 2→3 3/6"). State lives in memory only. If the server restarts, the job is gone; `report_status` returns "unknown job" and `start_report` can be called again. Finished reports are on disk under `reports/`.

## Prompt
`balance_review(path)` returns a user message that asks Kiro to: call `check_ruleset`; call `quick_balance`; for each dominant unit, propose at most 2 single-stat patches and `verify_patch` each; then summarise with the numbers and seed counts, recommending only verified patches.

## Steering (`.kiro/steering/balance.md`)
Front matter: `inclusion: fileMatch` and `fileMatchPattern: "rulesets/**/*.toml"`. Content (short):
- Answer balance questions with the neurisko tools; do not judge balance from reading the numbers alone.
- Quote shares with their baseline and seed count; "quick" results use 4 seeds and can be noisy for shares around 0.5.
- Recommend a stat change only after `verify_patch` marks it effective; otherwise report what failed.
- Never edit the ruleset unless the designer asks.

## Hook (`balance-on-save`)
PostFileSave, matcher `rulesets/.*\.toml$`, agent action: "The designer saved a ruleset. Run neurisko `check_ruleset` on it; if valid, run `quick_balance` and compare with the last result in this conversation. Report in at most 5 lines." Created with the `createHook` tool. The README tells designers how to delete it if checks on every save are too noisy.

## mcp.json
```json
{"mcpServers": {"neurisko": {
  "command": "uv", "args": ["run", "neurisko-mcp"],
  "disabled": false,
  "autoApprove": ["check_ruleset", "simulate_battle", "score_team"]}}}
```
Kiro's docs show both bare and prefixed tool names in `autoApprove` examples. Task 7 checks which form the MCP panel uses and fixes the list.

## Testing strategy
- `tests/mcp/test_tools.py`: the plain functions — path rejection (`../x.toml`, `/etc/hosts`, a `.py` file), invalid team and patch messages, battle log truncation.
- `tests/mcp/test_server.py`: SDK in-memory client; lists the 7 tools and the prompt; calls `check_ruleset` and `score_team`; error result for a bad path.
- `tests/mcp/test_jobs.py`: job lifecycle with a tiny report config; a second start returns the same job id.
- `quick_balance` and `verify_patch` on the real ruleset are `slow` tests that also check the 60 s budget.

## Implementation notes (2026-10-31)
1. **Measured timings** (12-core M4 Pro, real settings): `quick_balance` 16.7 s, `verify_patch` 14.9 s; the slow test with a cold cache: both together 32 s. Well under the 60 s budget and Kiro's 120 s default.
2. **Caches.** Games are cached by ruleset hash (keeps score caches); `quick_balance` results too, so `verify_patch` reuses the "before" runs and a repeated quick check is instant. Editing the file changes the hash, so stale results are never reused.
3. **Invalid archetypes.** A designer's edit (e.g. a lower budget) can make a built-in archetype opponent invalid, which used to make the game fail to load. The tools now drop those opponents and report them (`dropped_archetypes`), using the same helper as patch verification.
4. **Quick results differ from the full report**, as expected at 4 seeds and 8 generations: `witch.cost 2→3` gives witch 0.90 → 0.70 (still dominant, flesh_golem becomes dominant), while the 6-seed, 12-generation report gives 0.93 → 0.40. Tool notes and steering tell Kiro that quick results are noisy and to use the full report before recommending.
5. **`mcp.json` could not be written by the agent**: `.kiro/settings/` is protected by a Kiro permission rule. The intended file is `docs/kiro-mcp.json`; the user copies it.
6. **`autoApprove`** lists the read-only fast tools plus `report_status` (it only reads job state). `quick_balance`, `verify_patch` and `start_report` use several CPU cores and still ask.
7. **Tests** go through the SDK's in-memory `Client` and through the real `neurisko-mcp` process over stdio.
