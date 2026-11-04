"""Local web console: recorded runs, reports, and live runs streamed over SSE.

Meant for localhost: a live run spends this machine's CPU and LLM budget.
"""

# No `from __future__ import annotations`: FastAPI must evaluate the dependency annotations,
# and `get_live` is a closure it cannot look up from a string.
import asyncio
import json
import re
import threading
from collections.abc import AsyncIterable, Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from neurisko.engine.evolve import EvolveConfig
from neurisko.games.autobattler import MonsterMash
from neurisko.llm import LLMClient
from neurisko.runs import load_events, load_meta
from neurisko.runs.session import new_run_id, start_run
from neurisko.settings import Settings
from neurisko.web.export import game_for, static_dir
from neurisko.web.view import battle_view, compact_event, h59_view, run_view, tcs_view

ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
MAX_SEED = 2**31 - 1
MAX_DESIGN_TEXT = 200


@dataclass
class LiveRun:
    id: str
    events: list[dict] = field(default_factory=list)
    done: bool = False
    error: str | None = None
    thread: threading.Thread | None = None


class LiveRequest(BaseModel):
    seed: int = Field(default=0, ge=0, le=999_999)
    generations: int = Field(default=20, ge=1)
    llm: bool = True
    auditor: bool = True


def _resolve(base: Path, run_id: str) -> Path:
    """Directory of a run or report, looked up in `base` and `base/demo` only."""
    if not ID.match(run_id):
        raise HTTPException(422, "invalid id")
    root = base.resolve()
    for cand in (root / run_id, root / "demo" / run_id):
        p = cand.resolve()
        if p.is_relative_to(root) and p.is_dir():
            return p
    raise HTTPException(404, f"{run_id} not found")


def _list_runs(base: Path) -> list[dict]:
    out = []
    for parent in (base, base / "demo"):
        if not parent.is_dir():
            continue
        for d in parent.iterdir():
            if not (d / "meta.json").is_file() or not ID.match(d.name):
                continue
            meta = load_meta(d)
            cfg = meta.get("config", {})
            out.append(
                {
                    "id": d.name,
                    "demo": parent.name == "demo",
                    "seed": cfg.get("seed"),
                    "generations": cfg.get("generations"),
                    "auditor": cfg.get("auditor"),
                    "llm": meta.get("llm_model"),
                    "started": meta.get("started"),
                    "finished": meta.get("finished"),
                }
            )
    return sorted(out, key=lambda r: r.get("started") or "", reverse=True)


def _parse_design(text: str) -> tuple[str, ...]:
    if len(text) > MAX_DESIGN_TEXT:
        raise HTTPException(422, "design too long")
    return tuple(p.strip() for p in text.split(",") if p.strip())


