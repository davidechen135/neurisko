import json
import shutil
import subprocess
from pathlib import Path

import pytest

from neurisko.runs import load_events
from neurisko.web.export import MAX_DATA_BYTES, export_site, static_dir

NODE = shutil.which("node")
REPO = Path(__file__).resolve().parents[2]


def test_export_writes_a_complete_site(recorded, tmp_path):
    runs = recorded / "runs" / "demo"
    out = tmp_path / "site"
    sizes = export_site(runs / "tiny", out, h59_dirs=(runs / "h59-off", runs / "h59-on"))
    for f in ("index.html", "style.css", "js/app.js", "js/reducer.js", ".nojekyll"):
        assert (out / f).exists(), f
    manifest = json.loads((out / "data" / "manifest.json").read_text())
    assert manifest == {
        "mode": "static",
        "run_url": "data/run.json",
        "report_url": None,
        "h59_url": "data/h59.json",
    }
    assert sum(sizes.values()) < MAX_DATA_BYTES
    # Every URL in the frontend is relative, so the site works under a sub-path.
    for js in (out / "js").rglob("*.js"):
        text = js.read_text()
        assert 'fetch("/' not in text and "EventSource(`/" not in text, js
    html = (out / "index.html").read_text()
    assert 'href="/' not in html and 'src="/' not in html


def test_export_replaces_old_site(recorded, tmp_path):
    out = tmp_path / "site"
    out.mkdir()
    (out / "stale.txt").write_text("x")
    export_site(recorded / "runs" / "demo" / "tiny", out)
    assert not (out / "stale.txt").exists()


def test_demo_export_fits(tmp_path):
    """The real demo data (committed under runs/demo and reports/demo) stays under 1 MB."""
    demo = REPO / "runs" / "demo"
    if not (demo / "qwen-s0").exists():
        pytest.skip("demo run not present")
    sizes = export_site(
        demo / "qwen-s0",
        tmp_path / "site",
        report_dir=REPO / "reports" / "demo" / "default",
        h59_dirs=(demo / "h59-off", demo / "h59-on"),
    )
    assert sum(sizes.values()) < MAX_DATA_BYTES


@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_js_reducer_matches_recorded_run(recorded, tmp_path):
    """Run the real frontend reducer in node and compare with the Python record."""
    out = tmp_path / "site"
    export_site(recorded / "runs" / "demo" / "tiny", out)
    script = tmp_path / "check.mjs"
    script.write_text(
        f'import {{ readFileSync }} from "node:fs";\n'
        f'import {{ reduceAll, at }} from "{(static_dir() / "js" / "reducer.js").as_uri()}";\n'
        f'const run = JSON.parse(readFileSync("{out / "data" / "run.json"}", "utf8"));\n'
        "const s = reduceAll(run.events);\n"
        "const v = at(s, s.gens.length);\n"
        "console.log(JSON.stringify({gen: v.gen, best: v.summary.best, end: s.end.reason,\n"
        "  designs: v.designs.map(h => h.id), metas: v.metas.map(h => h.id),\n"
        "  first: at(s, 1).summary.best, invented: v.invented.length}));\n"
    )
    res = subprocess.run([NODE, str(script)], capture_output=True, text=True, timeout=30)
    assert res.returncode == 0, res.stderr
    got = json.loads(res.stdout)
    events = load_events(recorded / "runs" / "demo" / "tiny")
    gens = [e for e in events if e["type"] == "generation"]
    assert got["gen"] == len(gens) == 3
    assert got["best"] == gens[-1]["best"] and got["first"] == gens[0]["best"]
    assert got["end"] == "completed"
    assert got["metas"] == ["M1", "M2", "M3", "M4", "M5"]
    assert set(got["designs"]) == {k for k in gens[-1]["worth"] if k.startswith("H")}
    created = [e for e in events if e["type"] == "heuristic_created"]
    assert got["invented"] == sum(e["heuristic"]["origin"]["by"] == "M1" for e in created)


@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_js_modules_parse():
    for js in (static_dir() / "js").rglob("*.js"):
        res = subprocess.run(
            [NODE, "--input-type=module", "--check"],
            input=js.read_text(),
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert res.returncode == 0, f"{js}: {res.stderr}"
