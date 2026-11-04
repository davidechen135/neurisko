"""Export a recorded run (plus report and H59 comparison) as a static site."""

from __future__ import annotations

import json
import shutil
from importlib import resources
from pathlib import Path

from neurisko.engine.game import Game
from neurisko.games.registry import game_from_meta
from neurisko.runs import load_events, load_meta
from neurisko.web.view import h59_view, run_view, tcs_view

MAX_DATA_BYTES = 1_000_000


def static_dir() -> Path:
    return Path(str(resources.files("neurisko.web").joinpath("static")))


def game_for(meta: dict) -> Game:
    return game_from_meta(meta)


def _dump(path: Path, obj) -> int:
    text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    path.write_text(text, encoding="utf-8")
    return len(text.encode())


def export_site(
    run_dir: Path,
    out: Path,
    report_dir: Path | None = None,
    h59_dirs: tuple[Path, Path] | None = None,
    tcs_dirs: tuple[Path, Path] | None = None,
    tcs_reports: tuple[Path, Path] | None = None,
) -> dict[str, int]:
    """Write the site to `out` (replacing it). Returns data file sizes in bytes."""
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(static_dir(), out)
    data = out / "data"
    data.mkdir()
    meta = load_meta(run_dir)
    events = load_events(run_dir)
    sizes = {
        "run.json": _dump(data / "run.json", run_view(run_dir.name, meta, events, game_for(meta)))
    }
    manifest = {
        "mode": "static",
        "run_url": "data/run.json",
        "report_url": None,
        "h59_url": None,
        "tcs_url": None,
    }
    if report_dir is not None:
        shutil.copy(report_dir / "report.json", data / "report.json")
        sizes["report.json"] = (data / "report.json").stat().st_size
        manifest["report_url"] = "data/report.json"
    if h59_dirs is not None:
        off, on = ((load_meta(d), load_events(d)) for d in h59_dirs)
        sizes["h59.json"] = _dump(data / "h59.json", h59_view(off, on))
        manifest["h59_url"] = "data/h59.json"
    if tcs_dirs is not None:
        runs = {
            era: (d.name, load_meta(d), load_events(d))
            for era, d in zip(("1981", "1982"), tcs_dirs, strict=True)
        }
        reps = None
        if tcs_reports is not None:
            reps = {
                era: json.loads((d / "report.json").read_text())
                for era, d in zip(("1981", "1982"), tcs_reports, strict=True)
            }
        sizes["tcs.json"] = _dump(data / "tcs.json", tcs_view(runs, reps))
        manifest["tcs_url"] = "data/tcs.json"
    _dump(data / "manifest.json", manifest)
    (out / ".nojekyll").write_text("")  # GitHub Pages: serve files as they are
    total = sum(sizes.values())
    if total > MAX_DATA_BYTES:
        raise ValueError(f"exported data is {total:,} bytes (limit {MAX_DATA_BYTES:,})")
    return sizes
