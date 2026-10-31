# Design: Web UI ("The Lisp Machine")

## Screen layout (1280×720)
```
┌ NEURISKO ── EURISKO (LENAT 1981) RESURRECTED ─────────── run qwen-s0 ── GEN 14/20 ┐
│ ┌ SCORE ──────────────────────────────┐ ┌ HEURISTIC UNITS (by worth) ───────────┐ │
│ │ 1.0 ┤            ╭──────╮ ▒ held-out│ │ M1 Invent      ████████▉ 905  LLM     │ │
│ │ 0.8 ┤     ╭──────╯      ╰─ █ gauntl.│ │ M5 Clone       ███▏      300 PARASITE │ │
│ │ 0.6 ┼─────╯                         │ │ H27 ████████▉ 998 M1 IF unspent>=1 ... │ │
│ └─────────────────────────────────────┘ │ H65 ████████▋ 972 M1 IF winrate_vs_... │ │
│ ┌ AUDIT ─────────────────────────────┐  └────────────────────────────────────────┘ │
│ │ G03 DUPLICATE  H14 = H2  revoked .5│  ┌ CHAMPION ─────────────────────────────┐ │
│ │ G03 PARASITE   M5 tainted 1.00→300 │  │ werewolf > hellhound > bat_swarm >    │ │
│ └────────────────────────────────────┘  │ witch > witch      [▶ PLAY BATTLE]    │ │
│ [◀] ════════════●═══════ [▶]  GEN 14   [ RUN | REPORT | H59 | LLM ]   [CRT ON]  │
└───────────────────────────────────────────────────────────────────────────────────┘
```
Tabs: **RUN** (above), **REPORT** (balance report), **H59** (with/without auditor), **LLM** (Invent transcripts).

## Palette
| token | colour | use | contrast on #0b0f0b |
|---|---|---|---|
| `--bg` | #0b0f0b | background | – |
| `--fg` | #39ff7a | main text | about 14:1 |
| `--dim` | #2bb35a | secondary text | ≥ 7:1 (checked by test) |
| `--amber` | #ffb000 | warnings, LLM labels | about 11:1 |
| `--red` | #ff5f5f | PARASITE, failed patches | ≥ 6:1 |
Exact ratios are computed by the palette test (R6.3); if one fails, the colour is adjusted, not the threshold. Font: the system monospace stack, with no web font downloads. Effects in CSS only: scanline gradient overlay, slight text glow and an optional flicker keyframe, all disabled under `prefers-reduced-motion` or the CRT toggle (stored in `localStorage`).

## Data flow
```
events.jsonl ──► compact_event() ──► export: data/run.json  ─┐
                       │                                      ├─► reducer.js ──► state ──► views
live Recorder ─────────┴──► SSE  /api/live/{id}/events  ──────┘
```
- `web/view.py: compact_event(e) -> dict | None` keeps what the UI needs. `generation` without the `population` list, but with the top 5. `heuristic_created` as id, name, text, origin. `audit`, `hof_*`, `retired`, `run_*` unchanged. `llm_call` with the messages trimmed to the evidence part plus the reply. `applied` dropped and replaced by per-generation counts already in `generation`. This keeps the demo run around 100–200 KB; the test enforces < 1 MB.
- `reducer.js: reduce(state, event)` is pure. The scrubber rebuilds state by reducing events with `gen <= g` (cached snapshots every 5 generations).
- `run.json` = `{"meta": {...}, "events": [...], "battles": {key: log}}`.

## Precomputed battles (export)
For the final champion: against its 3 worst gauntlet matchups and the strongest hall-of-fame member, on seed 0. Each log is the `BattleResult` with its event list. In live mode the player calls `/api/battle` instead.

## Backend (web/app.py)
| route | purpose |
|---|---|
| `GET /` and `/static/*` | the same frontend files as the export |
| `GET /api/runs` | recorded runs (id, seed, generations, llm, auditor) |
| `GET /api/runs/{id}` | view model of a recorded run |
| `GET /api/reports/{id}` | `report.json` |
| `POST /api/live` | start a live run; body validated by a pydantic model; 409 if one is running |
| `GET /api/live/{id}/events` | SSE: compacted events; supports `Last-Event-ID` |
| `GET /api/battle?a=&b=&seed=` | simulate; designs validated with `game.validate`; `0 ≤ seed < 2^31` |

Live runs execute in a background thread. The `Recorder` gets a listener list. Each emitted event is appended to the run's in-memory buffer; SSE consumers read from the buffer by index (the event id is the index), so reconnects resume and slow clients do not block the run. SSE uses FastAPI's built-in `EventSourceResponse` (`fastapi.sse`, FastAPI 0.162); its exact API is checked when implementing. A keep-alive comment goes out every 15 s.

