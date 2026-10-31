# Design: Balance Report

## Measurements this design is based on (2026-10-30)
Default ruleset, engine without LLM, 12 generations, top 5 designs per run.

| | witch | flesh_golem | werewolf | pumpkin_mage | ghost |
|---|---|---|---|---|---|
| baseline share (3,000 random competitive designs) | 0.32 | 0.41 | 0.33 | 0.39 | 0.30 |
| evolved share, 16 seeds | **0.94** | 0.56 | 0.51 | 0.50 | 0.36 |
| range over 4 groups of 4 seeds | 0.90–1.00 | 0.50–0.65 | 0.45–0.70 | 0.25–0.70 | 0.40–0.45 |

Patches, 4 seeds each:

| patch | witch share | most common after |
|---|---|---|
| none | 0.90 | witch |
| witch cost 2→3 | **0.45** | flesh_golem 0.70 |
| witch heal 12→8 | 0.80 | witch |
| pumpkin_mage cost 3→4 / ATK 20→16 / splash 0.6→0.3 | 0.75–1.00 | witch |

Consequences:
- With the default thresholds, witch is dominant (lift 2.9). No other unit reaches lift 1.8.
- 4 seeds are enough to see a 0.94 → 0.45 change, but not to rank units at 0.5 ± 0.2. So detection uses 8 seeds and the report always shows the min/max.
- Runtime: 16 runs took 53 s in parallel on 12 cores. Default report = 8 detection runs + 2 parts × 3 patches × 6 seeds = 44 runs ≈ 3 minutes.

## Overview
```
ruleset ──► detection (8 seeds, parallel) ──► shares, lift, flags
                    │                               │
                    ├──► dependence (ablation of champions)
                    ├──► evidence heuristics, matchups
                    ▼
            dominant parts ──► patch candidates ──► verification (6 seeds each, parallel)
                                                          │
                              report.json + report.md ◄───┘ (+ optional LLM summary, number-checked)
```

## Modules
```
src/neurisko/report/
  protocol.py   # Patch model (pydantic)
  detect.py     # run_batch(), shares, flags
  explain.py    # dependence, evidence heuristics, matchup gains
  verify.py     # patch verification and ordering
  summary.py    # template summary; LLM summary + number check
  report.py     # build_report(): orchestrates, writes artifacts
games/autobattler/patches.py   # Monster Mash candidates and with_patch
```

### Batch runner (detect.py)
```python
@dataclass(frozen=True)
class RunSpec:  ruleset_json: str; seed: int; config: EvolveConfig
@dataclass
class RunOutcome:
    seed: int; champion: list[str]; top: list[list[str]]
    champion_held_out: float
    heuristics: list[dict]   # alive design heuristics: text, action, worth, applications, improvements
    battles: int; seconds: float
def run_batch(specs, workers) -> list[RunOutcome]  # ProcessPoolExecutor; sorted by seed
```
Workers receive the ruleset as JSON, not a `Game` object, so nothing large or unpicklable crosses process boundaries. Each worker rebuilds `MonsterMash(parse_ruleset(...))`. Results are sorted by seed, so the output does not depend on the number of workers (R2.5). `workers=1` runs in-process (used by tests).

`top` is the final population's top 5 (k = 5).

### Shares and flags
- Baseline: `game.baseline_designs(Random(1981), 3000)`; Monster Mash uses the existing `is_competitive` filter.
- Per part: `evolved = mean over runs of share(top)`, `lo/hi = min/max over runs`, `lift = evolved / max(baseline, 0.01)`, `champion_runs = #runs whose champion contains the part`.

### Dependence (explain.py)
For each champion containing the part, replace one copy of it with every other part that keeps the design valid, and take the best alternative's score. `dependence = score(champion) − best alternative`, against the champion's own scoring pool (held-out gauntlet plus all champions of the batch, half weight). Report the mean and the per-champion values.

### Evidence heuristics
A heuristic counts as evidence for a part if its action is `add_unit(unit=part)` or `replace_unit(new=part)`. Across all detection runs, sort by final worth and take the top 5. Exact duplicates (same text) are merged; the report shows how many runs contained each.

### Matchup gains
Using the champions' `ScoreReport` against the held-out gauntlet: for each opponent, the mean score of champions with the part minus the mean of champions without it. Show the top 3. Skip this when fewer than 2 champions are in either group, and say so.

### Patches (games/autobattler/patches.py)
```python
class Patch(BaseModel):  target: str; field: str; old: float; new: float; label: str
```
`field` is one of `cost`, `atk`, `hp`, or `ability.<param>` (`amount`, `fraction`, `chance`, `multiplier`, `max`). Candidates, as R1.4 says: cost +1 (skipped if that exceeds the budget), main stat ×0.8 rounded (at least 1 below the old value), ability magnitude ×0.7 (integers rounded, at least 1 below; `multiplier` is reduced toward 1, not below it). `with_patch` edits a dumped ruleset dict, drops archetypes that become over budget (returned in `dropped_opponents`), and re-validates through `parse_ruleset`.

