from neurisko.engine.heuristics import Condition, parse_rule

from .conftest import heuristic


def _parse(game, raw):
    return parse_rule(raw, game.feature_names(), game.action_schema())


def test_seed_rules_are_valid(seeds):
    assert len(seeds) == 10


def test_valid_rule_with_aliases(game):
    spec, errors = _parse(
        game,
        {
            "name": "x",
            "rationale": "y" * 500,
            "if": [{"feature": "unspent", "op": ">=", "value": 1}],
            "then": {"kind": "add_unit", "unit": "ghost", "position": "back"},
            "extra_key": "ignored",
        },
    )
    assert errors == []
    assert len(spec.rationale) == 200
    assert spec.conditions == [Condition(feature="unspent", op=">=", value=1)]


def test_rejections_name_the_problem(game):
    cases = [
        (
            {"feature": "mana", "op": ">", "value": 1},
            {"kind": "add_unit", "unit": "ghost", "position": "back"},
            "unknown feature 'mana'",
        ),
        (None, {"kind": "teleport"}, "unknown action kind 'teleport'"),
        (None, {"kind": "add_unit", "unit": "lich", "position": "back"}, "unit='lich' not allowed"),
        (None, {"kind": "add_unit", "unit": "ghost"}, "needs parameter 'position'"),
        (None, {"kind": "remove_unit", "unit": "ghost", "x": "1"}, "unknown parameters"),
    ]
    for cond, action, expected in cases:
        raw = {"name": "n", "if": [cond] if cond else [], "then": action}
        spec, errors = _parse(game, raw)
        assert spec is None
        assert any(expected in e for e in errors), (expected, errors)


def test_schema_errors(game):
    spec, errors = _parse(game, {"name": "n", "if": [{"feature": "cost", "op": "~", "value": 1}]})
    assert spec is None
    assert any("then" in e for e in errors)
    assert any("op" in e for e in errors)
    many = [{"feature": "cost", "op": ">", "value": i} for i in range(4)]
    spec, errors = _parse(
        game, {"name": "n", "if": many, "then": {"kind": "remove_unit", "unit": "ghost"}}
    )
    assert any("at most 3 conditions" in e for e in errors)


def test_matching_and_text():
    h = heuristic("H1", [{"feature": "unspent", "op": ">=", "value": 2}])
    assert h.matches({"unspent": 2}) and not h.matches({"unspent": 1})
    assert not h.matches({})  # missing feature never matches
    assert h.text() == "IF unspent>=2 THEN add_unit(unit=skeleton, position=back)"
    assert heuristic("H2").text().startswith("IF always THEN")
