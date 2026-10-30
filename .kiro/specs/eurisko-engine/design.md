# Design: Eurisko Engine

## Overview
```
        ┌──────────── generation loop ────────────┐
        │                                          │
 population ──► agenda ──► design heuristic ──► child design ──► score (simulator)
    ▲            │                                                  │
    │            └──► meta-heuristic ──► new/edited heuristics      │ Δ
    │                   (Invent = LLM)          ▲                   ▼
    └──── hall of fame ◄────────────────────────┴──── credit assignment ──► auditor
                                                                     │
                                                         events.jsonl (every step)
```
The heuristic structure follows Eurisko: heuristics are units with slots and a worth, and meta-heuristics treat heuristics as their objects. Lenat's heuristics were Lisp code. Ours are interpreted data (safety steering). The LLM makes it possible to invent rules from evidence in plain language, which Eurisko could only do by syntactic mutation.

## Measured LLM feasibility (2026-10-30)
Probe: local `qwen2.5:14b`, JSON mode, rules description plus the DSL below, asked for 3 heuristics, 3 trials. **9 of 9 heuristics were valid** (known features, known units, known action kinds). Latency was 24 s cold and about 10 s warm for about 230 output tokens, with a 780-token prompt. The proposals were sensible, for example "IF winrate_vs_armor_wall < 0.6 AND n_ranged < 3 THEN add a ranged unit". So Invent is affordable about once every 2 generations.

## Game protocol extension (engine/game.py)
```python
class Game(Protocol[D]):
    ...existing...
    def score(self, design: D, extra_opponents: Sequence[D] = ()) -> ScoreReport: ...
    def feature_names(self) -> list[str]: ...
    def features(self, design: D, report: ScoreReport) -> dict[str, float]: ...
    def action_schema(self) -> dict[str, dict[str, list[str]]]: ...  # kind -> param -> allowed values
    def apply_action(self, design: D, action: Action, rng: random.Random) -> D | None: ...
    def held_out(self) -> Game[D]: ...  # same rules, gauntlet built from another seed
```
`Action` is a game-agnostic `{"kind": str, **params}` dict, checked against `action_schema()`.

### Monster Mash vocabulary
- **Features**: `n_units`, `cost`, `unspent`, `n_ranged`, `n_melee`, `front_hp`, `front_armor`, `count_<unit>` ×12, `count_<faction>` ×4, `winrate_vs_<archetype>` ×6. That is 29 features.
- **Actions**:
  | kind | params |
  |---|---|
  | `add_unit` | `unit` ∈ units, `position` ∈ {front, back} |
  | `remove_unit` | `unit` ∈ units ∪ {@cheapest, @most_expensive} |
  | `replace_unit` | `old` ∈ units ∪ {@cheapest, @most_expensive}, `new` ∈ units |
  | `move_unit` | `unit` ∈ units, `to` ∈ {front, back} |
- `apply_action` returns `None` when the action can't apply (unit absent, over budget, too many copies). That counts as a misfire: no credit, and the misfire count is tracked.
- Score caching key becomes `(design, opponent-pool version)`.

## Data model (engine/heuristics.py, pydantic)
```python
class Condition(BaseModel):  feature: str; op: Literal["<","<=",">",">=","==","!="]; value: float
class Origin(BaseModel):     by: str; parent: str | None; generation: int
class Stats(BaseModel):      applications: int = 0; misfires: int = 0; improvements: int = 0
                             direct_credit: float = 0; lineage_credit: float = 0
                             recent: list[tuple[Design, Design]]   # last 8 (parent, child), for audit
class Heuristic(BaseModel):
    id: str              # "H1", "H2", ... (Eurisko-style numbering)
    level: Literal["design", "meta"]
    name: str; rationale: str = Field(max_length=200)
    conditions: list[Condition] = Field(max_length=3)   # design level only
    action: dict                                         # design level only
    worth: float = 500   # 0..1000
    origin: Origin; stats: Stats; alive: bool = True; flags: list[str] = []
```
`validate_heuristic(h, game)` checks features against `feature_names()` and the action against `action_schema()`. It returns a list of errors.

