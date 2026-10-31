import pytest

from neurisko.engine.game import Patch
from neurisko.games.autobattler import MonsterMash, RulesetError
from neurisko.games.autobattler.rules import parse_ruleset


@pytest.fixture(scope="module")
def game():
    return MonsterMash()


def test_witch_candidates(game):
    assert [p.text() for p in game.patch_candidates("witch")] == [
        "witch.cost 2->3",
        "witch.hp 45->36",  # ATK 6 is too low to be the main stat
        "witch.ability.amount 12->8",
    ]


def test_candidate_rules(game):
    texts = {u: [p.text() for p in game.patch_candidates(u)] for u in game.part_names()}
    assert "pumpkin_mage.atk 20->16" in texts["pumpkin_mage"]
    assert "hellhound.ability.multiplier 2->1.7" in texts["hellhound"]  # bonus shrinks, >= 1
    assert "necromancer.ability.max 3->2" in texts["necromancer"]
    assert texts["ghost"] == ["ghost.cost 2->3", "ghost.atk 9->7"]  # no magnitude to reduce


def test_with_patch_changes_hash_and_value(game):
    patched, dropped = game.with_patch(Patch(target="witch", field="cost", old=2, new=3))
    assert patched.ruleset_hash != game.ruleset_hash
    assert patched.rules.unit_map["witch"].cost == 3
    assert game.rules.unit_map["witch"].cost == 2  # original untouched
    # arcane_backline (gargoyle, zombie, witch, pumpkin_mage, ghost) costs 11 now
    assert dropped == ["arcane_backline"]
    assert "arcane_backline" not in [o.name for o in patched.gauntlet]
    assert patched.settings() == game.settings()


def test_with_patch_ability_and_errors(game):
    patched, _ = game.with_patch(Patch(target="witch", field="ability.amount", old=12, new=8))
    assert patched.rules.unit_map["witch"].ability.amount == 8
    with pytest.raises(RulesetError, match="no ability parameter"):
        game.with_patch(Patch(target="ghost", field="ability.amount", old=1, new=0))
    with pytest.raises(RulesetError, match="whole number"):
        game.with_patch(Patch(target="witch", field="cost", old=2, new=2.5))
    with pytest.raises(RulesetError, match="unknown unit"):
        game.with_patch(Patch(target="lich", field="cost", old=1, new=2))
    with pytest.raises(RulesetError, match="dodge"):  # chance must stay < 1
        game.with_patch(Patch(target="bat_swarm", field="ability.chance", old=0.3, new=1.5))


def test_baseline_designs_are_competitive(game):
    import random

    from neurisko.games.autobattler.gauntlet import is_competitive

    ds = game.baseline_designs(random.Random(0), 200)
    assert len(ds) == 200 and all(is_competitive(game.rules, d) for d in ds)


def test_registry_rebuilds_equivalent_game(game):
    from neurisko.games.registry import make_game

    g2 = make_game(game.name, game.ruleset_json(), game.settings())
    assert g2.ruleset_hash == game.ruleset_hash
    d = ("zombie", "ghost", "witch")
    assert g2.score(d).score == game.score(d).score
    assert parse_ruleset(g2.rules.model_dump()).hash == game.ruleset_hash
