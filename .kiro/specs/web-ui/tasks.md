# Tasks: Web UI ("The Lisp Machine")

- [ ] 1. Dependencies and view model
  - `uv add fastapi uvicorn`; `web/view.py` with `compact_event` and `build_run_view`; Recorder listeners.
  - _Requirements: R1.3, R3.4_

- [ ] 2. Static frontend skeleton
  - `index.html`, `style.css` (palette, CRT effects, reduced motion, focus), `app.js` with static-file data source and hash routing; palette contrast test.
  - _Requirements: R1.1, R1.2, R5.1–R5.5, R6.3_

- [ ] 3. Run views
  - Reducer, score chart, worth table with flags, audit teletype, champion panel, generation scrubber.
  - _Requirements: R4.1–R4.3, R4.5_

- [ ] 4. Battle player and LLM transcript
  - _Requirements: R4.4, R4.6_

- [ ] 5. Export
  - `neurisko export` with precomputed battles, H59 data and report; size test; reducer equivalence test.
  - _Requirements: R2.1–R2.3, R6.2_

- [ ] 6. Report and H59 tabs
  - Depends on the balance-report spec. Record `runs/demo/h59-off` and `runs/demo/h59-on`.
  - _Requirements: R4.7, R4.8_

- [ ] 7. Live server
  - FastAPI app, run manager (one at a time), SSE with resume, battle endpoint, path safety; API tests.
  - _Requirements: R3.1–R3.7, R6.1_

- [ ] 8. Deployment
  - GitHub Actions Pages workflow; enable Pages (ask the user first); check the public URL under its sub-path.
  - _Requirements: R2.4_

- [ ] 9. Checkpoint
  - Manual accessibility checklist, 1280×720 screenshot for the README, tests and ruff pass, notes updated.
