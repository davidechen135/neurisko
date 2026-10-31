# Requirements: Web UI ("The Lisp Machine")

## Introduction
The UI shows a Neurisko run the way a 1981 Lisp machine console might have: phosphor text, a worth table of heuristic units, a teletype audit log and ASCII charts. It has two modes that share one frontend:

- **Replay** (static): a run and its balance report exported to plain files and hosted on GitHub Pages. Judges open a link; there is no backend and no LLM.
- **Live** (local): `neurisko serve` starts runs on the developer's machine and streams events to the same page over SSE. This mode is for the demo video.

Hackathon judging weighs Design ("a complete, coherent product experience rather than a rough proof of concept"). The look must serve the content: every element shows real run data, and the H59 story has to be visible without narration.

## Glossary
- **View model**: the compact event stream plus metadata that the frontend renders. It is the same in both modes.
- **Battle player**: a teletype animation of one recorded or simulated battle log.

## Requirements

### R1. One frontend, two data sources
1. The frontend SHALL be static HTML, CSS and vanilla JS modules with no build step (tech steering).
2. It SHALL render from a view model, either loaded from a JSON file (replay) or built incrementally from SSE events (live), through one reducer.
3. The Python function that compacts run events for the UI SHALL be shared by the export and the live stream.

### R2. Static export and hosting
1. `neurisko export RUN_DIR [--report REPORT_DIR] --out site/` SHALL write a self-contained site: the frontend files plus `data/run.json`, `data/report.json` and precomputed battle logs.
2. The exported data for `runs/demo/qwen-s0` SHALL be under 1 MB.
3. The site SHALL work when served from any static host under a sub-path (GitHub Pages project URL).
4. A GitHub Actions workflow SHALL build and deploy the site to GitHub Pages on push to `main`.

### R3. Live mode
1. `neurisko serve [--host 127.0.0.1] [--port 8000]` SHALL bind to localhost by default. It SHALL print a warning if bound elsewhere, because a live run spends CPU and LLM budget.
2. The page SHALL let the user start a run with: seed, generations (≤ `MAX_GENERATIONS`), LLM on/off, auditor on/off.
3. Only one live run SHALL run at a time; a second start request SHALL get HTTP 409.
4. Events SHALL stream over SSE as they are recorded. A reconnecting client SHALL receive the events it missed (by last event id).
5. The live run SHALL be recorded to `runs/<run_id>/` exactly as a CLI run is, so it can be exported afterwards.
6. Run and report ids in URLs SHALL be validated against `^[A-Za-z0-9._-]+$` and resolved only inside `runs/` and `reports/`.
7. `GET /api/battle` SHALL simulate a battle between two valid designs on demand (validated input, bounded seed).

### R4. Views
1. **Score chart**: per generation, the champion's score on the fixed gauntlet and on held-out + hall of fame, as an ASCII/box-drawing chart.
2. **Worth table**: meta-heuristics and the top design heuristics with id, worth bar, origin (seed, M1–M5), rule text and flags. `PARASITE`, `DUPLICATE-OF:Hn` and `NON-REPLICATING` SHALL be visually distinct and explained on hover/focus.
3. **Audit teletype**: audit decisions in order, with their numbers.
4. **LLM transcript**: each Invent call, collapsed by default, showing the evidence sent, the reply and which heuristics were kept or rejected.
5. **Generation scrubber**: in replay mode, every view SHALL show the state as of the selected generation.
6. **Battle player**: plays a battle log as teletype text with speed control and skip-to-end.
7. **Balance report**: dominant and underused parts with shares, baseline and range; evidence; patches with before/after and effective/failed reasons; the summary, labelled when LLM-written.
8. **H59 view**: a side-by-side of the M5 Clone worth curve with and without the auditor, from two recorded demo runs.

### R5. Design quality and accessibility
1. Text and essential UI SHALL meet WCAG AA contrast (4.5:1) against the background.
2. Scanlines, flicker and typing animation SHALL be off when `prefers-reduced-motion` is set, and SHALL have a visible toggle.
3. All controls SHALL be keyboard-operable with visible focus.
4. Layout SHALL work at 1280×720 (video capture) and remain readable at 390 px width.
5. Information SHALL not rely on colour alone (flags also carry text labels).

### R6. Tests
1. API tests with FastAPI's test client: start, 409 on a second start, SSE delivers events, invalid ids rejected, battle endpoint validation.
2. Export test: files present, size limit, `run.json` reduces to the same final state as the recorded run.
3. A palette test checks the contrast ratios of the CSS colour variables.
