# Neurisko balance report

Game `tcs-lite`, ruleset `65b60296e58d`. 8 engine runs x 12 generations, top 5 designs per run, baseline 3000 random competitive designs. Took 25 s.

## Summary

scuttle is dominant: in 97% of top designs (range 80%-100% over 8 runs) against 30% of random designs, and in 8/8 champions. Champions lose 0.41 without it. Effective fix: era.max_disabled_fraction 0.3->0.6 + components.hull.cost.0 1->2 (nothing is dominant afterwards; most common is guns_max at 73%).

## Part shares (units, or fleet traits)

| part | in top designs | range | in random designs | lift | champions | flags |
|---|---|---|---|---|---|---|
| scuttle | `████████████████████` 0.97 | 0.80–1.00 | 0.30 | 3.3 | 8/8 | DOMINANT |
| guns_max | `████████████········` 0.62 | 0.00–1.00 | 0.50 | 1.3 | 6/8 |  |
| swarm | `████████████········` 0.60 | 0.00–1.00 | 0.09 | 6.6 | 5/8 |  |
| armour_none | `██████··············` 0.30 | 0.00–1.00 | 0.14 | 2.1 | 2/8 |  |
| armour_max | `██████··············` 0.28 | 0.00–0.80 | 0.49 | 0.6 | 2/8 |  |
| drive_none | `████················` 0.23 | 0.00–1.00 | 0.15 | 1.5 | 1/8 |  |
| drive_max | `██··················` 0.07 | 0.00–0.40 | 0.17 | 0.5 | 2/8 |  |
| elite | `····················` 0.00 | 0.00–0.00 | 0.00 | 0.0 | 0/8 |  |

## scuttle

**Dependence**: champions lose 0.406 on average when one scuttle is replaced by the best alternative (8 champions).

_Matchup comparison skipped: 7 distinct champions with scuttle, 0 without (need 2 of each)._

**Candidate fixes** (each verified on 6 seeds; a second change is tried when the best single change only moves dominance to another unit):

| change | changed unit's share before → after | most common after | held-out champion | verdict |
|---|---|---|---|---|
| `era.max_disabled_fraction 0.3->0.6 + components.hull.cost.0 1->2` | swarm 0.93 → 0.43 | guns_max 0.73 | 0.979 | ✅ effective (dropped opponents: mixed, swarm) |
| `era.max_disabled_fraction 0.3->0.6` | scuttle 1.00 → 0.33 | swarm 0.93 | 0.940 | ❌ new dominant: swarm |
| `components.hull.cost.0 1->2` | scuttle 1.00 → 1.00 | scuttle 1.00 | 0.991 | ❌ scuttle is still dominant (share 1.00, lift 3.4) (dropped opponents: mixed, swarm) |
| `era.max_disabled_fraction 0.3->0.6 + limits.max_ships_per_class 99->40` | swarm 0.93 → 0.43 | guns_max 1.00 | 0.937 | ❌ new dominant: guns_max (dropped opponents: swarm) |
| `era.max_disabled_fraction 0.3->0.6 + limits.repeat_discount 0.8->0.95` | swarm 0.93 → 0.83 | swarm 0.83 | 0.920 | ❌ swarm is still dominant (share 0.83, lift 7.3) (dropped opponents: mixed) |

## Champions

- seed 0: `45x[h0 a0 g0 d0] + 4x[h3 a1 g3 d1] · scuttle_disabled · 49 ships, cost 200/200` (held-out 0.990)
- seed 1: `97x[h0 a0 g0 d0] + 1x[h3 a0 g3 d1] · scuttle_disabled · 98 ships, cost 199.6/200` (held-out 1.000)
- seed 2: `5x[h3 a2 g3 d3] · scuttle_disabled · 5 ships, cost 195/200` (held-out 0.995)
- seed 3: `60x[h0 a0 g1 d0] · scuttle_disabled · 60 ships, cost 198.8/200` (held-out 0.980)
- seed 4: `66x[h0 a0 g0 d0] + 5x[h1 a0 g2 d0] + 1x[h3 a3 g2 d1] · scuttle_disabled · 72 ships, cost 199.8/200` (held-out 1.000)
- seed 5: `5x[h3 a2 g3 d3] · scuttle_disabled · 5 ships, cost 195/200` (held-out 0.995)
- seed 6: `59x[h0 a0 g0 d0] + 5x[h2 a1 g3 d1] · scuttle_disabled · 64 ships, cost 199.2/200` (held-out 1.000)
- seed 7: `5x[h3 a3 g3 d2] · scuttle_disabled · 5 ships, cost 195/200` (held-out 0.976)
