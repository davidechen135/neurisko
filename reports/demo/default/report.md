# Neurisko balance report

Game `monster-mash`, ruleset `f22da09334d3`. 8 engine runs x 12 generations, top 5 designs per run, baseline 3000 random competitive designs. Took 124 s.

## Summary

witch is dominant: in 95% of top designs (range 60%-100% over 8 runs) against 31% of random designs, and in 7/8 champions. Champions lose 0.21 without it. Effective fix: witch.cost 2->3 + flesh_golem.atk 10->8 (no unit is dominant afterwards; most common unit is witch at 67%).

Rarely used by strong designs: skeleton, necromancer.

**LLM-written summary** (qwen2.5:14b, numbers checked against the measurements):

> Recommended changes: Increase witch cost from 2 to 3 and reduce flesh_golem attack from 10 to 8. This change makes no unit dominant, with witch at 67%. Other tested changes were not effective: witch alone did not address dominance, and increasing flesh_golem cost to 4 created a dominant werewolf. Reducing witch's ability amount or health was also ineffective as witch remained dominant. Underused units include skeleton and necromancer.

## Unit shares

| unit | in top designs | range | in random designs | lift | champions | flags |
|---|---|---|---|---|---|---|
| witch | `███████████████████·` 0.95 | 0.60–1.00 | 0.31 | 3.0 | 7/8 | DOMINANT |
| werewolf | `██████████████······` 0.68 | 0.20–1.00 | 0.32 | 2.1 | 6/8 |  |
| flesh_golem | `██████████··········` 0.53 | 0.00–1.00 | 0.40 | 1.3 | 4/8 |  |
| ghost | `████████············` 0.42 | 0.00–1.00 | 0.31 | 1.4 | 4/8 |  |
| pumpkin_mage | `███████·············` 0.35 | 0.00–1.00 | 0.40 | 0.9 | 4/8 |  |
| gargoyle | `██████··············` 0.30 | 0.00–0.80 | 0.33 | 0.9 | 2/8 |  |
| hellhound | `████················` 0.17 | 0.00–1.00 | 0.40 | 0.4 | 1/8 |  |
| scarecrow | `████················` 0.17 | 0.00–0.80 | 0.27 | 0.7 | 1/8 |  |
| zombie | `██··················` 0.10 | 0.00–0.40 | 0.28 | 0.4 | 0/8 |  |
| bat_swarm | `██··················` 0.10 | 0.00–0.60 | 0.27 | 0.4 | 0/8 |  |
| skeleton | `····················` 0.03 | 0.00–0.20 | 0.28 | 0.1 | 0/8 | UNDERUSED |
| necromancer | `····················` 0.00 | 0.00–0.00 | 0.39 | 0.0 | 0/8 | UNDERUSED |

## witch

**Dependence**: champions lose 0.213 on average when one witch is replaced by the best alternative (7 champions).

**Heuristics that keep adding it** (highest worth across runs):

- `IF winrate_vs_beast_rush<0.5 THEN replace_unit(old=@cheapest, new=witch)` worth 844, 39 applications, 85% improved, in 2 run(s)
- `IF n_ranged==0 THEN replace_unit(old=@cheapest, new=witch)` worth 773, 109 applications, 67% improved, in 8 run(s)
- `IF always THEN replace_unit(old=@cheapest, new=witch)` worth 724, 81 applications, 64% improved, in 3 run(s)
- `IF n_ranged==0 THEN replace_unit(old=zombie, new=witch)` worth 600, 1 applications, 100% improved, in 1 run(s)
- `IF n_ranged==0 AND front_armor<=0 THEN replace_unit(old=@cheapest, new=witch)` worth 600, 3 applications, 33% improved, in 1 run(s)

_Matchup comparison skipped: 5 distinct champions with witch, 1 without (need 2 of each)._

**Candidate fixes** (each verified on 6 seeds; a second change is tried when the best single change only moves dominance to another unit):

| change | changed unit's share before → after | most common after | held-out champion | verdict |
|---|---|---|---|---|
| `witch.cost 2->3 + flesh_golem.atk 10->8` | flesh_golem 0.73 → 0.37 | witch 0.67 | 0.988 | ✅ effective (dropped opponents: arcane_backline) |
| `witch.cost 2->3` | witch 0.93 → 0.40 | flesh_golem 0.73 | 0.990 | ❌ new dominant: flesh_golem (dropped opponents: arcane_backline) |
| `witch.cost 2->3 + flesh_golem.cost 3->4` | flesh_golem 0.73 → 0.10 | werewolf 0.80 | 0.990 | ❌ new dominant: werewolf (dropped opponents: arcane_backline) |
| `witch.ability.amount 12->8` | witch 0.93 → 0.77 | witch 0.77 | 1.000 | ❌ witch is still dominant (share 0.77, lift 2.5) |
| `witch.hp 45->36` | witch 0.93 → 0.87 | witch 0.87 | 0.997 | ❌ witch is still dominant (share 0.87, lift 2.8); new dominant: flesh_golem, pumpkin_mage |

## Rarely used

skeleton, necromancer

## Champions

- seed 0: `flesh_golem > werewolf > pumpkin_mage > witch` (held-out 1.000)
- seed 1: `flesh_golem > gargoyle > pumpkin_mage > ghost` (held-out 1.000)
- seed 2: `werewolf > werewolf > ghost > witch > witch` (held-out 1.000)
- seed 3: `gargoyle > scarecrow > witch > pumpkin_mage > witch` (held-out 1.000)
- seed 4: `flesh_golem > werewolf > pumpkin_mage > witch` (held-out 1.000)
- seed 5: `werewolf > werewolf > witch > ghost > witch` (held-out 1.000)
- seed 6: `flesh_golem > hellhound > werewolf > witch` (held-out 0.979)
- seed 7: `werewolf > werewolf > ghost > witch > witch` (held-out 1.000)
