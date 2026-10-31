"""Append-only run records: `runs/<run_id>/meta.json` and `events.jsonl`.

Every event is also kept in memory (`Recorder.events`) so tests and the CLI can read it.
Any string listed in `redact` (e.g. an API key) is replaced before anything is written.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

REDACTED = "***"


def _default(o: Any) -> Any:
    if dataclasses.is_dataclass(o) and not isinstance(o, type):
        return dataclasses.asdict(o)
    if isinstance(o, (set, frozenset, tuple)):
        return list(o)
    if hasattr(o, "model_dump"):
        return o.model_dump(mode="json")
    raise TypeError(f"not JSON serialisable: {type(o).__name__}")


class Recorder:
    def __init__(
        self,
        run_dir: Path | None = None,
        redact: list[str] | None = None,
        listeners: list[Callable[[dict], None]] | None = None,
    ) -> None:
        self.run_dir = run_dir
        self.listeners = list(listeners or [])  # called with each event after it is written
        self.redact = [r for r in (redact or []) if r]
        self.events: list[dict] = []
        self._seq = 0
        self._file = None
        if run_dir is not None:
            run_dir.mkdir(parents=True, exist_ok=False)
            self._file = (run_dir / "events.jsonl").open("w", encoding="utf-8")

    def _dumps(self, obj: Any, **kw) -> str:
        text = json.dumps(obj, default=_default, ensure_ascii=False, **kw)
        for secret in self.redact:
            text = text.replace(secret, REDACTED)
        return text

    def emit(self, type: str, gen: int, **data: Any) -> dict:
        line = self._dumps({"t": self._seq, "gen": gen, "type": type, **data})
        self._seq += 1
        event = json.loads(line)  # the in-memory copy is exactly what was written
        self.events.append(event)
        if self._file is not None:
            self._file.write(line + "\n")
            self._file.flush()
        for listener in self.listeners:
            listener(event)
        return event

    def write_meta(self, meta: dict) -> None:
        if self.run_dir is not None:
            (self.run_dir / "meta.json").write_text(self._dumps(meta, indent=2) + "\n")

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None

    def of_type(self, type: str) -> list[dict]:
        return [e for e in self.events if e["type"] == type]


def load_events(run_dir: Path) -> list[dict]:
    with (run_dir / "events.jsonl").open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_meta(run_dir: Path) -> dict:
    return json.loads((run_dir / "meta.json").read_text())
