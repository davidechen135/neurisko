import json
import shutil
import time

import pytest
from fastapi.testclient import TestClient

from neurisko.settings import Settings
from neurisko.web.app import create_app

from .conftest import ENGINE, GAME, fake_llm


@pytest.fixture
def client(recorded, tmp_path):
    runs = tmp_path / "runs"
    (runs / "demo").mkdir(parents=True)
    for name in ("tiny", "h59-off", "h59-on"):
        shutil.copytree(recorded / "runs" / "demo" / name, runs / "demo" / name)
    app = create_app(
        runs_dir=runs,
        reports_dir=tmp_path / "reports",
        settings=Settings(max_generations=5, llm_api_key="sk-live-secret-key"),
        llm_factory=fake_llm,
        engine_overrides=ENGINE,
        game_settings=GAME,
    )
    with TestClient(app) as c:
        yield c


def sse_events(client, url, headers=None):
    out = []
    with client.stream("GET", url, headers=headers or {}) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        ev = {}
        for line in r.iter_lines():
            if line.startswith("id:"):
                ev["id"] = int(line[3:].strip())
            elif line.startswith("data:"):
                ev["data"] = json.loads(line[5:].strip())
            elif line == "" and ev:
                out.append(ev)
                ev = {}
    return out


def test_static_and_manifest(client):
    assert "NEURISKO" in client.get("/").text
    assert client.get("/js/reducer.js").status_code == 200
    m = client.get("/data/manifest.json").json()
    assert m["mode"] == "live" and m["run_url"] == "api/runs/tiny" and m["h59_url"] == "api/h59"
    assert m["report_url"] is None


def test_recorded_run_view(client):
    v = client.get("/api/runs/tiny").json()
    types = {e["type"] for e in v["events"]}
    assert {"run_start", "generation", "run_end", "llm_call"} <= types
    assert "applied" not in types
    assert v["battles"] and v["system_prompt"]
    assert [r["id"] for r in client.get("/api/runs").json()].count("tiny") == 1
    h = client.get("/api/h59").json()
    assert set(h["off"]["worth"]) == {"M1", "M2", "M3", "M4", "M5"}


@pytest.mark.parametrize("bad", ["..", "a b", ".hidden", "x" * 101, "%2e%2e"])
def test_invalid_ids_rejected(client, bad):
    r = client.get(f"/api/runs/{bad}")
    assert r.status_code in (404, 422)


def test_symlink_out_of_runs_dir_is_rejected(client, recorded, tmp_path):
    (tmp_path / "runs" / "escape").symlink_to(recorded / "runs" / "demo" / "tiny")
    assert client.get("/api/runs/escape").status_code == 404


def test_unknown_ids(client):
    assert client.get("/api/runs/nope").status_code == 404
    assert client.get("/api/reports/default").status_code == 404
    assert client.get("/api/live/nope/events").status_code == 404


def test_battle_endpoint(client):
    r = client.get("/api/battle", params={"a": "zombie,ghost", "b": "gargoyle", "seed": 3})
    assert r.status_code == 200
    b = r.json()
    assert b["winner"] in ("A", "B", "draw") and b["events"]
    bad = client.get("/api/battle", params={"a": "lich", "b": "gargoyle"})
    assert bad.status_code == 422 and "unknown units" in json.dumps(bad.json())
    assert (
        client.get("/api/battle", params={"a": "zombie", "b": "zombie", "seed": -1}).status_code
        == 422
    )
    assert client.get("/api/battle", params={"a": "z," * 200, "b": "zombie"}).status_code == 422


def test_live_run_streams_and_records(client, tmp_path):
    r = client.post("/api/live", json={"seed": 1, "generations": 2, "llm": True, "auditor": True})
    assert r.status_code == 200
    run_id = r.json()["id"]
    events = sse_events(client, f"/api/live/{run_id}/events")
    types = [e["data"]["type"] for e in events]
    assert types[0] == "run_start" and types[-1] == "run_end" and types.count("generation") == 2
    assert [e["id"] for e in events] == list(range(len(events)))
    # Resume after event 3: the rest, nothing repeated.
    rest = sse_events(client, f"/api/live/{run_id}/events", {"Last-Event-ID": "3"})
    assert [e["id"] for e in rest] == list(range(4, len(events)))
    # Recorded like a CLI run, and the key never written.
    run_dir = tmp_path / "runs" / run_id
    for _ in range(50):
        if (run_dir / "meta.json").exists() and "finished" in (run_dir / "meta.json").read_text():
            break
        time.sleep(0.1)
    assert (run_dir / "events.jsonl").exists()
    for name in ("events.jsonl", "meta.json"):
        assert "sk-live-secret-key" not in (run_dir / name).read_text()
    assert client.get(f"/api/runs/{run_id}").status_code == 200


def test_one_live_run_at_a_time(client):
    first = client.post("/api/live", json={"seed": 2, "generations": 3, "llm": False})
    assert first.status_code == 200
    second = client.post("/api/live", json={"seed": 3, "generations": 1, "llm": False})
    assert second.status_code == 409 and second.json()["detail"]["id"] == first.json()["id"]
    sse_events(client, f"/api/live/{first.json()['id']}/events")  # wait for it to finish
    third = client.post("/api/live", json={"seed": 3, "generations": 1, "llm": False})
    assert third.status_code == 200
    sse_events(client, f"/api/live/{third.json()['id']}/events")


def test_live_request_validation(client):
    assert client.post("/api/live", json={"generations": 6}).status_code == 422  # > max 5
    assert client.post("/api/live", json={"seed": -1}).status_code == 422
    assert client.post("/api/live", json={"generations": 0}).status_code == 422
