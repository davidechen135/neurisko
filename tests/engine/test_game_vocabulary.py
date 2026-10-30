import random

from neurisko.engine.game import BattleResult, MatchupResult, ScoreReport, weighted_score


def test_features_match_names(game):
    rng = random.Random(0)
    for _ in range(20):
        d = game.random_design(rng)
        feats = game.features(d, game.score(d))
        assert list(feats) == game.feature_names()
    assert len(game.feature_names()) == 7 + 12 + 4 + 6


def test_feature_values(game):
    d = ("flesh_golem", "gargoyle", "witch")
    f = game.features(d, game.score(d))
    assert f["cost"] == 7 and f["unspent"] == 3 and f["n_units"] == 3
    assert f["n_ranged"] == 1 and f["n_melee"] == 2
    assert f["front_hp"] == 160 + 70 and f["front_armor"] == 6 + 4
    assert f["count_construct"] == 2 and f["count_witch"] == 1
    assert 0 <= f["winrate_vs_armor_wall"] <= 1


def test_every_action_is_valid_or_none(game):
    rng = random.Random(1)
    schema = game.action_schema()
    for _ in range(40):
        d = game.random_design(rng)
        for kind, params in schema.items():
            for _ in range(10):
                action = {"kind": kind, **{p: rng.choice(v) for p, v in params.items()}}
                out = game.apply_action(d, action, rng)
                assert out is None or (game.validate(out) == [] and out != d)


def test_action_semantics(game):
    rng = random.Random(0)
    d = ("zombie", "ghost", "witch")
    apply = game.apply_action
    add = {"kind": "add_unit", "unit": "skeleton", "position": "front"}
    assert apply(d, add, rng) == ("skeleton", *d)
    assert apply(d, {"kind": "remove_unit", "unit": "@most_expensive"}, rng) == ("zombie", "witch")
    assert apply(d, {"kind": "replace_unit", "old": "@cheapest", "new": "gargoyle"}, rng) == (
        "gargoyle",
        "ghost",
        "witch",
    )
    assert apply(d, {"kind": "move_unit", "unit": "zombie", "to": "back"}, rng) == (
        "ghost",
        "witch",
        "zombie",
    )
    assert apply(d, {"kind": "move_unit", "unit": "zombie", "to": "front"}, rng) is None  # no-op
    assert apply(d, {"kind": "remove_unit", "unit": "hellhound"}, rng) is None  # absent
    big = {"kind": "add_unit", "unit": "hellhound", "position": "back"}
    assert apply(("hellhound", "hellhound", "flesh_golem"), big, rng) is None  # over budget


def test_held_out_differs(game):
    held = game.held_out()
    assert held.ruleset_hash == game.ruleset_hash
    assert [o.design for o in held.gauntlet] != [o.design for o in game.gauntlet]
    d = ("zombie", "ghost", "witch")
    assert held.score(d).battles == game.score(d).battles


def test_score_with_extra_opponents(game):
    d = ("zombie", "ghost", "witch")
    hof = [("hellhound", "hellhound", "witch", "witch")]
    r = game.score(d, hof)
    assert len(r.matchups) == len(game.gauntlet) + 1
    assert r.matchups[-1].opponent == "hof_00"
    assert game.score(d).matchups == r.matchups[:-1]  # stable seeds per opponent


def test_weighted_score():
    r = ScoreReport(0.0, 0, [MatchupResult("a", wins=4), MatchupResult("hof", losses=4)])
    assert weighted_score(r, 0, 0.5) == 0.0  # no extras: plain score
    assert weighted_score(r, 1, 0.5) == 0.5
    assert weighted_score(r, 1, 0.25) == 0.75
    assert BattleResult  # imported for completeness of the protocol module
