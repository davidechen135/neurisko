# Neurisko balance report

Game `tcs-lite`, ruleset `7db68d5b37df`. 8 engine runs x 12 generations, top 5 designs per run, baseline 3000 random competitive designs. Took 20 s.

## Summary

swarm is dominant: in 90% of top designs (range 60%-100% over 8 runs) against 9% of random designs, and in 7/8 champions. Champions lose 0.65 without it. Effective fix: components.hull.cost.0 1->2 (nothing is dominant afterwards; most common is guns_max at 57%).

## Part shares (units, or fleet traits)

| part | in top designs | range | in random designs | lift | champions | flags |
|---|---|---|---|---|---|---|
| swarm | `██████████████████··` 0.90 | 0.60–1.00 | 0.09 | 9.8 | 7/8 | DOMINANT |
| guns_max | `██████████████······` 0.68 | 0.00–1.00 | 0.48 | 1.4 | 6/8 |  |
| armour_max | `████████············` 0.38 | 0.00–0.80 | 0.49 | 0.8 | 3/8 |  |
| armour_none | `██████··············` 0.28 | 0.00–1.00 | 0.15 | 1.9 | 1/8 |  |
| drive_none | `█████···············` 0.25 | 0.00–1.00 | 0.15 | 1.6 | 1/8 |  |
| drive_max | `····················` 0.03 | 0.00–0.20 | 0.18 | 0.1 | 0/8 |  |
| elite | `····················` 0.00 | 0.00–0.00 | 0.00 | 0.0 | 0/8 |  |
| scuttle | `····················` 0.00 | 0.00–0.00 | 0.00 | 0.0 | 0/8 |  |

## swarm

**Dependence**: champions lose 0.651 on average when one swarm is replaced by the best alternative (7 champions).

**Heuristics that keep adding it** (highest worth across runs):

- `IF unspent>=5 THEN set_count(class=@largest, change=max)` worth 967, 161 applications, 98% improved, in 7 run(s)
- `IF always THEN set_count(class=@largest, change=max)` worth 926, 56 applications, 98% improved, in 3 run(s)
- `IF unspent>=5 THEN set_count(class=@smallest, change=max)` worth 869, 6 applications, 100% improved, in 1 run(s)
- `IF unspent>=5 THEN set_count(class=@cheapest, change=max)` worth 777, 25 applications, 88% improved, in 1 run(s)
- `IF always THEN add_class(template=minimal, count=1)` worth 714, 5 applications, 100% improved, in 1 run(s)

_Matchup comparison skipped: 6 distinct champions with swarm, 1 without (need 2 of each)._

**Candidate fixes** (each verified on 6 seeds; a second change is tried when the best single change only moves dominance to another unit):

| change | changed unit's share before → after | most common after | held-out champion | verdict |
|---|---|---|---|---|
| `components.hull.cost.0 1->2` | swarm 0.87 → 0.53 | guns_max 0.57 | 0.989 | ✅ effective (dropped opponents: mixed, swarm) |
| `limits.repeat_discount 0.8->0.95` | swarm 0.87 → 0.90 | swarm 0.90 | 0.974 | ❌ swarm is still dominant (share 0.90, lift 7.4); new dominant: armour_none (dropped opponents: mixed) |
| `limits.max_ships_per_class 99->40` | swarm 0.87 → 0.77 | guns_max 0.97 | 0.968 | ❌ swarm is still dominant (share 0.77, lift 8.5); new dominant: guns_max (dropped opponents: swarm) |

## Champions

- seed 0: `21x[h0 a0 g0 d0] + 4x[h3 a3 g3 d2] · 25 ships, cost 199/200` (held-out 0.941)
- seed 1: `47x[h0 a0 g0 d0] + 5x[h1 a0 g3 d1] + 2x[h2 a3 g2 d0] · 54 ships, cost 199.8/200` (held-out 0.936)
- seed 2: `70x[h0 a0 g0 d0] + 4x[h2 a1 g3 d1] · 74 ships, cost 199.2/200` (held-out 1.000)
- seed 3: `70x[h0 a0 g0 d0] + 4x[h2 a1 g3 d1] · 74 ships, cost 199.2/200` (held-out 1.000)
- seed 4: `99x[h0 a0 g0 d0] + 1x[h2 a1 g1 d2] · 100 ships, cost 188.8/200` (held-out 0.931)
- seed 5: `26x[h0 a0 g0 d0] + 7x[h2 a2 g3 d1] · 33 ships, cost 199/200` (held-out 0.971)
- seed 6: `65x[h0 a0 g0 d0] + 17x[h1 a0 g1 d0] · 82 ships, cost 199.2/200` (held-out 0.980)
- seed 7: `89x[h0 a0 g0 d0] + 1x[h3 a3 g3 d2] · 90 ships, cost 199.8/200` (held-out 0.941)
