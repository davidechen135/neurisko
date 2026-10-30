# Product: Neurisko

## One-liner
Eurisko (Douglas Lenat, ~1976–1983) resurrected with LLMs. A system of self-improving heuristics that searches a game's design space for dominant strategies and balance exploits, then explains them to the game designer.

## Hackathon context
- Kiroween 2026, track: **Resurrection**. Deadline 2026-12-04 14:00 PT. Rules: `docs/HACKATHON_RULES.md`.
- Judging: Impact, Kiro usage depth, Design, Innovation, Presentation. Favor a polished small product over a large rough one.

## Target user
Indie game and tabletop designers who need to find overpowered strategies before players do.

## Historical framing (keep accurate)
- Eurisko was made of heuristics, including heuristics about using and modifying heuristics (meta-heuristics). Each heuristic carried a "worth" score.
- It won the Traveller Trillion Credit Squadron (TCS) tournament in 1981 and 1982 by exploiting the rules; organizers changed the rules after the first win.
- A known failure mode: a parasitic heuristic raised its own worth by claiming credit for discoveries it did not make. We treat this as early reward hacking and build an auditor against it.
- Source circa 1981 was later recovered from the SAILDART archive (github.com/white-flame/eurisko), without the TCS domain heuristics.
- Before publishing any historical claim in UI, video or Devpost text, verify it against a primary source and note the source.

## Scope
1. Auto-battler game (primary domain): budget-constrained team building + deterministic auto-combat.
2. TCS-lite (homage, video opener): our own simplified ship/fleet rules. Never copy Traveller rulebook text or the unlicensed topher-brennan/tcs code.
3. Output: a balance report (dominant compositions, exploited rule or stat, suggested fix, before/after rerun).

## Out of scope
- Agents that modify Neurisko's own source code.
- Running LLM-generated code outside the sandbox.
- Multiplayer, accounts, payments.
