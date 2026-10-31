import json

import pytest

from neurisko.engine.evolve import EvolveConfig
from neurisko.llm import FakeClient
from neurisko.runs.session import start_run

GAME = dict(n_random=4, n_seeds=1)
ENGINE = dict(population=8, design_apps=12, immigrants=2)
GOOD = {
    "name": "Ghosts for armor",
    "if": [{"feature": "winrate_vs_armor_wall", "op": "<", "value": 0.9}],
    "then": {"kind": "replace_unit", "old": "@cheapest", "new": "ghost"},
}


def fake_llm(_seed=0):
    return FakeClient(replies=[json.dumps({"heuristics": [GOOD]})] * 20)


def record(run_dir, generations=3, auditor=True, llm=True, seed=0):
    cfg = EvolveConfig(generations=generations, seed=seed, auditor=auditor, **ENGINE)
    start_run(cfg, fake_llm() if llm else None, run_dir, game_settings=GAME)
    return run_dir


@pytest.fixture(scope="module")
def recorded(tmp_path_factory):
    """A tiny recorded run plus the two H59 runs, under a runs/ tree."""
    root = tmp_path_factory.mktemp("w")
    runs = root / "runs"
    record(runs / "demo" / "tiny", generations=3)
    record(runs / "demo" / "h59-off", generations=3, auditor=False, llm=False)
    record(runs / "demo" / "h59-on", generations=3, auditor=True, llm=False)
    return root
