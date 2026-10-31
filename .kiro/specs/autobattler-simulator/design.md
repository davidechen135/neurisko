# Design: Auto-battler Simulator ("Monster Mash")

## Overview
A tick-based 5v5 auto-battler. Teams are ordered lists; the front of the list is the front line. The rules are small enough to explain in the demo video in 20 seconds, but have enough interactions (armor, summons, synergies, positioning) for non-obvious dominant strategies to exist.

## Game rules

### Global limits (default ruleset)
| Key | Value |
|---|---|
| `budget` | 10 gold |
| `max_team_size` | 5 |
| `max_copies` | 2 per unit |
| `max_ticks` | 600 (200 caused 18% draws on random matchups; 600 gives ~3.5%, median battle 90 ticks) |
| `front_line_size` | 2 |

### Units
Stats: `cost`, `hp`, `atk`, `armor`, `speed` (ticks between attacks, lower is faster), `range` (`melee` / `ranged`), `faction`, optional `ability`.

| Unit | Faction | Cost | HP | ATK | Armor | Speed | Range | Ability |
|---|---|---|---|---|---|---|---|---|
| skeleton | undead | 1 | 40 | 8 | 0 | 10 | melee | none |
| zombie | undead | 1 | 80 | 6 | 0 | 14 | melee | none |
| necromancer | undead | 3 | 50 | 6 | 0 | 12 | ranged | `summon_on_ally_death` (skeleton, max 3) |
| werewolf | beast | 2 | 90 | 14 | 0 | 10 | melee | `lifesteal` 30% |
| bat_swarm | beast | 1 | 30 | 5 | 0 | 5 | melee | `dodge` 30% |
| hellhound | beast | 3 | 110 | 18 | 0 | 12 | melee | `first_strike` ×2 |
| witch | arcane | 2 | 45 | 6 | 0 | 12 | ranged | `heal_lowest_ally` 12 per attack |
| pumpkin_mage | arcane | 3 | 50 | 20 | 0 | 16 | ranged | `splash` (target + next in line) |
| ghost | arcane | 2 | 35 | 9 | 0 | 10 | ranged | `ignore_armor` |
| flesh_golem | construct | 3 | 160 | 10 | 6 | 16 | melee | none |
| gargoyle | construct | 2 | 70 | 8 | 4 | 12 | melee | none |
| scarecrow | construct | 1 | 60 | 4 | 2 | 14 | melee | none |

### Synergies (active with ≥ 2 living units of the faction)
| Faction | Bonus |
|---|---|
| undead | +25% max HP to undead units |
| beast | +15% ATK to beast units |
| arcane | ability magnitudes +30% (heal, splash damage) |
| construct | +3 armor to construct units |

Synergy is recomputed whenever a unit spawns or dies.

### Combat
1. Each unit starts with a cooldown equal to its `speed`. Each tick, all cooldowns decrease by 1.
2. A unit whose cooldown reaches 0 acts and resets its cooldown to `speed`.
   - A **melee** unit may act only if it is among the first `front_line_size` living units of its team. Otherwise it waits with its cooldown held at 0.
   - A **ranged** unit may act from any position.
3. The target is the frontmost living enemy.
4. Damage = `max(1, atk - target_armor)`, unless `ignore_armor`. `dodge` is the only random element and uses the battle's seeded RNG.
5. All actions in a tick are computed from the state at the start of that tick, then applied together. After that, deaths and on-death triggers (summons) are resolved, and synergies are recomputed.
6. Summoned units are inserted at the back of the summoner's team.
7. The battle ends when one side has no living units (if both sides die in the same tick, it is a draw), or at `max_ticks` (draw).

### Intended imbalances (fixtures, keep in v0)
These match the Eurisko story of exploiting rules that look reasonable on paper:
- **Undead swarm**: summoned skeletons count toward the undead synergy and receive its HP bonus, so a necromancer with cheap undead keeps the synergy alive and refills the front line. This echoes Eurisko's 1981 TCS strategy of many cheap units (verify exact fleet details before quoting).
- **Armor wall**: flat armor plus the construct synergy brings many low-ATK attackers to the 1-damage floor. Cheap construct front lines beat teams that rely on fast, weak attackers.
- **Ghost hard-counter**: `ignore_armor` makes ghost the only efficient answer to the armor wall, which creates a rock-paper-scissors loop the engine should be able to map.

The test suite should check that these effects exist (for example, an armor wall beats a bat-swarm team) without fixing exact win rates.

