import json

import pytest

from neurisko.cli import main
from neurisko.engine.evolve import EvolveConfig
from neurisko.llm import FakeClient
from neurisko.runs import Recorder, load_events, load_meta
from neurisko.runs.session import config_from_meta, replay_run, start_run

GOOD = {
    "name": "Ghosts for armor",
    "if": [{"feature": "winrate_vs_armor_wall", "op": "<", "value": 0.9}],
    "then": {"kind": "replace_unit", "old": "@cheapest", "new": "ghost"},
}
SECRET = "sk-test-secret-123456"


def test_recorder_writes_and_redacts(tmp_path):
    rec = Recorder(tmp_path / "r", redact=[SECRET])
    rec.emit("x", 1, design=("a", "b"), note=f"key={SECRET}")
    rec.write_meta({"key": SECRET})
    rec.close()
    [e] = load_events(tmp_path / "r")
    assert e == {"t": 0, "gen": 1, "type": "x", "design": ["a", "b"], "note": "key=***"}
    assert load_meta(tmp_path / "r") == {"key": "***"}
    with pytest.raises(FileExistsError):
        Recorder(tmp_path / "r")


def _cfg(**kw):
    base = dict(generations=3, seed=1, population=10, design_apps=16, immigrants=2)
    base.update(kw)
    return EvolveConfig(**base)


def test_run_is_recorded_and_replays_identically(tmp_path):
    replies = [json.dumps({"heuristics": [GOOD]}), TimeoutError("slow"), "not json", "{}"]
    llm = FakeClient(replies=replies * 3)
    run_dir = tmp_path / "run"
    start_run(_cfg(), llm, run_dir, redact=[SECRET])
    meta = load_meta(run_dir)
    assert meta["llm_model"] == "fake" and meta["battles"] > 0
    assert config_from_meta(meta) == _cfg()
    events = load_events(run_dir)
    assert events[-1]["type"] == "run_end"
    assert any(e["type"] in ("llm_call", "llm_error") for e in events)
    ev, problems = replay_run(run_dir)
    assert problems == []
    assert ev.rec.of_type("llm_call") or ev.rec.of_type("llm_error")


def test_api_key_never_recorded(tmp_path, monkeypatch):
    """The key is redacted even if it ends up in a prompt or reply."""
    llm = FakeClient(replies=[json.dumps({"heuristics": [GOOD], "echo": SECRET})] * 10)
    run_dir = tmp_path / "run"
    start_run(_cfg(generations=2), llm, run_dir, redact=[SECRET])
    for name in ("events.jsonl", "meta.json"):
        assert SECRET not in (run_dir / name).read_text()


def test_replay_detects_mismatch(tmp_path):
    run_dir = tmp_path / "run"
    start_run(_cfg(generations=2), None, run_dir)
    lines = (run_dir / "events.jsonl").read_text().splitlines()
    tampered = []
    for line in lines:
        e = json.loads(line)
        if e["type"] == "generation" and e["gen"] == 2:
            e["best_pool"] = -1
        tampered.append(json.dumps(e))
    (run_dir / "events.jsonl").write_text("\n".join(tampered) + "\n")
    _, problems = replay_run(run_dir)
    assert problems == ["generation 2 differs in ['best_pool']"]


def test_cli_evolve_and_replay(tmp_path, capsys):
    args = ["evolve", "--no-llm", "--generations", "2", "--runs-dir", str(tmp_path)]
    assert main([*args, "--run-id", "a"]) == 0
    out = capsys.readouterr().out
    assert "GEN 01" in out and "GEN 02" in out and "COMPLETED" in out
    assert main([*args, "--run-id", "a"]) == 2  # refuses to overwrite
    assert main(["evolve", "--replay", str(tmp_path / "a")]) == 0
    assert "replay identical" in capsys.readouterr().out
