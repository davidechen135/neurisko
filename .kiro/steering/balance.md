---
inclusion: fileMatch
fileMatchPattern: "rulesets/**/*.toml"
---

# Answering balance questions about a ruleset

The `neurisko` MCP server measures balance by simulation. When the designer asks about balance, strength, counters or fixes for a ruleset file:

- **Measure, don't guess.** Use the tools instead of judging from the numbers in the file. Start with `check_ruleset`, then `quick_balance` for "is this balanced?".
- **Quote numbers with their context**: a unit's share in strong teams *and* in random teams (the baseline), the range across runs, and the seed count. `quick_balance` uses 4 seeds; shares around 0.5 are noisy at that size, so say so.
- **Verify before recommending.** Propose single-stat changes, run `verify_patch` on each, and recommend only changes it marks `effective`. If none are, report what failed (still dominant, made useless, or another unit became dominant) and suggest a full report.
- **Full report**: `start_report`, then `report_status` every 20–30 s until `done` (about 2 minutes); link the `report_md` path.
- **Never edit the ruleset unless asked.** If the designer asks you to apply a change, edit only that value, then run `check_ruleset` and `quick_balance` again and compare with the previous result.
- Known result for the default rules (8-seed report, `reports/demo/default/report.md`): witch is dominant (0.95 of strong teams vs 0.31 of random); the single changes tested on witch were not enough on their own, and `witch.cost 2→3 + flesh_golem.atk 10→8` was effective. Re-measure rather than repeat this if the file has changed.
