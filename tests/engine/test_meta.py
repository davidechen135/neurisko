import random

from neurisko.engine.heuristics import validate_rule
from neurisko.engine.meta import MetaContext, clone, generalize, retarget, specialize
from neurisko.runs import Recorder

from .conftest import heuristic


def _ctx(game, hs, seed=0):
    return MetaContext(
        game=game,
        rng=random.Random(seed),
        generation=1,
        heuristics=hs,
        features_of=lambda d: game.features(d, game.score(d)),
        recorder=Recorder(),
    )


def _valid(game, p):
    return validate_rule(p.conditions, p.action, game.feature_names(), game.action_schema()) == []


def _worked(h):
    h.stats.applications = 2
    h.stats.recent = [(("zombie", "ghost"), ("zombie", "ghost", "skeleton"), 0.1)]
    return h


def test_specialize_adds_a_condition_true_for_the_parent(game):
    h = _worked(heuristic("H1", [{"feature": "unspent", "op": ">=", "value": 1}]))
    for seed in range(10):
        [p] = specialize(_ctx(game, [h], seed))
        assert _valid(game, p) and p.parent == "H1"
        assert len(p.conditions) == 2 and p.conditions[0] == h.conditions[0]
        parent = ("zombie", "ghost")
        assert p.conditions[1].holds(game.features(parent, game.score(parent)))
    assert specialize(_ctx(game, [heuristic("H2")])) == []  # never improved anything


def test_generalize_drops_a_condition(game):
    h = heuristic(
        "H1",
        [
            {"feature": "unspent", "op": ">=", "value": 1},
            {"feature": "n_units", "op": "<", "value": 4},
        ],
    )
    [p] = generalize(_ctx(game, [h]))
    assert len(p.conditions) == 1 and _valid(game, p) and p.parent == "H1"
    assert generalize(_ctx(game, [heuristic("H2")])) == []


def test_retarget_changes_one_parameter(game):
    h = heuristic("H1")
    for seed in range(10):
        [p] = retarget(_ctx(game, [h], seed))
        assert _valid(game, p)
        changed = [k for k in h.action if h.action[k] != p.action[k]]
        assert len(changed) == 1 and changed[0] != "kind"


def test_clone_copies_the_best_used_heuristic(game):
    a = _worked(heuristic("H1", worth=600))
    b = _worked(heuristic("H2", [{"feature": "cost", "op": "<", "value": 9}], worth=900))
    unused = heuristic("H3", worth=1000)
    [p] = clone(_ctx(game, [a, b, unused]))
    assert p.parent == "H2" and p.conditions == b.conditions and p.action == b.action
    assert clone(_ctx(game, [unused])) == []