### Measured balance of ruleset v0 (non-LLM hill-climb, 8 restarts)
- The mechanics work as designed: the armor wall beats a bat/skeleton team 10/10 seeds, the ghost team beats the armor wall 10/10, and the necromancer summons exactly 3 skeletons.
- The planted imbalances are **not** what dominates. Archetype scores: undead_swarm 0.15, armor_wall 0.40, arcane_backline 0.92.
- The real outlier is **pumpkin_mage**: it appears in 7 of 8 hill-climb optima. Ranged + 20 ATK + splash for 3 gold is under-costed. This is a better demo story than the planted one: the designer's intended exploit is not the broken one, and Neurisko finds the one that is.
- **Correction (2026-10-30, Spec 3 measurements):** the pumpkin_mage finding above does not hold up. It came from 8 hill-climb restarts against a saturated score. Under the engine's hall-of-fame-weighted score over 16 seeds, the robust outlier is **witch**: it is in 94% of top-5 designs, against 32% of random competitive designs, and every group of 4 seeds gives 0.90–1.00. pumpkin_mage is at 50% against a 39% baseline and swings between 0.25 and 0.70 across seed groups. Raising witch's cost from 2 to 3 drops its share to 45%. No pumpkin_mage nerf changed the picture.
- **Score saturation**: 8 of 8 optima reach 1.000 against the fixed gauntlet, so the score cannot rank strong designs. Spec 2 (engine) must handle this, for example by adding discovered champions to the gauntlet (hall of fame / co-evolution).

## Architecture

```
src/neurisko/
  engine/game.py              # Game protocol + shared result types (no Monster Mash imports)
  games/autobattler/
    rules.py                  # pydantic models, TOML loading, validation, hash
    design.py                 # validate, random design, mutations
    combat.py                 # simulate(): tick loop, abilities, synergies, events
    gauntlet.py               # archetypes + random pool, score()
    game.py                   # MonsterMash implements Game
    data/default.toml         # packaged default ruleset (loaded via importlib.resources)
  cli.py                      # `neurisko battle`, `neurisko score`
scripts/bench_autobattler.py
tests/autobattler/
```

### Game protocol (engine/game.py)
```python
class Game(Protocol[D]):
    name: str
    ruleset_hash: str
    def random_design(self, rng: random.Random) -> D: ...
    def validate(self, design: D) -> list[str]: ...           # empty list = valid
    def mutations(self, design: D, rng: random.Random) -> list[D]: ...
    def simulate(self, a: D, b: D, seed: int, log: bool = False) -> BattleResult: ...
    def score(self, design: D) -> ScoreReport: ...
    def describe(self, design: D) -> str: ...                 # compact text for LLM prompts
    def describe_rules(self) -> str: ...
```
`BattleResult` (winner, ticks, survivors, per-unit stats, optional events) and `ScoreReport` (score, per-opponent results) are plain dataclasses, so they serialize to JSON for run recording.

### Data model
- `Ruleset`, `UnitDef`, `Ability`, `Synergy`: pydantic v2 models. `Ability` is a discriminated union on `kind`, so unknown abilities fail validation (R1.2).
- Ruleset hash: SHA-256 of the canonical JSON dump of the model, first 12 hex characters.
- `Design`: `tuple[str, ...]` of unit ids, hashable so it can be used as a cache key.
- Combat state: a list of small mutable `Fighter` objects created per battle. `UnitDef` itself is never mutated.

### Performance approach
- No pydantic objects in the hot loop. At load time, the ruleset is compiled into plain tuples/slots classes.
- Skip idle ticks: jump directly to the next tick in which some cooldown reaches 0.
- `score()` caches results by `(ruleset_hash, design)`.
- If the benchmark misses 1,000 battles/s, profile first. Parallelize `score()` across processes only after that.

### Gauntlet
- 6 hand-written archetypes in the TOML file (balanced, undead swarm, armor wall, beast rush, arcane backline, ghost counter).
- Plus 18 random valid designs from `gauntlet_seed` (default 1981).
- Default: 3 seeds × 2 sides per opponent, so 144 battles per score.

## Error handling
- Ruleset errors: raise `RulesetError` with the field path and reason; the CLI prints it and exits with code 2.
- Invalid designs in the CLI: print all violations and exit with code 2.

## Testing strategy
- Rules: the default file loads; each kind of invalid file is rejected with a clear message; the hash is stable and changes when a stat changes.
- Designs: random designs are always valid (property test over many seeds); every mutation result is valid.
- Combat: same seed gives an identical log; swapping sides gives a mirrored result for seed-independent battles; draw at `max_ticks`; simultaneous kill gives a draw; each ability has a focused test.
- Fixtures: the armor wall beats a bat-swarm team; the necromancer summons at most 3 skeletons; summoned skeletons count toward the undead synergy.
- Score: in [0, 1] and reproducible.
- Benchmark: run by a script, not in the default test run.