Meta-heuristics are built-in code objects, but they are recorded as `Heuristic(level="meta")` with worth and stats, so the UI shows them alongside design heuristics:

| id | name | effect | uses LLM |
|---|---|---|---|
| M1 | Invent | proposes up to 3 design heuristics from evidence | yes |
| M2 | Specialize | adds one condition taken from the features of the parent of a successful application | no |
| M3 | Generalize | drops one condition | no |
| M4 | Retarget | changes one unit parameter of the action | no |
| M5 | Clone | copies a high-worth heuristic unchanged | no |

**Why M5 exists.** It is the cheapest way to produce Eurisko's H59 pattern. A copy behaves exactly like its source, so it earns the same direct credit, and the meta-heuristic that made it collects lineage credit for work that was already being done. M2 and M3 can also produce exact duplicates by accident, for example when a condition is always true, so the pattern does not depend on M5. The Devpost text must say plainly that M5 is a deliberate analogue of H59, not a recreation of Lenat's code.

## Seed heuristics (data/seed_heuristics.toml per game)
About 10 obvious rules, so that `--no-llm` runs work, for example: "IF unspent ≥ 1 THEN add @cheapest-affordable", "IF winrate_vs_armor_wall < 0.5 THEN add ghost", "IF n_ranged == 0 THEN replace @cheapest with witch". They are plain and kept deliberately weak, so that improvement over them is visible.

## Generation loop (engine/evolve.py)
Defaults (all in `EvolveConfig`):

| key | default |
|---|---|
| population size P | 20 (starts as P random competitive designs) |
| design applications / gen | 40 |
| meta applications / gen | 3 (Invent at most once, and only if the LLM budget allows) |
| hall of fame cap | 12 |
| audit interval | every 3 gens |
| retire threshold | worth < 100 (keep at least 8 design heuristics alive) |

```
for gen in 1..G:
    pool = gauntlet + hall_of_fame                  # pool version bumps when HoF changes
    rescore population vs pool
    for task in agenda.design_tasks(n=40):          # (heuristic, design) with matching conditions
        child = game.apply_action(design, h.action, rng)
        if child is None: misfire; continue
        Δ = score(child) - score(design)            # same pool
        credit(h, Δ)
        population.offer(child)
    for task in agenda.meta_tasks(n=3):
        new = meta.apply(...)                       # validated; duplicates by id/name allowed (auditor's job)
    hall_of_fame.update(best of population)         # add if not present; evict weakest vs current pool
    if auditor and gen % 3 == 0: audit()
    retire()
    record generation summary
```

### Agenda priority
`priority(h, d) = h.worth/1000 + 0.5 · rank_score(d) + c · sqrt(ln(N) / (1 + h.applications)) + ε`. Here `rank_score` is the population rank scaled to [0, 1], the third term is a UCB bonus that makes sure new heuristics get tried, and ε is seeded noise below 0.01 that breaks ties. Each heuristic gets at most 6 tasks per generation, so the queue keeps some diversity.

### Credit assignment
- Reward: `r = clip(Δ / 0.05, −1, 1)`, so a 5-point win-rate gain is full credit.
- Direct: `worth ← worth + α · (500 + 500·r − worth)`, α = 0.2. `stats.direct_credit += r`.
- Lineage: the creating meta-heuristic M receives `worth_M ← worth_M + λα · (500 + 500·r − worth_M)` with λ = 0.5, and `stats.lineage_credit += λ·r`. Each lineage contribution is also logged against the child heuristic, so the auditor can revoke it.
- Worth is clamped to [0, 1000].

## Auditor (engine/auditor.py)
Runs every 3 generations. Every decision is written as an `audit` event with its numbers.

1. **Replication.** For each design heuristic with worth > 600 and at least 5 applications, re-score its `recent` (parent, child) pairs against `game.held_out()` (gauntlet seed + 1 plus the current hall of fame). IF the mean held-out Δ ≤ 0 THEN set worth to 400 and flag `non-replicating`.
2. **Duplicates.** Signature = the tuple of `apply_action` outputs on 32 fixed probe designs, combined with which probes pass the conditions. Two heuristics with the same signature are duplicates. Keep the older one, add the newer one's stats to it, retire the newer one and flag it `duplicate-of:Hn`. Revoke the lineage credit the duplicate gave to its creator (subtract from `lineage_credit` and recompute worth from the logged contributions).
3. **Parasite.** For each meta-heuristic: `tainted = lineage credit from duplicate or non-replicating children / total lineage credit`. IF tainted > 0.5 and worth > 600 THEN set worth to 300 and flag `parasite`.

