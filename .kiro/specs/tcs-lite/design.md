# Design: TCS-lite

## Rules (v0 numbers, to be tuned by measurement, R7.3)

### Components (levels 0–3)
| component | effect | build cost by level 0/1/2/3 |
|---|---|---|
| hull | ship size: hit points 2/4/8/16 and the slots available (level+1) | 1 / 3 / 8 / 20 |
| armour | subtracts 0/1/2/3 from each hit's damage | 0 / 2 / 5 / 10 |
| guns | number of shots per round 1/2/3/4 (needs hull slots) | 1 / 3 / 6 / 10 |
| drive | enemy hit chance 0.8/0.65/0.5/0.35 | 0 / 2 / 5 / 10 |

- A ship's guns + armour + drive levels may not exceed its hull slots × 2. This keeps tiny ships simple.
- Shot damage: 2 minus target armour, minimum 0.
- A ship is **disabled** (cannot fire) when it has taken ≥ half its hit points. It is **destroyed** at full hit points. Disabled ships still absorb fire as targets.
- Targeting: each shot goes to a uniformly random living enemy ship, using a seeded RNG. Because of this, many cheap ships soak up fire.

### Fleet economy
- `budget = 200`, `design_fee = 6` per class, `repeat_discount = 0.8`, `max_ships_per_class = 99`, `max_classes = 4`, `max_rounds = 30`.
- Intended loophole under 1981 rules: a minimal ship (hull 0, guns 0, everything else 0) costs 2, then 1.6 per repeat. About 120 of them have about 120 guns and take about 120 shots to stop, while an "elite" fleet of a few big ships fires a few dozen shots per round. Random targeting spreads the elite fleet's fire, so the swarm wins.
- The **1982 era** adds `max_disabled_fraction = 0.5`: a fleet that is more than half disabled withdraws and loses. A swarm is disabled quickly, so it now loses. The engine's way out is the `scuttle_disabled` doctrine (allowed in 1982), because disabled ships are removed and never count. The share of disabled ships then stays low and the swarm works again. This mirrors "the rules permitted the program to destroy its own ships".

### Archetypes (fixed opponents, per era file)
`elite` (3 big armoured ships), `line` (10 medium ships), `swarm` (≈100 minimal ships), `fast` (fast medium ships), `mixed` (one class of each), plus 12 random competitive fleets.

## Design type
```python
ShipClass = tuple[int, int, int, int]          # hull, armour, guns, drive
Fleet = tuple[tuple[tuple[ShipClass, int], ...], tuple[str, ...]]   # sorted classes with counts, doctrine flags
```
Classes are kept sorted, so equal fleets hash equally. `describe(fleet)` gives `"96x[h0 a0 g0 d0] + 3x[h3 a3 g3 d1] · scuttle"`.

## Features (for heuristic conditions)
`n_ships`, `n_classes`, `unspent`, `total_guns`, `total_hp`, `mean_armour`, `mean_drive`, `max_hull`, `share_minimal` (ships with hull 0), `doctrine_scuttle`, and `winrate_vs_<archetype>`.

## Actions
| kind | params |
|---|---|
| `set_count` | `class` ∈ {@largest, @smallest, @cheapest, @most_expensive}, `change` ∈ {+1, +5, +20, -1, -5, max} (`max` = as many as the budget allows) |
| `upgrade` / `downgrade` | `class` as above, `component` ∈ {hull, armour, guns, drive} |
| `add_class` | `template` ∈ {minimal, gunboat, tank, fast, capital}, `count` ∈ {1, 5, 20, max} |
| `remove_class` | `class` as above |
| `toggle_doctrine` | `flag` ∈ {scuttle_disabled} (applies only if the era allows it) |

## Parts (balance report)
`swarm`, `elite`, `armour_max`, `armour_none`, `guns_max`, `drive_max`, `drive_none`, `scuttle`. Parts and patch candidates are defined over the era rules and costs (e.g. `repeat_discount 0.8→0.9`, `design_fee 6→12`, `max_disabled_fraction 0.5→0.3`), not over units. This needs a small generalisation of `Patch`: `target` may be `"rules"`, with `field` a dotted path into the ruleset.

## Engine generality changes (R5)
- `games/registry.py`: `GAMES = {"monster-mash": ..., "tcs-lite": ...}`; `load_game(name, ruleset_path, **settings)` and `make_game(name, ruleset_json, settings)`.
- `runs/session.py`: take a `game` name; `meta.json` records it; replay uses it. Seed heuristics come from the game (`game.seed_rules()`, a protocol addition).
- `web/view.py`: `featured_battles` uses `game.featured_opponents(champion)` (protocol addition) instead of reading `game.gauntlet` directly. Battle logs use `game.describe_event` (protocol addition), so the player shows TCS events ("A3 fires at B17: 2 dmg", "B17 disabled", "A scuttles 4").
- `report/`: `Patch.text()` handles `target == "rules"`.
- MCP: unchanged in v1 (Monster Mash only). Out of scope.
- CLI: `--game` flag; `--ruleset` defaults to the game's packaged default.

## Performance plan
Fleets of ~120 ships × 30 rounds are heavier than Monster Mash. Ships are stored as parallel lists (hp, damage, guns, armour, drive). Fire is resolved per round in aggregate per shooter class. Target sampling uses `rng.choices` over living indices, rebuilt each round. Target: ≥ 2,000 battles/s. Measure in the first task. If it is missed, cap fleets at 99 ships total before optimising further.

## Testing strategy
- Rules: both era files load; the 1982 file differs from 1981 only in era fields (checked by diffing the dumps).
- Fleets: costs (design fee and repeat discount) computed by hand for 3 fleets; validation messages; canonical ordering makes equal fleets hash equally.
- Combat: determinism; side symmetry; disable/destroy thresholds; armour damage floor; withdrawal at `max_disabled_fraction` (1982 only); scuttling removes disabled ships and prevents withdrawal.
- Protocol: the conformance test shared with Monster Mash (moved to `tests/engine/test_protocol.py` and parametrised over games).
- Story (slow): R7.1 and R7.2 with the default engine config.
- Web: export of a TCS run renders (node reducer test reused; manifest names the game).
