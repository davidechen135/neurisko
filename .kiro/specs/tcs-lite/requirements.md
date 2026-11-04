# Requirements: TCS-lite ("Trillion Credit Squadron, lite")

## Introduction
TCS-lite is the homage that opens the demo video: a small fleet-design game in the spirit of the Traveller *Trillion Credit Squadron* tournament that Eurisko won in 1981 and 1982. It has two purposes:

1. **Tell the story with the real engine.** Under "1981" rules the engine should rediscover a swarm of many identical cheap ships. After a "1982" rule change it should adapt and find a new loophole involving scuttling its own ships.
2. **Show that the engine is game-agnostic.** The same engine, auditor, run recorder, web console and balance report run on a second game, with no game-specific code in the engine.

### Historical facts this spec relies on (checked 2026-11-01)
From Wikipedia, "Eurisko" and "Traveller Adventure 5: Trillion Credit Squadron", which cite M. Gladwell, *The New Yorker*, 2009-05-11, and *Journal of the Travellers' Aid Society* #10:
- In 1981 Eurisko's winning fleet had 96 ships, 75 of one "Eurisko class". It was described as a large number of small, stationary ships carrying many small weapons. The tournament rules were changed afterwards.
- In 1982 Eurisko won again, because the rules allowed it to destroy its own ships.
- Officials said the competition would be abolished if Eurisko won again, and Lenat retired it.

Sources disagree on details such as the armour, so public text states only the facts above. Before the video, check the Gladwell article (the most-cited secondary source).

### Copyright and licensing boundary
TCS-lite uses **our own rules, numbers and wording**. It does not copy text, tables or ship-design rules from Traveller books, and it does not use code from the unlicensed topher-brennan/tcs repository. Two general mechanics are reused as ideas, written in our own words: a budget with a discount for repeated identical ships, and the "last fleet able to fire wins" condition. Every UI and docs page about TCS-lite carries a one-line notice: "TCS-lite is an original simplified game inspired by Traveller: TCS; it is not affiliated with or derived from its rules text."

## Glossary
- **Ship class**: a ship design made of hull size, armour, guns and drive levels.
- **Fleet (design)**: up to 4 ship classes, each with a count, plus a doctrine.
- **Doctrine**: fleet-wide orders. In v1, `scuttle_disabled`, which removes own ships that can no longer fire.
- **Era**: a ruleset. `1981` and `1982` ship by default.

## Requirements

### R1. Rulesets
1. TCS-lite rulesets SHALL be TOML files with pydantic validation and a hash, like Monster Mash: budget, component cost tables, discount for repeat ships, round limit and era rules.
2. Two packaged rulesets SHALL exist: `tcs-1981.toml` and `tcs-1982.toml`. The 1982 file differs only in the era rules (R3.4), so that the rule change is visible as a small diff.

### R2. Fleets
1. A fleet SHALL be a hashable design with 1–4 classes, each with a count of 1 to `max_ships_per_class`, total cost ≤ budget, plus doctrine flags allowed by the era.
2. Cost: the first ship of a class pays a design fee plus its build cost; every further ship of that class pays `repeat_discount` × build cost.
3. Validation SHALL report every violated constraint.

### R3. Combat
1. Combat SHALL be deterministic given a seed, simultaneous within a round, and SHALL NOT call the LLM. It SHALL run at ≥ 2,000 battles/s for typical fleets on the dev machine.
2. Each round, every ship that can fire picks a target by a fixed rule. Hit chance depends on the target's drive. A hit's damage is reduced by armour, and accumulated damage disables guns, then the ship.
3. A fleet with no ship able to fire is out. The last fleet able to fire wins. The round limit gives a draw.
4. **1982 era rule**: after each round, a fleet whose disabled ships make up more than `max_disabled_fraction` of its ships withdraws and loses. If `scuttle_disabled` is allowed and set, the fleet removes its disabled ships at the end of each round, so they never count. This is our simplified analogue of the reported 1982 loophole, not the real 1982 rule.

### R4. Game protocol
1. TCS-lite SHALL implement the whole `Game` protocol: designs, mutations, simulate, score with extra opponents, features, action schema, apply_action, held-out, parts, baseline designs, patch candidates and with_patch.
2. Actions SHALL include changing a class's count, changing one component level, adding or removing a class, and toggling a doctrine flag.
3. Parts for the balance report SHALL be coarse fleet traits: `swarm` (≥ 30 ships), `elite` (≤ 4 ships), each component at its max or min level, and each doctrine flag.

### R5. Engine generality
1. The engine, auditor, run recorder, replay, web view/export, balance report and MCP tools SHALL work with any registered game. No module outside `games/` may import a concrete game, except the registry and the CLI default.
2. The CLI SHALL accept `--game {monster-mash,tcs-lite}` for `battle`, `score`, `evolve`, `report` and `export`. Run and report metadata SHALL record the game, and replay SHALL rebuild the right one.
3. The web console SHALL render a TCS-lite run with the same views. The battle player and the champion panel SHALL use a game-provided text description, not Monster Mash unit lists.

### R6. Seed heuristics
1. TCS-lite SHALL ship about 8 plain seed heuristics, for example "spend leftover budget on more of the cheapest class" and "add armour if win rate against the armoured archetype < 0.5".

### R7. Story acceptance (slow tests, measured facts, not loosened to pass)
1. Under 1981 rules, the default engine run SHALL produce champions in which the `swarm` part is dominant in the balance report (share ≥ 0.7, lift ≥ 1.8).
2. Under 1982 rules without scuttling, swarm champions SHALL lose most of their score against the 1981 champions' successors. With the doctrine available, the engine SHALL find champions that use `scuttle_disabled` in most runs.
3. If measurement shows the story does not emerge, the rule numbers are tuned, and every tuning step is recorded in the design notes. The tests are not changed to accept a different story.

### R8. Demo
1. `runs/demo/tcs-1981` and `runs/demo/tcs-1982` SHALL be recorded without the LLM, so anyone can reproduce them, and exported to a "TCS" view in the static site with the era diff shown.