With `--no-auditor`, the expected outcome is that M5 Clone climbs toward the top of the worth table. This is the H59 demo. The tests check this behaviour on a small fixed run.

## LLM (llm/)
- `client.py`: `LLMClient` protocol with `complete(messages) -> LLMResponse(text, usage, latency)`. The `OpenAICompatClient` uses the `openai` SDK with `base_url` and JSON mode, a 120 s timeout and no SDK retries (failures are handled by the engine, R6.4). `ReplayClient` returns recorded responses in order. `FakeClient` is for tests.
- `prompts.py`: system prompt = `game.describe_rules()` + DSL description generated from `feature_names()` and `action_schema()`. User prompt = evidence: top 3 designs with their 2 worst matchups, top 5 and bottom 3 design heuristics with worth, applications and improvement rate, plus recent audit flags. Target prompt size below 2k tokens.
- `schemas.py`: response = `{"heuristics": [ {name, rationale, if, then} ]}`. Each item is parsed separately, so one bad item does not discard the others.
- Settings: `pydantic-settings` reads `.env` (`LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`, `MAX_LLM_CALLS_PER_GENERATION`, `MAX_GENERATIONS`). The key is a `SecretStr` and is excluded from every record.

## Recording (runs/)
- `recorder.py` appends one JSON object per line to `runs/<run_id>/events.jsonl`, with `{"t": seq, "gen": n, "type": ..., ...}`. Event types: `run_start`, `heuristic_created`, `heuristic_rejected`, `applied`, `credited`, `scored`, `hof_added`, `hof_removed`, `llm_call`, `llm_error`, `audit`, `retired`, `generation`, `run_end`.
- `meta.json`: config, seed, ruleset hash, model name, git commit if available, start/end time.
- Battle logs are not recorded per application, to keep runs small. The UI can re-simulate any recorded matchup on demand, because battles are deterministic.
- `--replay runs/<id>` re-executes with `ReplayClient`. Determinism is checked by comparing the `generation` events.

## CLI
`neurisko evolve [--generations 20] [--seed 0] [--no-llm] [--no-auditor] [--run-id ID] [--ruleset PATH] [--replay DIR]`

Per-generation output, in the terminal style:
```
GEN 07  best 0.912  pop 20  hof 7/12  llm 1 call 9.8s  battles 9,860
  H14  912  Improve vs Armor Wall   IF winrate_vs_armor_wall<0.6 THEN replace @cheapest→ghost
  M5   874  Clone                   [lineage 82%]
  AUDIT H21 duplicate-of:H14 · M5 parasite (tainted 0.71) → 300
```

## Evaluation script (scripts/compare_baseline.py)
Runs the engine (`--no-llm`, and with the LLM when available) and a random-mutation hill-climb (best-first over `game.mutations`), each limited to the same number of battles, over 5 seeds. Both final champions are scored against the held-out pool plus each other. The script prints a table and writes `docs/BASELINE.md`. The result is reported as it comes out, including if the engine loses.

## Error handling
- Invalid LLM heuristic: `heuristic_rejected` event with its errors; the run continues.
- LLM timeout or connection error: `llm_error` event; Invent is skipped for that generation (R6.4).
- Budget reached: `run_end` with `reason: "budget"`.
- Ctrl-C: write `run_end` with `reason: "interrupted"` and exit cleanly. The partial run stays replayable.

