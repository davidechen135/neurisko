"""The visual replay data must agree with the simulator it was rebuilt from."""

import random

import pytest

from neurisko.games.autobattler.game import MonsterMash
from neurisko.games.tcs_lite import fleet as F
from neurisko.games.tcs_lite.game import TcsLite
from neurisko.web.view import battle_view
from neurisko.web.visual import monster_visual


@pytest.fixture(scope="module")
def mm():
    return MonsterMash()


def test_monster_rebuild_matches_simulator(mm):
    rng = random.Random(7)
    for seed in range(60):
        a, b = mm.random_design(rng), mm.random_design(rng)
        r = mm.simulate(a, b, seed, log=True)
        v = monster_visual(mm, a, b, r.events)
        assert v["survivors"]["A"] == r.survivors_a, seed
        assert v["survivors"]["B"] == r.survivors_b, seed
        assert len(v["steps"]) == len(r.events)
        hp = {u["label"]: u["hp"] for u in v["units"]}
        for kind, actor, _t, _n, updates in v["steps"]:
            for label, h, mx in updates:
                assert h <= mx
                hp[label] = h
            if kind == "death":
                assert hp[actor] <= 0, (seed, actor)
        for label in r.survivors_a + r.survivors_b:
            assert hp[label] > 0, (seed, label)


def test_fleet_status_snapshots():
    g = TcsLite()
    swarm = F.make_fleet([((0, 0, 0, 0), 99)], ["scuttle_disabled"])
    elite = F.make_fleet([((3, 3, 3, 2), 4)])
    bv = battle_view(g, swarm, elite, 0)
    v = bv["visual"]
    assert v["kind"] == "fleet" and len(v["steps"]) == len(bv["lines"])
    assert all(k != "status" for k, _ in bv["lines"])
    snaps = [s[4] for s in v["steps"] if s[4]]
    assert snaps and all(len(s["A"]) == 99 and len(s["B"]) == 4 for s in snaps)
    assert set("".join(s["A"] for s in snaps)) <= set("adxs")


def test_simulation_unchanged_by_status_logging():
    g = TcsLite()
    a = F.make_fleet([((0, 0, 0, 0), 60)])
    b = F.make_fleet([((2, 1, 2, 1), 6)])
    for seed in range(10):
        quiet, logged = g.simulate(a, b, seed), g.simulate(a, b, seed, log=True)
        assert (quiet.winner, quiet.ticks) == (logged.winner, logged.ticks)
