# Kiro development notes

Running log of how Kiro was used, for the demo video, Devpost description and blog post.

## 2026-10-30 · Spec 1: Monster Mash simulator

**Steering**: `product.md`, `tech.md` and `safety.md` were written before any code. They fixed the key architecture rule (simulators never call the LLM) and the rule that historical claims must be checked against a source before publishing.

**Spec**: requirements (EARS-style acceptance criteria), then design, then 10 tasks, all implemented in one session.

**Hooks**: ruff on every `.py` save; full pytest after each spec task.

**Findings during implementation** (the spec design was updated each time):
- `max_ticks = 200` made 18% of random battles draws. Measured 200/400/600/1000, chose 600 (about 3.5% draws; median battle 90 ticks).
- The first gauntlet included tiny random teams, so many designs scored 1.000. Random opponents are now filtered to "competitive" teams (3+ units, at most 1 gold unspent).
- A non-LLM hill-climb showed the planted imbalances are not the dominant ones. Undead swarm scores 0.15. **pumpkin_mage** (under-costed ranged splash) appears in 7 of 8 optima. This is a better demo story: the tool finds the exploit the designer didn't plant.
- Score still saturates at 1.000 for strong designs. Carried over to Spec 2 (hall of fame / co-evolving gauntlet).

**Result**: 49 tests; 14,874 battles/s (target 1,000); one gauntlet score = 144 battles in about 15 ms.

## 2026-10-30 · Spec 2 written: Eurisko engine

- Probed local `qwen2.5:14b` with the planned heuristic DSL before writing the design: 9 of 9 proposed heuristics were valid; about 10 s per call when warm. This decided that the LLM is used for one meta-heuristic (Invent) only, and everything else stays in code.
- H59 source found: Wikipedia "Reward hacking" names H59 as the parasitic heuristic that took unearned partial credit. Primary source to check before the video: Lenat, *EURISKO: A Program That Learns New Heuristics and Domain Concepts*, Artificial Intelligence 21 (1983).
- Design decision: the engine reproduces the H59 pattern on purpose (lineage credit plus a Clone meta-heuristic), so the auditor's fix can be shown with it switched off and on.