Path safety: `resolve_run(id)` checks the id regex, then `(RUNS_DIR / id).resolve()` must be inside `RUNS_DIR.resolve()`.

## H59 tab data
Two demo runs with the same seed and config, one with `--no-auditor`: `runs/demo/h59-off` and `runs/demo/h59-on` (no LLM, so they are reproducible by anyone). The export includes both as `data/h59.json` with only the meta-heuristic worth per generation and the audit events.

## Frontend files (src/neurisko/web/static/)
```
index.html     # semantic layout: header, nav (tabs), main panels, footer with sources
style.css      # palette, CRT effects, grid layout, focus styles, reduced-motion
app.js         # data source selection (static file vs API), tab routing (hash), scrubber
reducer.js     # pure reducer, unit-testable with node if available (not required)
views/*.js     # chart.js, worth.js, audit.js, llm.js, battle.js, report.js, h59.js
```
Rendering uses `textContent` and DOM APIs only, never `innerHTML` with run data, because LLM text is untrusted.

## Footer content
Sources for the historical claims, as required by product steering: the Eurisko article (Lenat 1983, Artificial Intelligence 21), the H59 reference (Wikipedia, "Reward hacking", to be checked against the primary source before publishing) and the SAILDART recovery (github.com/white-flame/eurisko).

## Deployment (.github/workflows/pages.yml)
On push to `main`: set up uv, `uv sync`, `uv run neurisko export runs/demo/qwen-s0 --report reports/demo/default --h59 runs/demo/h59-off runs/demo/h59-on --out site`, then upload the Pages artifact and deploy. Turning on Pages with "GitHub Actions" as source is a repository setting; it is done once, with the user's approval.

## Testing strategy
- `tests/web/test_api.py`: start a live run with a tiny config and the fake LLM; second start gives 409; SSE returns `run_start` … `run_end`; reconnect with `Last-Event-ID` resumes; `../etc` and `a/b` ids give 404/422; battle endpoint rejects an invalid design.
- `tests/web/test_export.py`: export of a tiny recorded run; file list; size; Python port of the reducer's final-state fields (best design, worth table) matches the recorder's final `generation` event.
- `tests/web/test_palette.py`: parse `style.css` variables, compute WCAG contrast, assert ≥ 4.5 (≥ 7 for `--fg`).
- Manual checklist (recorded in tasks): keyboard-only walkthrough, reduced-motion on, 390 px width, 1280×720 screenshot.

## Implementation notes (2026-10-31)
1. **Manifest.** Both modes start from `data/manifest.json`: a static file in the export, a route in the live server. It holds relative URLs for the run, report and H59 data, and in live mode the id of a run in progress, so a reloaded page re-attaches to it.
2. **Scrubbing without snapshots.** `reducer.js: at(state, g)` derives every view from events with `gen <= g`; runs are small enough (about 1,600 compact events) that no snapshot cache is needed.
3. **Parasite flags can clear.** The worth table first showed `PARASITE` on M2 at generation 20 although later audits found its credit clean again (worth back to 839). The flag now reflects the latest parasite audit: `PARASITE` if still demoted, otherwise `PARASITE G03, CLEARED`.
4. **H59 tab data.** `scripts/record_h59_demo.py` records `runs/demo/h59-off` and `h59-on` with the H59 test configuration (seed 0, 9 generations): M5 ends at worth 887 and rank 1 without the auditor, and at 300 with the auditor, flagged at G03, G06 and G09. The chart shows M5 against the best of M1–M4, because five overlapping series were unreadable.
5. **Bugs found with headless Chrome screenshots**, not by tests: the nav class `.bar` collided with the worth-bar class; `[hidden]` was overridden by `display: flex`; `Element.append(array)` printed `[object HTMLOptionElement]`. A `fill()` helper now flattens children everywhere.
6. **SSE.** FastAPI's `EventSourceResponse` with an async generator; the event id is the index into the run's compact-event buffer, so `Last-Event-ID` resumes exactly. The run lookup is a dependency so an unknown id still gets a 404 before streaming starts. `app.py` cannot use `from __future__ import annotations`, because FastAPI must resolve the closure dependency.
7. **Data size.** The demo export is 182 kB (run) + 50 kB (report) + 4 kB (H59).
8. **Contrast.** `--line` (#1d5c33) is only used for decorative borders and is excluded from the text-contrast test; every text colour is ≥ 4.5:1 on both backgrounds, and `--fg` / `--dim` are ≥ 7:1.
