# Devpost submission: Neurisko

Paste-ready text for https://kiroween.devpost.com/. Every number is from this repository (docs/KIRO_NOTES.md, docs/BASELINE.md, reports/demo/).

---

**Project name:** Neurisko

**Tagline:** Eurisko (1981), resurrected with an LLM, to find a game's exploits before the players do.

**Category:** Resurrection

**Links**
- Code (MIT): https://github.com/davidechen135/neurisko
- Live replay, no install: https://davidechen135.github.io/neurisko/
- Demo video: _YouTube link_

**Built with:** python, fastapi, server-sent-events, javascript, ollama, qwen, mcp, kiro, playwright, ffmpeg, kokoro-tts, github-pages

---

## Inspiration

In 1981 a program called Eurisko won a naval war-game tournament with a fleet of 96 ships, 75 of them one cheap design. The organisers changed the rules. In 1982 it won again, because the new rules let it destroy its own ships. Eurisko was made of heuristics that rewrote other heuristics. It also produced a famous early case of reward hacking: a heuristic called H59 climbed to the top by taking credit for other heuristics' discoveries.

Lenat never released the code. But "find the exploit the rule-writer didn't see" is exactly what game designers need before launch, and today's LLMs can write heuristics in plain English. So we brought Eurisko back.

## What it does

Neurisko takes a game's ruleset and:

1. **Evolves strong designs** with a Eurisko engine. Its heuristics are natural-language if-then rules with a worth score, and a local LLM invents new ones from the evidence. Worth comes only from measured battles.
2. **Finds what dominates.** Each unit's share of strong designs is compared with a random baseline, across 8 seeds.
3. **Tests fixes by evolving again**, and writes a balance report. On our Halloween auto-battler, *Monster Mash*, the witch is in 95% of strong teams against 31% of random ones. No single change fixed it. The report found a two-step fix that does: witch cost 2→3 plus flesh golem attack 10→8.
4. **Guards against its own reward hacking.** We rebuilt the H59 failure on purpose. With the auditor off, a Clone meta-heuristic tops the worth table in 8 of 8 seeds. With the auditor on, it is caught and demoted every time.

It also relives its own history. On *TCS-lite*, a small fleet game we wrote in the spirit of the 1981 tournament, the engine starts with heuristics that only say "build good warships". It rediscovers the cheap swarm under 1981 rules, and scuttling its own disabled ships under 1982 rules (8/8 runs).

Designers use it from a 1981-terminal web console, which has live runs, replays and animated battles for both games. They can also use it inside Kiro, where Neurisko is an MCP server: open a ruleset, ask "is this balanced?", and Kiro measures before it answers.

## How we built it

- **Engine:** Python 3.12. Units, heuristics, meta-heuristics (Specialize, Generalize, Retarget, Clone, LLM Invent), an agenda and credit assignment, behind a game protocol so the same engine runs two very different games.
- **Simulators:** pure, seeded Python with no LLM calls. Monster Mash runs about 15,000 battles per second.
- **LLM:** any OpenAI-compatible endpoint. We used local Ollama `qwen2.5:14b`, and every output is schema-validated. Runs are recorded and replay without an LLM.
- **Console:** FastAPI with SSE for live runs, and vanilla JS. The same frontend renders the static GitHub Pages export.
- **MCP server:** `check_ruleset`, `simulate_battle`, `score_team`, `quick_balance`, `verify_patch`, `start_report`/`report_status`, and a `balance_review` prompt.
- **Video:** generated from the real console with Playwright, local Kokoro TTS narration and an original synthesised score.

## How we used Kiro

- **Specs for everything.** Six specs (simulator, engine, balance report, web UI, MCP server, TCS-lite) each went requirements → design → tasks before code. When a measurement proved a design wrong, we updated the spec's notes rather than letting code drift. One requirement, "report the baseline comparison whichever method wins", kept the pitch honest when plain hill-climbing with a hall of fame tied our engine.
- **Steering.** `tech.md` fixed the core architecture rule: simulators never call the LLM. `product.md` requires a source for every historical claim. `safety.md` sets LLM budgets. `balance.md` is a `fileMatch` steering file that activates only when a ruleset is open and tells Kiro to measure, not guess.
- **Hooks.** Ruff on every Python save, the full test suite after every spec task (slow and live-LLM tests moved behind markers when it got slow), and a balance re-check whenever a ruleset file is saved.
- **MCP, end to end.** In a real Kiro session, Kiro ran the Neurisko tools and recommended a fix that a 4-seed quick check marked effective. The 6-seed full report showed it only moved the problem. We changed the tool note and the steering so that a quick "effective" is only a candidate. Kiro's own guardrail is now part of the product.

## Challenges we ran into

- **The system hacked its own reward, twice.** We built an auditor for H59-style credit theft, and the engine found a second inflation bug of its own: a plain seed heuristic hit worth 1000 by being re-credited for the same move every generation.
- **Small samples lied, three times**: "pumpkin_mage is the outlier", "witch cost 2→3 fixes it", and Kiro's quick-check false positive. Each time, more seeds caught it. That is why every claim in the report carries a random baseline and the spread across seeds.
- **Making history emerge, not scripting it.** The first TCS-lite numbers made the 1982 rule useless. A grid search tuned the game until the swarm, and then scuttling, appeared on their own, from heuristics that mention neither.

## Accomplishments that we're proud of

- A working Eurisko-style system that rediscovers both of Eurisko's tournament exploits.
- A reproducible H59 demonstration with an auditor that catches it in 8/8 seeds.
- Honest results. At equal budget the engine ties hill-climbing with the same hall of fame (0.826 vs 0.838), and we say so. Its value is explanation: readable, ranked, audited rules and verified fixes.
- 181 tests (174 fast by default, plus slow and live-LLM ones), including a test that runs the JavaScript reducer under Node against the Python run record.

## What we learned

- Measure before believing, including when the believer is an AI assistant.
- The ideas of 1981 hold up well. What was missing was a cheap way to write heuristics, and LLMs supply it.

## What's next

- Import rulesets from other auto-battlers and card games.
- A save-to-report loop for designers inside Kiro.
- Co-evolving opponents, so the gauntlet keeps up with the meta.

---

## Submission checklist

- [x] Public repo with an MIT license and the `.kiro/` directory (specs, steering, hooks, settings)
- [x] Working app: CLI, web console, MCP server, and the live replay site
- [x] Demo video under 3 minutes (2:58), showing the problem, end-to-end flow and Kiro usage
- [ ] Upload the video to YouTube (public or unlisted), then add the link here and in README.md
- [ ] Push to `main` so GitHub Pages deploys the new battle arena
- [ ] Fill in the Devpost form with this text, choose **Resurrection**, and add your Kiro user ID
- [ ] Optional: blog post (2,000 Kiro credits for the first 100) and a `#Kiroween26` social post
