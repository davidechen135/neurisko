# Requirements: Eurisko Engine

## Introduction
The engine is the core of Neurisko. Like Lenat's Eurisko, it keeps a pool of heuristics, each with a **worth** score from 0 to 1000. Object-level heuristics change game designs; meta-heuristics create and change other heuristics. An agenda decides which heuristic to apply next. Worth comes only from measured results in the simulator.

The LLM takes part in exactly one meta-heuristic, **Invent**: it reads the evidence and proposes new heuristics. Everything else is plain code, so a run is fast, bounded and replayable.

The engine must also reproduce Eurisko's best-known failure and guard against it. Around 1983, a heuristic called H59 reached the highest possible worth by taking partial credit for other heuristics' discoveries ([Wikipedia: Reward hacking](https://en.wikipedia.org/wiki/Reward_hacking); primary source to check before publishing: Lenat, *EURISKO: A Program That Learns New Heuristics and Domain Concepts*, Artificial Intelligence 21, 1983). Neurisko's **auditor** detects that pattern. With the auditor turned off, the failure should be observable.

The engine depends only on the `Game` protocol. Monster Mash is the first game; TCS-lite comes later.

## Glossary
- **Design heuristic**: data rule `IF conditions on design features THEN action on the design`.
- **Meta-heuristic**: rule that produces or edits design heuristics (Invent, Specialize, Generalize, Retarget, Clone).
- **Worth**: 0–1000, starts at 500. Drives the agenda.
- **Application**: one firing of a heuristic. For a design heuristic: parent design → child design, scored.
- **Opponent pool**: the game's fixed gauntlet plus the hall of fame.
- **Hall of fame**: strong designs found during the run, added to the opponent pool.
- **Held-out pool**: a second gauntlet with a different seed, used only by the auditor.
- **Run**: one execution of the evolution loop, recorded under `runs/<run_id>/`.

## Requirements

### R1. Game protocol extension
**User story:** As the engine, I need game-specific vocabulary for conditions and actions without importing the game.

1. The `Game` protocol SHALL add: `feature_names()`, `features(design, report)` returning `dict[str, float]`, `action_schema()` describing action kinds and parameter domains, and `apply_action(design, action, rng)` returning a valid design or `None`.
2. `score` SHALL accept extra opponents, so that the hall of fame can join the opponent pool.
3. Monster Mash SHALL implement these. Its features SHALL include team size, cost, unspent gold, ranged/melee counts, front-line HP and armor, per-unit and per-faction counts, and win rate against each archetype.

### R2. Heuristics are validated data
**User story:** As the operator, I want heuristics to be data that our code interprets, so that nothing the LLM writes is executed.

1. A design heuristic SHALL have: id, name, rationale (≤ 200 chars), 0–3 conditions (feature, operator, number), one action, worth, origin (creating meta-heuristic, parent heuristic, generation), and application statistics.
2. The system SHALL reject any heuristic with an unknown feature, unknown action kind or out-of-domain parameter, and SHALL log the reason.
3. The system SHALL ship a hand-written seed set of design heuristics, so that runs work without an LLM.

### R3. Evolution loop
**User story:** As a designer, I want the system to search for strong designs over generations.

1. Each generation SHALL: rescore the population against the current opponent pool; run design-heuristic applications chosen by the agenda; run meta-heuristic applications; update the population and hall of fame; run the auditor when due; retire low-worth heuristics; record the generation.
2. The agenda SHALL prioritise tasks by heuristic worth and design score, with a seeded exploration term so that new heuristics get tried.
3. A heuristic SHALL only be applied to a design whose features satisfy its conditions.
4. WHEN the run is given the same seed, config, ruleset and recorded LLM responses THEN it SHALL produce identical results.

### R4. Credit assignment
**User story:** As the operator, I want worth to reflect measured contribution only (safety steering).

1. A design heuristic's worth SHALL be updated from Δ = score(child) − score(parent), with both scored against the same opponent pool.
2. A meta-heuristic SHALL receive a configurable share of the credit later earned by the heuristics it created (lineage credit), as Eurisko did.
3. The system SHALL keep direct credit and lineage credit as separate totals for every heuristic.
4. No credit SHALL come from any value a heuristic or the LLM reports about itself.

### R5. Auditor
**User story:** As a designer, I want to trust that high-worth heuristics really help, and as the presenter, I want to show Eurisko's H59 failure and its fix.

1. **Replication check**: for high-worth heuristics, the auditor SHALL re-score recent parent/child pairs against the held-out pool. IF the improvement does not replicate THEN it SHALL demote the heuristic.
2. **Duplicate check**: the auditor SHALL compare heuristics by behaviour on a fixed probe set of designs. A heuristic that behaves exactly like an older one SHALL be merged into it, and the lineage credit it generated SHALL be revoked.
3. **Parasite check**: IF a heuristic's worth is mostly lineage credit traced to duplicates or non-replicating heuristics THEN the auditor SHALL demote it and flag it as a parasite.
4. Every audit decision SHALL be recorded with the evidence numbers.
5. The auditor SHALL be switchable off (`--no-auditor`), so that the parasite pattern can be demonstrated.

### R6. LLM Invent
**User story:** As the operator, I want the LLM to invent heuristics from evidence, within budget, on any OpenAI-compatible endpoint.

1. Invent SHALL send the rules description, the condition/action vocabulary and current evidence (top designs and their worst matchups, best and worst heuristics with their stats), and SHALL request JSON.
2. Each proposed heuristic SHALL be validated separately. Valid ones are kept and invalid ones are logged. IF none are valid THEN Invent SHALL retry once with the validation errors, and the retry SHALL count against the budget.
3. The system SHALL enforce `MAX_LLM_CALLS_PER_GENERATION` and `MAX_GENERATIONS`, and SHALL stop cleanly when a budget is hit.
4. WHEN the LLM endpoint is unreachable or times out THEN the run SHALL continue without Invent for that generation and record the error.
5. Endpoint, model and key SHALL come from `.env`. The key SHALL never be written to a run record or log.

### R7. Run recording and replay
**User story:** As the web UI (next spec), I need every run on disk, so that it can be replayed without an LLM.

1. A run SHALL write `runs/<run_id>/meta.json` (config, seed, ruleset hash, model name, timings) and `events.jsonl` (heuristic created / applied / credited / audited / retired, design scored, hall-of-fame change, LLM call with prompt, response and token usage, generation summary).
2. A run SHALL be re-executable from its record by replaying recorded LLM responses instead of calling the endpoint.

### R8. CLI and evaluation
**User story:** As the developer and for the video, I want to start a run from the terminal and see whether the engine is better than a naive search.

1. `neurisko evolve` SHALL accept `--generations`, `--seed`, `--no-llm`, `--no-auditor`, `--run-id` and `--ruleset`, and SHALL print per-generation progress: best score, hall-of-fame size, top heuristics by worth, and audit flags.
2. A script SHALL compare the engine with a plain random-mutation hill-climb using the same battle budget, scoring both final champions against a held-out pool, and SHALL report the result whichever method wins.
3. A run of 20 generations without the LLM SHALL finish in under 60 seconds on the dev machine.
