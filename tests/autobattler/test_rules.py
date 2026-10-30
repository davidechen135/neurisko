import copy

import pytest

from neurisko.games.autobattler.rules import RulesetError, load_ruleset, parse_ruleset


def _data(rules) -> dict:
    return copy.deepcopy(rules.model_dump())


def test_default_ruleset_shape(rules):
    assert len(rules.units) == 12
    factions = {u.faction for u in rules.units}
    assert factions == {"undead", "beast", "arcane", "construct"}
    for f in factions:
        assert sum(u.faction == f for u in rules.units) == 3
    assert {s.faction: s.threshold for s in rules.synergies} == dict.fromkeys(factions, 2)


def test_hash_is_stable_and_sensitive(rules):
    assert load_ruleset().hash == rules.hash
    data = _data(rules)
    data["units"][0]["hp"] += 1
    assert parse_ruleset(data).hash != rules.hash


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda d: d["units"][0].pop("hp"), "units.0.hp"),
        (lambda d: d["units"][0].update(atk=-1), "units.0.atk"),
        (lambda d: d["units"][0].update(ability={"kind": "teleport"}), "units.0.ability"),
        (lambda d: d["synergies"][0].update(faction="vampire"), "unknown faction"),
        (lambda d: d["units"][2]["ability"].update(unit="lich"), "summons unknown unit"),
        (lambda d: d["units"][1].update(id=d["units"][0]["id"]), "duplicate unit ids"),
        (lambda d: d["archetypes"][0]["units"].append("lich"), "unknown units"),
        (lambda d: d["limits"].update(surprise=1), "limits.surprise"),
    ],
)
def test_invalid_rulesets_are_rejected_with_location(rules, mutate, expected):
    data = _data(rules)
    mutate(data)
    with pytest.raises(RulesetError, match=expected):
        parse_ruleset(data)


def test_unreadable_file(tmp_path):
    with pytest.raises(RulesetError, match="cannot read"):
        load_ruleset(tmp_path / "missing.toml")
    bad = tmp_path / "bad.toml"
    bad.write_text("this is = = not toml")
    with pytest.raises(RulesetError, match="cannot read"):
        load_ruleset(bad)


def test_load_from_file_matches_default(rules, tmp_path):
    from importlib import resources

    text = (
        resources.files("neurisko.games.autobattler").joinpath("data", "default.toml").read_text()
    )
    path = tmp_path / "copy.toml"
    path.write_text(text)
    assert load_ruleset(path).hash == rules.hash
