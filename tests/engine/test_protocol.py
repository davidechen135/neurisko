"""Every registered game implements the whole `Game` protocol with matching signatures."""

import inspect
import random

import pytest

from neurisko.engine.game import Game
from neurisko.games.registry import GAMES, load_game, make_game


@pytest.fixture(params=GAMES, scope="module")
def game(request):
    return load_game(request.param, n_random=4, n_seeds=1)


def test_protocol_conformance(game):
    for name, member in inspect.getmembers(Game):
        if name.startswith("_"):
            continue
        assert hasattr(game, name), name
        if callable(member):
            got = list(inspect.signature(getattr(game, name)).parameters)
            want = list(inspect.signature(member).parameters)[1:]
            assert got == want, name
    for name in Game.__annotations__:
        assert hasattr(game, name), name


def test_shared_behaviour(game):
    rng = random.Random(0)
    d = game.random_design(rng)
    assert game.validate(d) == []
    assert game.from_json(game.to_json(d)) == d
    for m in game.mutations(d, rng)[:20]:
        assert game.validate(m) == [] and m != d
    feats = game.features(d, game.score(d))
    assert list(feats) == game.feature_names()
    r = game.simulate(d, d, 1, log=True)
    assert r.winner in ("A", "B", "draw")
    assert all(isinstance(game.describe_event(e), str) for e in r.events)
    assert game.seed_rules()
    assert set(game.parts(d)) <= set(game.part_names())
    assert all(game.validate(x) == [] for x in game.baseline_designs(rng, 5))
    for alt in game.without_part(d, next(iter(game.parts(d)), "none")):
        assert game.validate(alt) == []
    g2 = make_game(game.name, game.ruleset_json(), game.settings())
    assert g2.ruleset_hash == game.ruleset_hash and g2.score(d).score == game.score(d).score
    assert game.held_out().ruleset_hash == game.ruleset_hash
    for opp in game.featured_opponents(d):
        assert game.validate(opp) == []
