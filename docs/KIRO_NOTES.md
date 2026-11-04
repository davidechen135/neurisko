# Kiro development notes

Running log of how Kiro was used, for the demo video, Devpost description and blog post.

## 2026-10-30 · Spec 1: Monster Mash simulator

**Steering**: `product.md`, `tech.md` and `safety.md` were written before any code. They fixed the key architecture rule (simulators never call the LLM) and the rule that historical claims must be checked against a source before publishing.

**Spec**: requirements (EARS-style acceptance criteria), then design, then 10 tasks, all implemented in one session.

**Hooks**: ruff on every `.py` save; full pytest after each spec task.

**Findings during implementation** (the spec design was updated each time):
- `max_ticks = 200` made 18% of random battles draws. Measured 200/400/600/1000, chose 600 (about 3.5% draws; median battle 90 ticks).
- The first gauntlet included tiny random teams, so many designs scored 1.000. Random opponents are now filtered to "competitive" teams (3+ units, at most 1 gold unspent).
- A non-LLM hill-climb showed the planted imbalances are not the dominant ones. Undead swarm scores 0.15. **pumpkin_mage** (under-costed ranged splash) appears in 7 of 8 optima. This is a better demo story: the tool finds the exploit the designer didn't plant.
- Score still saturates at 1.000 for strong designs. Carried over to Spec 2 (hall of fame / co-evolving gauntlet).

**Result**: 49 tests; 14,874 battles/s (target 1,000); one gauntlet score = 144 battles in about 15 ms.

## 2026-10-30 · Spec 2 written: Eurisko engine

- Probed local `qwen2.5:14b` with the planned heuristic DSL before writing the design: 9 of 9 proposed heuristics were valid; about 10 s per call when warm. This decided that the LLM is used for one meta-heuristic (Invent) only, and everything else stays in code.
- H59 source found: Wikipedia "Reward hacking" names H59 as the parasitic heuristic that took unearned partial credit. Primary source to check before the video: Lenat, *EURISKO: A Program That Learns New Heuristics and Domain Concepts*, Artificial Intelligence 21 (1983).
- Design decision: the engine reproduces the H59 pattern on purpose (lineage credit plus a Clone meta-heuristic), so the auditor's fix can be shown with it switched off and on.

## 2026-10-30 · Spec 2 implemented: Eurisko engine

**Spec as a contract**: all 13 tasks were implemented against the requirements. Where measurement contradicted the design, the change went into an "Implementation notes" section of `design.md` instead of silently diverging.

**Problems found by running the engine, not by reading the code**:
- **A second worth-inflation bug, unplanned.** In the first run, a plain seed heuristic hit worth 1000 by being credited every generation for the same parent → child move. That is H59-like inflation, without any meta-heuristic involved. Fix: a transition is credited at most once. Good material for the video: "we built an auditor for one kind of reward hacking and the system found another".
- **Population collapse.** After that fix, every reachable move was tried by generation 8. Fix: 4 random immigrants per generation.
- **Score saturation** (carried over from Spec 1). Fix: the hall of fame weighs 50% of the score.

**H59 reproduced reliably**: over 8 seeds, Clone was the top meta-heuristic 8/8 times without the auditor and was flagged as a parasite 8/8 times with it. This is now a regression test (`tests/engine/test_auditor.py::test_h59_demo`).

**Local Qwen as Invent**: 18 calls in a 20-generation run, 0 invalid heuristics. LLM-invented rules improved designs at about the same rate as hand-written seeds (65% vs 64%). 4 of the 5 highest-worth rules at the end were LLM-invented.

**Hooks in practice**: the post-task pytest hook got slow (90 s) once engine tests existed, so slow and live-LLM tests moved behind markers. The default run is about 40 s.

**Baseline result, reported as it came out**: at equal battle budget, the engine ties hill-climbing-with-hall-of-fame (0.826 vs 0.838, within noise), and the LLM version scores 0.794. The real win over plain hill-climbing (0.629) comes from the hall of fame. Writing this requirement into the spec up front (R8.2: "report the result whichever method wins") is what stopped the project from being pitched on a claim that wasn't true. The pitch shifts to explanation: ranked, audited, human-readable rules.

## 2026-10-30 · Measurements before Spec 3

- **Correction of an earlier claim.** In Spec 1 we wrote that pumpkin_mage was "the real outlier". Measured properly (16 seeds, against the random competitive baseline), that is wrong: **witch** sits in 94% of top designs against a 32% baseline, stable across seed groups. pumpkin_mage is at 50% against 39% and noisy. The first claim came from a saturated score and 8 restarts. Lesson for the report design: always compare against a random baseline and show the spread across seeds.
- **The fix loop works.** witch cost 2→3 drops witch's share from about 0.94 to 0.45, and flesh_golem becomes the most common unit (0.70). witch heal 12→8 only gets it to 0.80. Nerfing pumpkin_mage (cost, ATK or splash) does almost nothing. So the cheapest stat to change is not always the one that matters, and the report has to measure the candidate fixes, not guess them.
- 16 engine runs (12 generations, no LLM) take 53 s in parallel on the 12-core M4 Pro, so verifying several candidate fixes takes minutes.

## 2026-10-31 · Spec 3 implemented: balance report

