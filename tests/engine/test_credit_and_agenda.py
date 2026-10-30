import random

import pytest

from neurisko.engine.agenda import design_tasks, meta_tasks, ucb
from neurisko.engine.credit import (
    CreditConfig,
    credit_application,
    ema,
    revoke_lineage,
    reward,
)
from neurisko.engine.meta import make_metas

from .conftest import heuristic

CFG = CreditConfig()


def test_reward_and_ema():
    assert reward(0.025, 0.05) == 0.5
    assert reward(1.0, 0.05) == 1.0 and reward(-1.0, 0.05) == -1.0
    assert ema(500, 1.0, 0.2) == pytest.approx(600)
    assert ema(500, -1.0, 0.2) == pytest.approx(400)
    assert ema(1000, 1.0, 1.0) == 1000 and ema(0, -1.0, 1.0) == 0


def test_direct_and_lineage_credit():
    metas = make_metas()
    h = heuristic("H1", by="M5")
    info = credit_application(h, 0.05, metas, CFG)
    assert h.worth == pytest.approx(600)
    assert h.stats.applications == 1 and h.stats.improvements == 1
    assert h.stats.direct_credit == 1.0
    m5 = metas["M5"]
    assert m5.worth == pytest.approx(550)  # rate lambda * alpha = 0.1
    assert m5.stats.lineage_credit == 0.5
    assert info["lineage"]["meta"] == "M5"
    seed_h = heuristic("H2", by="seed")
    assert "lineage" not in credit_application(seed_h, 0.05, metas, CFG)


def test_revoke_lineage_recomputes_worth():
    metas = make_metas()
    clone, honest = heuristic("H1", by="M5"), heuristic("H2", by="M5")
    for _ in range(5):
        credit_application(clone, 0.05, metas, CFG)
    credit_application(honest, -0.05, metas, CFG)
    revoked = revoke_lineage(metas["M5"], "H1", CFG)
    assert revoked == pytest.approx(2.5)
    assert metas["M5"].worth == pytest.approx(450)  # only the honest -1 remains
    assert metas["M5"].stats.lineage_credit == pytest.approx(-0.5)
    assert revoke_lineage(metas["M5"], "H1", CFG) == 0


def _pop(game, designs):
    return [(d, game.features(d, game.score(d))) for d in designs]


def test_agenda_respects_conditions_cap_and_explored(game):
    rng = random.Random(0)
    designs = [game.random_design(rng) for _ in range(10)]
    pop = _pop(game, designs)
    never = heuristic("H1", [{"feature": "cost", "op": ">", "value": 99}])
    always = heuristic("H2", action={"kind": "remove_unit", "unit": "@cheapest"})
    tasks, active = design_tasks([never, always], pop, game, rng, 40, 3, 0.3, 0)
    assert active == {"H2"}
    assert len(tasks) == 3 and all(t.heuristic is always for t in tasks)
    explored = {(t.parent, t.child) for t in tasks}
    again, _ = design_tasks([always], pop, game, rng, 40, 10, 0.3, 0, explored=explored)
    assert not explored & {(t.parent, t.child) for t in again}


def test_untried_heuristics_get_scheduled(game):
    rng = random.Random(0)
    pop = _pop(game, [game.random_design(rng) for _ in range(8)])
    veteran = heuristic("H1", action={"kind": "remove_unit", "unit": "@cheapest"}, worth=550)
    veteran.stats.applications = 500
    rookie = heuristic("H2", action={"kind": "remove_unit", "unit": "@most_expensive"}, worth=500)
    tasks, _ = design_tasks([veteran, rookie], pop, game, rng, 1, 1, 0.3, 500)
    assert tasks[0].heuristic is rookie
    assert ucb(0, 500, 0.3) > ucb(500, 500, 0.3)


def test_meta_tasks_distinct():
    metas = list(make_metas().values())
    chosen = meta_tasks(metas, random.Random(0), 3, 0.3, 0)
    assert len(chosen) == 3 and len({m.id for m in chosen}) == 3