For witch this gives: `witch.cost 2→3`, `witch.hp 45→36` (ATK 6 ≤ 6, so HP is the main stat), `witch.ability.amount 12→8`.

### Verification (verify.py)
For each patch: `run_batch` on the patched ruleset with `verify_seeds`. Compute the same share table and apply R4.3. The "before" numbers come from the detection runs with the same first `verify_seeds` seeds, so before and after use the same seeds.

### Summary (summary.py)
Template example (layout only; the dependence value, champion count and underused list are illustrative, not measured yet):
> **witch is dominant**: in 94% of top designs (range 90–100% over 8 runs) against 32% of random teams, and in 8/8 champions. Champions lose 0.21 on average without it. **Effective fix: witch.cost 2 → 3**: share drops to 45%, nothing else becomes dominant; most common unit afterwards is flesh_golem (70%). **Never used**: necromancer, skeleton.

LLM summary: the system prompt says to use only the given facts and numbers. The facts are the template's numbers as JSON. Number check: extract `\d+(\.\d+)?%?` from the reply; normalise percentages and decimals (`45%` == `0.45`); every number must be in the set of fact values formatted as shown, plus counts and small integers ≤ 10 (seed counts, ranks). On failure, emit `llm_summary_rejected` with the offending numbers and use the template.

### Artifacts
`reports/<report_id>/report.json`:
```json
{"schema": 1, "ruleset_hash": "...", "config": {...}, "seeds": [...], "seconds": 171,
 "baseline_n": 3000,
 "parts": [{"part": "witch", "evolved": 0.94, "lo": 0.9, "hi": 1.0, "baseline": 0.32,
            "lift": 2.9, "champion_runs": 8, "flags": ["dominant"]}, ...],
 "dominant": [{"part": "witch", "dependence": {...}, "evidence": [...], "matchups": [...],
               "patches": [{"patch": {...}, "before": {...}, "after": {...},
                            "effective": true, "failed": [], "dropped_opponents": []}]}],
 "underused": ["necromancer", ...],
 "summary": {"template": "...", "llm": null, "llm_rejected": null},
 "champions": [{"seed": 0, "design": [...], "held_out": 0.98}, ...]}
```
`report.md` renders the same data with tables. `reports/` is gitignored except `reports/demo/`.

## CLI output (terminal style)
```
NEURISKO BALANCE REPORT  ruleset f22da09334d3  8 seeds x 12 gens
[detect] 8/8 runs  41s
  witch          ████████████████████ 0.94 (0.90-1.00)  base 0.32  lift 2.9  DOMINANT
  flesh_golem    ████████████         0.56 ...
[verify] witch: cost 2->3 ✓ effective   hp 45->36 ✗ still dominant   heal 12->8 ✗ still dominant
...
```

## Error handling
- An invalid ruleset gives the existing `RulesetError` and exit code 2.
- A worker exception stops the batch and reports which seed failed. No partial report is written.
- No dominant parts: the report says so and skips verification. This is a valid result.

## Testing strategy
- Patches: candidate list for witch matches the design; `with_patch` changes the hash; an over-budget archetype is dropped and reported; the multiplier is never reduced below 1.
- Batch: same results for `workers=1` and `workers=2` on a tiny config.
- Shares and flags: hand-built outcomes give the expected lift and flags.
- Dependence: on a constructed champion, the value equals a hand-computed score difference.
- Number check: a reply with an invented number is rejected; one using only the fact numbers (as % or decimal) is accepted.
- Artifacts: `report.json` validates against the pydantic schema; `report.md` contains the summary.
- Acceptance (R8, `slow`): default report flags witch and finds an effective patch for it.

## Implementation notes (2026-10-30)
1. **Batched verification.** All patches of one part run as one process-pool batch (runs are tagged by change text), so 18 runs use all 12 cores. Doing patches one after another took about 3× longer.
2. **Follow-up step (R4.5).** Measured on the default ruleset with 6 verify seeds:

   | change | witch | most common / dominant after |
   |---|---|---|
   | witch.cost 2→3 | 0.93 → 0.40 | flesh_golem 0.73 (dominant) |
   | witch.hp 45→36 | 0.93 → 0.87 | still dominant |
   | witch.ability.amount 12→8 | 0.93 → 0.77 | still dominant |
   | witch.cost 2→3 + flesh_golem.cost 3→4 | – | flesh_golem 0.10; werewolf becomes dominant |
   | **witch.cost 2→3 + flesh_golem.atk 10→8** | – | **flesh_golem 0.37; nothing dominant** (witch 0.67, lift 1.84, just under the 0.7 share threshold) |

   So the earlier 4-seed finding "witch cost 2→3 fixes it" was incomplete: it moves the problem to flesh_golem. Before/after for the follow-up uses the step-1 outcomes of the same seeds.
3. **Runtime**: the default report takes 119 s (8 detection runs, 3 + 2 patches × 6 seeds). R7.2 limit: 5 minutes.
4. **Converged populations.** A run's top 5 are often near-copies of one design, so per-run shares are often 0 or 1, and ranges are wide (e.g. ghost 0.00–1.00). The report shows the range rather than hiding it.
