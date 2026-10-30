import inspect
import random

from neurisko.engine.game import BattleResult, Game
from neurisko.games.autobattler import MonsterMash
from neurisko.games.autobattler.design import validate
from neurisko.games.autobattler.gauntlet import build_gauntlet, is_competitive, score


def test_gauntlet_is_deterministic_and_valid(rules):
    g1, g2 = build_gauntlet(rules, 1981), build_gauntlet(rules, 1981)
    assert g1 == g2
    assert len(g1) == len(rules.archetypes) + 18
    assert [o.name for o in g1[: len(rules.archetypes)]] == [a.name for a in rules.archetypes]
    assert len({o.design for o in g1}) == len(g1)
    for o in g1:
        assert validate(rules, o.design) == []
    for o in g1[len(rules.archetypes) :]:
        assert is_competitive(rules, o.design)
    assert build_gauntlet(rules, 7) != g1


def test_score_range_battles_and_reproducibility(rules):
    game = MonsterMash(rules)
    d = ("zombie", "werewolf", "witch", "ghost")
    report = game.score(d)
    assert 0.0 <= report.score <= 1.0
    assert report.battles == len(game.gauntlet) * 3 * 2
    assert MonsterMash(rules).score(d).score == report.score
    assert game.score(list(d)) is report  # cached, list and tuple share the key


def test_draw_counts_as_half(rules):
    def always_draw(a, b, seed):
        return BattleResult("draw", 1, [], [], [])

    gauntlet = build_gauntlet(rules)
    assert score(("zombie",), gauntlet, always_draw).score == 0.5


def test_score_counts_wins_on_both_sides(rules):
    me = ("zombie",)

    def i_always_win(a, b, seed):
        return BattleResult("A" if a == me else "B", 1, [], [], [])

    report = score(me, build_gauntlet(rules), i_always_win, n_seeds=2)
    assert report.score == 1.0
    assert all(m.wins == 4 and m.games == 4 for m in report.matchups)


def test_monster_mash_implements_game_protocol(rules):
    game = MonsterMash(rules)
    for name, member in inspect.getmembers(Game):
        if name.startswith("_"):
            continue
        assert hasattr(game, name), name
        if callable(member):
            assert (
                list(inspect.signature(getattr(game, name)).parameters)
                == list(inspect.signature(member).parameters)[1:]
            ), name
    for name in Game.__annotations__:
        assert hasattr(game, name), name


def test_describe(rules):
    game = MonsterMash(rules)
    assert game.describe(("zombie", "ghost")) == "[zombie > ghost] cost 3/10"
    text = game.describe_rules()
    for u in rules.units:
        assert u.id in text
    assert rules.hash in text
    assert "summon_on_ally_death(unit=skeleton, max=3)" in text


def test_game_methods_delegate(rules):
    game = MonsterMash(rules)
    rng = random.Random(0)
    d = game.random_design(rng)
    assert game.validate(d) == []
    assert all(game.validate(m) == [] for m in game.mutations(d, rng))
    assert game.simulate(d, d, 0).winner in {"A", "B", "draw"}
