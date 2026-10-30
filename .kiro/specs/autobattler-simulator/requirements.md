# Requirements: Auto-battler Simulator ("Monster Mash")

## Introduction
Monster Mash is a small Halloween-themed auto-battler used as Neurisko's primary game domain. Players build a team under a gold budget, and two teams fight automatically. The simulator must be fast, deterministic and data-driven, so that the Eurisko engine (next spec) can run thousands of battles per generation and a designer can edit the ruleset file and rerun to check a balance fix.

The default ruleset deliberately contains known imbalances. They are fixtures: the engine spec will use them as an acceptance test ("Neurisko rediscovers them").

## Glossary
- **Ruleset**: data file defining units, factions, synergies and global limits.
- **Design**: one team, an ordered list of unit ids (index 0 is the front).
- **Battle**: one simulated fight between two designs with a seed.
- **Gauntlet**: fixed pool of opponent designs used to score a design.
- **Game interface**: the game-agnostic protocol the engine depends on.

## Requirements

### R1. Data-driven ruleset
**User story:** As a game designer, I want all units and rules in one editable file, so that I can change a number and rerun without touching code.

1. The system SHALL load the ruleset from a TOML file, defaulting to the packaged `src/neurisko/games/autobattler/data/default.toml`.
2. WHEN the ruleset file is invalid (missing field, unknown ability, negative stat, unknown faction) THEN the system SHALL refuse to load it and report the field and reason.
3. The system SHALL compute a stable ruleset hash so that runs with different rulesets can be told apart.
4. The default ruleset SHALL define 12 units in 4 factions, each faction having a 2-unit synergy bonus.

### R2. Team building
**User story:** As the engine, I want to generate, validate and mutate designs, so that I can search the design space.

1. A design SHALL be valid only IF it has 1 to `max_team_size` units, total cost ≤ `budget`, and no unit appears more than `max_copies` times.
2. The system SHALL generate a random valid design from a seeded RNG.
3. The system SHALL offer primitive mutations (add, remove, replace, swap positions) that always return a valid design or report that none is possible.
4. WHEN given an invalid design THEN validation SHALL return every violated constraint.

### R3. Deterministic combat
**User story:** As a developer, I want the same inputs to always give the same result, so that runs can be replayed and tests are reliable.

1. WHEN two designs, a ruleset and a seed are given THEN the battle result and log SHALL be identical on every run.
2. Actions within one tick SHALL resolve simultaneously, so that neither side gets a first-mover advantage.
3. WHEN a battle reaches `max_ticks` THEN it SHALL end in a draw.
4. The result SHALL include the winner (A, B or draw), ticks elapsed, surviving units, and per-unit stats (damage dealt, damage taken, kills, healing, summons).
5. WHERE a full log is requested, the system SHALL record ordered events (attack, damage, dodge, heal, summon, death, synergy activation).

### R4. Scoring
**User story:** As the engine, I want one number for how strong a design is, so that I can do credit assignment.

1. The system SHALL score a design as its win rate against the gauntlet, counting a draw as 0.5.
2. Each matchup SHALL be played on both sides and over a configurable number of seeds.
3. The gauntlet SHALL be built deterministically from the ruleset and a seed: hand-written archetype designs plus random valid designs.
4. The score SHALL be in [0, 1] and reproducible for the same ruleset, gauntlet seed and design.

### R5. Performance
**User story:** As the engine, I need battles to be cheap, so that evolution runs live in a demo.

1. A battle SHALL NOT call the LLM, the network or the filesystem.
2. The simulator SHALL run at least 1,000 battles per second on one core of the dev machine (Apple M4 Pro), measured by a benchmark script.

### R6. Game interface
**User story:** As the engine author, I want the engine to depend on a protocol rather than on Monster Mash, so that TCS-lite can plug in later.

1. The system SHALL define a `Game` protocol with: ruleset access, random design, validate, mutations, simulate, score, and design description for prompts.
2. Monster Mash SHALL implement this protocol, and the engine-side code SHALL import only the protocol.

### R7. CLI
**User story:** As a developer and for the demo video, I want to run a battle from the terminal.

1. `neurisko battle A B --seed N` SHALL print the battle log and result, where A and B are comma-separated unit ids.
2. `neurisko score A` SHALL print the gauntlet score and per-opponent results.
3. Both commands SHALL accept `--ruleset PATH`.
