# Tech Stack and Conventions

## Stack
- Python 3.12, managed with `uv` (`uv add`, `uv run`). Do not use pip directly.
- Backend: FastAPI; stream evolution progress to the browser with Server-Sent Events.
- Frontend: server-rendered HTML + vanilla JS or htmx. No React or build step unless a spec decides otherwise.
- Visual style: 1981 terminal / Lisp machine (phosphor green, CRT scanlines, monospace, ASCII charts).
- LLM: any OpenAI-compatible endpoint, configured via `.env` (`LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`). Default is local Ollama `qwen2.5:14b`.
- Tests: pytest. Lint/format: ruff.

## Architecture rules
- Simulators are pure Python, deterministic given a seed, and never call the LLM. Thousands of battles per generation must stay fast.
- The LLM only proposes, mutates and explains heuristics. All LLM output is parsed into validated data models (pydantic); reject and log anything that fails validation.
- Games implement one shared interface (rules, random design, mutate design, simulate, score) so the engine stays game-agnostic.
- Every evolution run is recorded to `runs/<run_id>/` (heuristics, worth history, designs, scores, battle logs) so the web UI can replay it without an LLM.

## Layout
```
src/neurisko/
  engine/     # units, heuristics, agenda, credit assignment, auditor
  llm/        # OpenAI-compatible client, prompts, output schemas
  games/
    autobattler/
    tcs_lite/
  runs/       # recording and replay
  web/        # FastAPI app, templates, static
tests/
```

## Commands
- Install: `uv sync`
- Tests: `uv run pytest`
- Lint: `uv run ruff check . && uv run ruff format --check .`