- **The fix needed two steps.** Every single witch change either left witch dominant or made flesh_golem dominant (witch cost 2→3: witch 0.93 → 0.40, flesh_golem 0.73). The spec gained a follow-up requirement (R4.5) mid-implementation: if the best change only moves the problem, fix the next unit on top of it. The report found `witch.cost 2→3 + flesh_golem.atk 10→8`, which leaves no unit dominant. It is borderline: witch is still the most common unit at 0.67, just under the 0.7 threshold, and the report says so.
- **Wrong conclusions caught by measuring.** Twice now a 4-seed result was incomplete: "pumpkin_mage is the outlier" (Spec 1) and "witch cost 2→3 fixes it" (pre-Spec-3 probe). The report uses 8 seeds and shows the range.
- **LLM summaries get two checks.** Qwen's first summary used only real numbers but claimed the effective fix "maintains witch as the dominant part" and called the witch cost change ineffective. A number check alone would have let it through. Added a second check, that the summary must state each step of the recommended change. With a clearer prompt, 5/5 Qwen summaries passed. Both failure modes are regression tests.
- **Runtime.** Batching all patch verifications into one process pool brought the default report to about 2 minutes on 12 cores (limit 5).

## 2026-10-31 · Spec 4 implemented: web UI

- **One frontend, two modes.** The same vanilla-JS page renders a static export (for GitHub Pages) and the live server (SSE). One Python function decides what the UI sees in both.
- **Seeing the UI found the bugs tests didn't.** Headless Chrome screenshots at 1280×720 and 390 px caught a CSS class collision, an overridden `hidden` attribute, and arrays printed as `[object HTMLOptionElement]`. All 131 tests were green at the time.
- **A misleading flag.** The worth table showed M2 as PARASITE at generation 20, although later audits had cleared it. The flag now shows the latest verdict.
- **The JS reducer is tested for real**: pytest runs it under Node and compares its final state with the Python run record.

## 2026-10-31 · Spec 5 implemented: Neurisko as an MCP server

- **Checked the SDK before writing code.** The MCP Python SDK is now 2.x (`FastMCP` renamed `MCPServer`); most examples online are 1.x. A 30-line probe confirmed the result shapes, that sync tools run on worker threads, and that prompts work.
- **Checked Kiro's docs before designing.** The `introspect` agent answered from kiro.dev: 120 s default tool timeout, no documented progress notifications, servers start in the workspace root. So the 2-minute report became a background job with a status tool, and the quick tools were sized to finish in about 15 s.
- **Three Kiro features around one MCP server**: a `fileMatch` steering file that activates only when a ruleset is open ("measure, don't guess; verify before recommending"), a `PostFileSave` hook on `rulesets/*.toml` that re-checks balance, and an MCP prompt (`balance_review`) in the `#` menu.
- **A protected path.** Kiro's permission rules block agents from writing `.kiro/settings/`, so `mcp.json` is the one file the user creates by hand (`docs/kiro-mcp.json`).

## 2026-11-01 · End-to-end check in Kiro (Spec 5, task 7)

- In a new Kiro session with `rulesets/monster-mash.toml` open, Kiro loaded the neurisko tools, ran `check_ruleset`, `quick_balance` and two `verify_patch` calls, and answered in Chinese. It followed the steering: it quoted shares with the random baseline and seed count, said 4 seeds are noisy, recommended only the change marked effective, suggested `start_report` before applying it, and did not edit the file.
- Its answer: witch dominant (0.90 vs baseline 0.31, lift 2.89); `witch.cost 2→3` failed (flesh_golem became dominant); `witch.ability.amount 12→7` effective (witch 0.90 → 0.60).
- **Checking that answer with the full-report settings** (6 seeds × 12 generations): `witch.ability.amount 12→7` is **not** effective. witch drops 0.93 → 0.67, but flesh_golem becomes dominant (0.77). 12→6 gives the same result (flesh_golem 0.83). The quick check gave a false positive.
- Fix: the `verify_patch` note and the steering now call a quick "effective" a candidate that must be confirmed with a full report before it is recommended. This is the third time in this project that a small sample gave a wrong answer, after the pumpkin_mage claim and "witch cost 2→3 fixes it".

## 2026-11-04 · Spec 6 implemented: TCS-lite, and GitHub Pages

- **Public replay site**: https://davidechen135.github.io/neurisko/ deployed by GitHub Actions on every push. One deploy failed first: `astral-sh/setup-uv` no longer publishes major-version tags after v7, so the workflow pins `v10.3.3`.
- **History first, then rules.** Before designing TCS-lite we checked what the sources agree on (96 ships, 75 of one class, small ships with many small weapons; 1982 won by destroying its own ships) and wrote only that. The game's rules and numbers are our own.
- **The story had to emerge, not be scripted.** The first numbers made the 1982 rule useless (swarm still won 100%). A small grid search fixed it, and every step is in the design notes. With seed heuristics that only encode "build good warships", the engine found the 99-ship swarm under 1981 rules (swarm dominant in 7/8 champions) and scuttling under 1982 rules (8/8), and nothing in its rules mentions either.
- **Second game, same engine.** The protocol conformance test now runs on both games, and caught a parameter-name mismatch. Old Monster Mash runs still replay identically after the refactor.
