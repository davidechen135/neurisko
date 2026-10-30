import json
import time

import pytest

from neurisko.engine.evolve import Evolution
from neurisko.engine.heuristics import RuleSpec
from neurisko.games.autobattler import MonsterMash
from neurisko.llm import FakeClient
from neurisko.runs import Recorder
from neurisko.runs.session import TIMING_KEYS

from .conftest import small_config, small_game

GOOD = {
    "name": "Ghosts for armor",
    "rationale": "ignore armor",
    "if": [{"feature": "winrate_vs_armor_wall", "op": "<", "value": 0.9}],
    "then": {"kind": "replace_unit", "old": "@cheapest", "new": "ghost"},
}
BAD = {"name": "Teleport", "then": {"kind": "teleport"}}


def _gens(events):
    return [
        {k: v for k, v in e.items() if k not in TIMING_KEYS}
        for e in events
        if e["type"] == "generation"
    ]


def test_loop_records_every_generation(seeds):
    ev = Evolution(small_game(), small_config(generations=3), seeds)
    result = ev.run()
    assert result.reason == "completed" and result.generations == 3
    types = [e["type"] for e in ev.rec.events]
    assert types[0] == "run_start" and types[-1] == "run_end"
    assert types.count("generation") == 3
    assert len(ev.rec.of_type("heuristic_created")) >= 5 + len(seeds)
    for a in ev.rec.of_type("applied"):
        assert a["delta"] == a["child_score"] - a["parent_score"]
    s = result.summaries[-1]
    assert len(s["population"]) == 12 and 1 <= len(s["hof"]) <= 3
    scores = [x[1] for x in s["population"]]
    assert scores == sorted(scores, reverse=True)
    json.dumps(ev.rec.events)  # everything is JSON-serialisable


def test_same_seed_same_run(seeds):
    a = Evolution(small_game(), small_config(seed=3), seeds)
    b = Evolution(small_game(), small_config(seed=3), seeds)
    a.run()
    b.run()
    assert _gens(a.rec.events) == _gens(b.rec.events)
    c = Evolution(small_game(), small_config(seed=4), seeds)
    c.run()
    assert _gens(a.rec.events) != _gens(c.rec.events)


def test_max_generations_budget(seeds):
    ev = Evolution(small_game(), small_config(generations=5, max_generations=2), seeds)
    result = ev.run()
    assert result.reason == "budget" and result.generations == 2
    assert ev.rec.of_type("run_end")[0]["reason"] == "budget"


def test_population_score_does_not_fall_against_fixed_gauntlet(seeds):
    ev = Evolution(small_game(), small_config(generations=4), seeds)
    result = ev.run()
    first = result.summaries[0]["best_gauntlet"]
    assert result.summaries[-1]["best_gauntlet"] >= first


def test_retirement_keeps_minimum(seeds):
    # Auditor off: merging a duplicate is not retirement (its behaviour lives on in the
    # original), so only retirement is held to the minimum.
    cfg = small_config(generations=6, retire_below=1000, auditor=False)
    ev = Evolution(small_game(), cfg, seeds)
    ev.run()
    assert len(ev.design_heuristics()) >= ev.cfg.min_design_heuristics
    assert ev.rec.of_type("retired")


def _invent_run(replies, **cfg):
    llm = FakeClient(replies=list(replies))
    # Force Invent to run every generation by making the other metas unavailable.
    config = small_config(generations=1, meta_apps=5, **cfg)
    ev = Evolution(small_game(), config, [], llm=llm, recorder=Recorder())
    ev.run()
    return ev, llm


def test_invent_keeps_valid_and_logs_rejected():
    ev, llm = _invent_run([json.dumps({"heuristics": [GOOD, BAD]})])
    created = [
        e for e in ev.rec.of_type("heuristic_created") if e["heuristic"]["origin"]["by"] == "M1"
    ]
    assert [e["heuristic"]["name"] for e in created] == ["Ghosts for armor"]
    rejected = ev.rec.of_type("heuristic_rejected")
    assert rejected and "unknown action kind 'teleport'" in rejected[0]["errors"][0]
    assert len(llm.calls) == 1
    call = ev.rec.of_type("llm_call")[0]
    assert call["response"] and call["messages"][0]["role"] == "system"
    assert "winrate_vs_armor_wall" in call["messages"][0]["content"]


def test_invent_retries_once_with_errors():
    ev, llm = _invent_run([json.dumps({"heuristics": [BAD]}), json.dumps({"heuristics": [GOOD]})])
    assert len(llm.calls) == 2
    assert "teleport" in llm.calls[1][-1]["content"]
    assert [e["attempt"] for e in ev.rec.of_type("llm_call")] == [0, 1]


def test_invent_respects_budget():
    ev, llm = _invent_run([json.dumps({"heuristics": [BAD]})] * 3, max_llm_calls_per_generation=1)
    assert len(llm.calls) == 1
    assert ev.rec.of_type("llm_skipped")[0]["reason"] == "budget"


def test_llm_error_does_not_stop_the_run():
    ev, _ = _invent_run([TimeoutError("timed out")])
    assert ev.rec.of_type("llm_error")[0]["error"] == "timed out"
    assert ev.rec.of_type("run_end")[0]["reason"] == "completed"


def test_garbage_reply_is_rejected():
    ev, _ = _invent_run(["not json", json.dumps({"nope": 1})])
    assert len(ev.rec.of_type("llm_call")) == 2
    assert not [
        e for e in ev.rec.of_type("heuristic_created") if e["heuristic"]["origin"]["by"] == "M1"
    ]


@pytest.mark.slow
def test_twenty_generations_under_a_minute(seeds):
    """R8.3, with the full default gauntlet and config."""
    from neurisko.engine.evolve import EvolveConfig

    t = time.perf_counter()
    ev = Evolution(MonsterMash(), EvolveConfig(generations=20), seeds)
    ev.run()
    assert time.perf_counter() - t < 60


def test_rule_spec_roundtrip(seeds):
    for s in seeds:
        assert RuleSpec.model_validate(s.model_dump(by_alias=True)) == s