## Testing strategy
- Protocol: Monster Mash features match `feature_names()`; every action kind applies or returns `None`, and results are always valid designs.
- Validation: unknown feature, kind or unit is rejected with a message; the seed set validates.
- Credit: a hand-built Δ sequence gives the expected worth values; lineage credit goes to the creator; clamping works.
- Agenda: heuristics whose conditions fail are never scheduled; the per-heuristic cap holds; untried heuristics get scheduled.
- Auditor: a constructed duplicate is merged and its lineage credit is revoked; a heuristic whose gains don't replicate on the held-out pool is demoted; a meta-heuristic with mostly tainted credit is flagged.
- H59 demo: on a fixed seed, a short `--no-auditor` run puts M5 in the worth top 3, and the same run with the auditor flags it.
- LLM: `FakeClient` returning a mix of valid and invalid items gives correct keep/reject events; a timeout is recorded as `llm_error` and the run continues; the API key never appears in `events.jsonl` or `meta.json`.
- Determinism: same seed with `FakeClient` gives identical `generation` events; replaying a recorded run reproduces them.
- Optional integration test against a live Ollama, marked `@pytest.mark.llm` and skipped by default.

## Implementation notes (2026-10-30)
Changes made while implementing, each driven by a measured problem. The code is the reference; this section explains why it differs from the design above.

1. **No repeated credit for the same move.** In the first run, a seed heuristic reached worth 1000 by being credited every generation for the *same* parent → child transition on a stable population. This is a second, unplanned way to inflate worth without new work. The agenda now skips any `(parent, child)` transition that was already credited.
2. **Immigrants.** After fix 1, the population converged and every reachable move had been tried by generation ~8 (applications dropped from 40 to 0–8 per generation). Each generation now replaces the 4 weakest designs with fresh random ones (`immigrants = 4`).
3. **Hall-of-fame weighting.** With 24 gauntlet opponents and up to 12 hall-of-fame opponents, the hall of fame was only a third of the pool, so strong designs still saturated near 1.0. The optimised score is now `0.5 · gauntlet win rate + 0.5 · hall-of-fame win rate` (`hof_weight`, `engine/game.py: weighted_score`). The strongest design *not yet* in the hall of fame joins it each generation, so pressure keeps rising even when the champion does not change.
4. **No misfires.** The agenda only schedules tasks whose action actually applies, so there is no misfire penalty. Heuristics with no applicable task for 5 generations retire as `dormant`.
5. **Parasite check.** It runs whatever the current worth is, because the duplicate check's revocation usually already pulls worth below 600 in the same audit. The tainted ratio counts revoked contributions too. It needs at least 3 positive contributions.
6. **Events.** `credited` is folded into `applied` (worth before/after, lineage). Added `meta_applied` and `llm_skipped`. `generation` summaries add `best_held_out_pool` (held-out gauntlet plus current hall of fame).
7. **Tests.** Default `uv run pytest` skips the `slow` (20-generation budget test, extra H59 seeds) and `llm` (live endpoint) markers, so the post-task hook stays under a minute.

## Measured results (2026-10-30)
- **H59 demo**: small config, 9 generations, seeds 0–7. Without the auditor, M5 Clone was the highest-worth meta-heuristic on **8 of 8** seeds (worth 700–909). With the auditor, it was flagged as a parasite on **8 of 8** (worth 300).
- **Speed**: 20 generations without the LLM take about 37 s with the full gauntlet (R8.3 limit: 60 s). About 220k battles.
- **Live Qwen run** (`runs/demo/qwen-s0`, 20 generations, about 6 minutes): 18 LLM calls, 0 errors, 0 rejected heuristics, 54 heuristics invented. LLM-invented heuristics improved the design on 65% of applications (mean Δ +0.093), against 64% (+0.080) for the hand-written seeds. The top 5 heuristics by worth at the end: 4 were invented by the LLM, 1 came from Specialize.
- **Baseline comparison** (`docs/BASELINE.md`, 5 seeds, equal battle budget about 214k): on the final exam, hc+hof scored 0.838, engine 0.826, engine+llm 0.794 and plain hill-climbing 0.629. The top three are within seed noise. The hall of fame accounts for the gain over plain hill-climbing; the heuristics and the LLM do not produce better champions. 20/20 champions across all methods contain witch or pumpkin_mage.
- **Consequence for Spec 3**: the product claim is explanation (ranked, audited rules saying *why* designs win, plus the identified imbalance), not stronger search. Don't claim in the video or Devpost text that Neurisko out-searches a hill-climb.