def create_app(
    runs_dir: Path = Path("runs"),
    reports_dir: Path = Path("reports"),
    settings: Settings | None = None,
    llm_factory: Callable[[int], LLMClient | None] | None = None,
    engine_overrides: dict[str, Any] | None = None,
    game_settings: dict[str, Any] | None = None,
) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="Neurisko", docs_url=None, redoc_url=None)
    lock = threading.Lock()
    live: dict[str, LiveRun] = {}
    current: list[LiveRun | None] = [None]
    game = MonsterMash(**(game_settings or {}))

    def default_llm(seed: int) -> LLMClient | None:
        from neurisko.llm import OpenAICompatClient

        return OpenAICompatClient(
            settings.llm_base_url,
            settings.llm_model,
            settings.llm_api_key.get_secret_value(),
            timeout_s=settings.llm_timeout_s,
            seed=seed,
        )

    make_llm = llm_factory or default_llm

    @app.get("/data/manifest.json")
    def manifest() -> dict:
        runs = _list_runs(runs_dir)
        demo = next((r for r in runs if r["demo"] and r["llm"]), None) or (
            runs[0] if runs else None
        )
        has_report = (reports_dir / "demo" / "default" / "report.json").is_file()
        report = "api/reports/default" if has_report else None
        h59 = all((runs_dir / "demo" / n / "meta.json").is_file() for n in ("h59-off", "h59-on"))
        tcs = all(
            (runs_dir / "demo" / f"tcs-{e}" / "meta.json").is_file() for e in ("1981", "1982")
        )
        return {
            "mode": "live",
            "run_url": f"api/runs/{demo['id']}" if demo else None,
            "report_url": report,
            "h59_url": "api/h59" if h59 else None,
            "tcs_url": "api/tcs" if tcs else None,
            "max_generations": settings.max_generations,
            "live_id": current[0].id if current[0] is not None and not current[0].done else None,
        }

    @app.get("/api/runs")
    def runs() -> list[dict]:
        return _list_runs(runs_dir)

    @app.get("/api/runs/{run_id}")
    def run(run_id: str) -> dict:
        d = _resolve(runs_dir, run_id)
        meta = load_meta(d)
        return run_view(d.name, meta, load_events(d), game_for(meta))

    @app.get("/api/reports/{report_id}")
    def report(report_id: str) -> JSONResponse:
        d = _resolve(reports_dir, report_id)
        return JSONResponse(json.loads((d / "report.json").read_text()))

    @app.get("/api/h59")
    def h59() -> dict:
        dirs = [_resolve(runs_dir, n) for n in ("h59-off", "h59-on")]
        off, on = ((load_meta(d), load_events(d)) for d in dirs)
        return h59_view(off, on)

    @app.get("/api/tcs")
    def tcs() -> dict:
        runs = {}
        reports = {}
        for era in ("1981", "1982"):
            d = _resolve(runs_dir, f"tcs-{era}")
            runs[era] = (d.name, load_meta(d), load_events(d))
            rp = reports_dir / "demo" / f"tcs-{era}" / "report.json"
            if rp.is_file():
                reports[era] = json.loads(rp.read_text())
        return tcs_view(runs, reports or None)

    @app.get("/api/battle")
    def battle(
        a: str = Query(...), b: str = Query(...), seed: int = Query(0, ge=0, le=MAX_SEED)
    ) -> dict:
        da, db = _parse_design(a), _parse_design(b)
        errors = {k: game.validate(d) for k, d in (("a", da), ("b", db)) if game.validate(d)}
        if errors:
            raise HTTPException(422, {"message": "invalid design", "errors": errors})
        return battle_view(game, da, db, seed)

    @app.post("/api/live")
    def start_live(req: LiveRequest) -> dict:
        if req.generations > settings.max_generations:
            raise HTTPException(
                422, {"message": f"generations must be <= {settings.max_generations}"}
            )
        with lock:
            cur = current[0]
            if cur is not None and not cur.done:
                raise HTTPException(
                    409, {"message": f"run {cur.id} is still running", "id": cur.id}
                )
            run_id = new_run_id(req.seed)
            n = 1
            while (runs_dir / run_id).exists() or run_id in live:
                n += 1
                run_id = f"{new_run_id(req.seed)}-{n}"
            lr = LiveRun(run_id)
            live[run_id] = lr
            current[0] = lr

        cfg = replace(
            EvolveConfig(
                generations=req.generations,
                max_generations=settings.max_generations,
                seed=req.seed,
                auditor=req.auditor,
                max_llm_calls_per_generation=settings.max_llm_calls_per_generation,
            ),
            **(engine_overrides or {}),
        )

        def on_event(e: dict) -> None:
            c = compact_event(e)
            if c is not None:
                lr.events.append(c)

        def work() -> None:
            try:
                start_run(
                    cfg,
                    make_llm(req.seed) if req.llm else None,
                    runs_dir / run_id,
                    redact=[settings.llm_api_key.get_secret_value()],
                    listeners=[on_event],
                    game_settings=game_settings,
                )
            except Exception as err:  # the stream must still end
                lr.error = f"{type(err).__name__}: {err}"
                lr.events.append(
                    {"t": -1, "gen": 0, "type": "run_end", "reason": "error", "error": lr.error}
                )
            finally:
                lr.done = True

        lr.thread = threading.Thread(target=work, name=f"run-{run_id}", daemon=True)
        lr.thread.start()
        return {"id": run_id}

    def get_live(run_id: str) -> LiveRun:
        # A dependency runs before the response starts, so it can still return 404.
        if not ID.match(run_id) or run_id not in live:
            raise HTTPException(404, f"no live run {run_id}")
        return live[run_id]

    @app.get("/api/live/{run_id}/events", response_class=EventSourceResponse)
    async def live_events(
        request: Request,
        lr: Annotated[LiveRun, Depends(get_live)],
        last_event_id: Annotated[str | None, Header()] = None,
    ) -> AsyncIterable[ServerSentEvent]:
        i = int(last_event_id) + 1 if last_event_id and last_event_id.isdigit() else 0
        while True:
            while i < len(lr.events):
                yield ServerSentEvent(data=lr.events[i], id=str(i))
                i += 1
            if lr.done and i >= len(lr.events):
                return
            if await request.is_disconnected():
                return
            await asyncio.sleep(0.2)

    app.mount("/", StaticFiles(directory=static_dir(), html=True), name="static")
    return app
