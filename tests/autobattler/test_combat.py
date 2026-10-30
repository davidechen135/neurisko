import random

from neurisko.games.autobattler.design import random_design

from .conftest import fight, make_rules, unit

WALL = ("flesh_golem", "gargoyle", "gargoyle", "scarecrow", "scarecrow")
BATS = ("bat_swarm", "bat_swarm", "skeleton", "skeleton", "zombie")
GHOSTS = ("scarecrow", "zombie", "ghost", "ghost", "witch")
UNDEAD = ("zombie", "skeleton", "zombie", "skeleton", "necromancer")


def _events(result, kind, actor_part=""):
    return [e for e in result.events if e.kind == kind and actor_part in e.actor]


# --- Determinism and fairness -----------------------------------------------------------


def test_same_seed_same_result(rules):
    for seed in range(30):
        rng = random.Random(seed)
        a, b = random_design(rules, rng), random_design(rules, rng)
        assert fight(rules, a, b, seed) == fight(rules, a, b, seed)


def test_swapping_sides_mirrors_result_without_randomness(rules):
    no_dodge = [u.id for u in rules.units if u.id != "bat_swarm"]
    rng = random.Random(7)
    for seed in range(40):
        a = tuple(rng.sample(no_dodge, 3))
        b = tuple(rng.sample(no_dodge, 3))
        ab = fight(rules, a, b, seed, log=False)
        ba = fight(rules, b, a, seed, log=False)
        mirror = {"A": "B", "B": "A", "draw": "draw"}
        assert ba.winner == mirror[ab.winner], (a, b)
        assert ba.ticks == ab.ticks


def test_identical_units_kill_each_other_in_the_same_tick():
    r = make_rules([unit("x", hp=30, atk=10)])
    result = fight(r, ["x"], ["x"])
    assert result.winner == "draw"
    assert result.ticks == 30
    assert result.survivors_a == result.survivors_b == []


def test_max_ticks_is_a_draw():
    r = make_rules([unit("tank", hp=10_000, atk=1)], max_ticks=50)
    result = fight(r, ["tank"], ["tank"])
    assert result.winner == "draw"
    assert result.ticks == 50
    assert result.survivors_a and result.survivors_b


def test_result_has_per_unit_stats(rules):
    result = fight(rules, WALL, BATS, 1)
    assert {s.side for s in result.stats} == {"A", "B"}
    assert len(result.stats) == len(WALL) + len(BATS)
    dealt_by_a = sum(s.damage_dealt for s in result.stats if s.side == "A")
    taken_by_b = sum(s.damage_taken for s in result.stats if s.side == "B")
    assert dealt_by_a == taken_by_b > 0
    assert sum(s.kills for s in result.stats if s.side == "A") == len(BATS)


def test_log_is_optional(rules):
    assert fight(rules, WALL, BATS, 1, log=False).events is None


# --- Positioning ------------------------------------------------------------------------


def test_back_line_melee_waits_ranged_acts():
    r = make_rules(
        [
            unit("wall", hp=10_000, atk=0),
            unit("brute", atk=50),
            unit("archer", atk=5, range="ranged"),
            unit("dummy", hp=10_000, atk=0),
        ],
        max_ticks=100,
    )
    result = fight(r, ["wall", "wall", "brute", "archer"], ["dummy"])
    assert _events(result, "attack", "archer")
    assert not _events(result, "attack", "brute")


def test_back_melee_steps_up_when_front_dies():
    r = make_rules(
        [unit("weak", hp=1, atk=0), unit("brute", atk=50), unit("hitter", hp=10_000, atk=5)],
    )
    result = fight(r, ["weak", "weak", "brute"], ["hitter"])
    assert _events(result, "attack", "brute")


# --- Abilities --------------------------------------------------------------------------


def test_lifesteal_heals_attacker():
    r = make_rules(
        [
            unit("leech", atk=20, ability={"kind": "lifesteal", "fraction": 0.5}),
            unit("punchbag", hp=10_000, atk=5, speed=1),
        ],
        max_ticks=100,
    )
    result = fight(r, ["leech"], ["punchbag"])
    leech = next(s for s in result.stats if s.unit_id == "leech")
    assert leech.healing > 0
    assert all(e.amount == 10 for e in _events(result, "heal"))


def test_dodge_avoids_some_hits():
    r = make_rules(
        [
            unit("bat", hp=10_000, atk=0, ability={"kind": "dodge", "chance": 0.5}),
            unit("hitter", atk=1, speed=1),
        ],
        max_ticks=200,
    )
    result = fight(r, ["bat"], ["hitter"], seed=0)
    dodges, hits = len(_events(result, "dodge")), len(_events(result, "attack", "hitter"))
    assert dodges + hits == 200
    assert 60 < dodges < 140


def test_first_strike_doubles_only_first_attack():
    r = make_rules(
        [
            unit("hound", atk=10, ability={"kind": "first_strike", "multiplier": 2.0}),
            unit("dummy", hp=10_000, atk=0),
        ],
        max_ticks=40,
    )
    amounts = [e.amount for e in _events(fight(r, ["hound"], ["dummy"]), "attack", "hound")]
    assert amounts == [20, 10, 10, 10]


def test_heal_targets_lowest_hp_ratio_ally():
    r = make_rules(
        [
            unit("front", hp=100, atk=0),
            unit("witch", atk=0, range="ranged", ability={"kind": "heal_lowest_ally", "amount": 7}),
            unit("hitter", hp=10_000, atk=30, speed=10),
        ],
        max_ticks=10,
    )
    result = fight(r, ["front", "witch"], ["hitter"])
    heals = _events(result, "heal")
    assert [(e.target, e.amount) for e in heals] == [("A0:front", 7)]


def test_splash_hits_unit_behind_target():
    r = make_rules(
        [
            unit("mage", atk=20, range="ranged", ability={"kind": "splash", "fraction": 0.5}),
            unit("dummy", hp=10_000, atk=0),
        ],
        max_ticks=10,
    )
    result = fight(r, ["mage"], ["dummy", "dummy"])
    assert [(e.target, e.amount) for e in _events(result, "attack", "mage")] == [
        ("B0:dummy", 20),
        ("B1:dummy", 10),
    ]


def test_ignore_armor_and_damage_floor():
    r = make_rules(
        [
            unit("ghost", atk=9, range="ranged", ability={"kind": "ignore_armor"}),
            unit("archer", atk=9, range="ranged"),
            unit("golem", hp=10_000, atk=0, armor=50),
        ],
        max_ticks=10,
    )
    result = fight(r, ["ghost", "archer"], ["golem"])
    assert [e.amount for e in _events(result, "attack", "ghost")] == [9]
    assert [e.amount for e in _events(result, "attack", "archer")] == [1]


def test_necromancer_summons_at_most_max(rules):
    result = fight(rules, UNDEAD, WALL, 0)
    necro = next(s for s in result.stats if s.unit_id == "necromancer")
    summoned = [s for s in result.stats if s.summoned]
    assert necro.summons == 3
    assert len(summoned) == 3
    assert all(s.unit_id == "skeleton" for s in summoned)
    assert [s.label for s in summoned] == ["A5:skeleton", "A6:skeleton", "A7:skeleton"]


# --- Synergies and intended imbalances ---------------------------------------------------


def test_synergy_bonuses_apply():
    syn = [{"faction": "test", "threshold": 2, "atk_pct": 0.5, "armor_flat": 3}]
    r = make_rules(
        [unit("x", atk=10, range="ranged"), unit("dummy", faction="d", hp=10_000, atk=0)],
        synergies=syn,
        max_ticks=10,
    )
    solo = fight(r, ["x"], ["dummy"])
    pair = fight(r, ["x", "x"], ["dummy"])
    assert [e.amount for e in _events(solo, "attack", "x")] == [10]
    assert [e.amount for e in _events(pair, "attack", "x")] == [15, 15]


def test_synergy_turns_off_when_faction_drops_below_threshold(rules):
    result = fight(rules, BATS, WALL, 1)
    assert _events(result, "synergy_off", "A:beast")


def test_summons_keep_undead_synergy_alive(rules):
    """Summoned skeletons count toward the undead synergy (intended imbalance)."""
    r = fight(rules, ("skeleton", "necromancer"), ("flesh_golem",), 0)
    first_death = next(e.tick for e in _events(r, "death", "A0:skeleton"))
    summons_then = [e for e in _events(r, "summon") if e.tick == first_death]
    offs_then = [e for e in _events(r, "synergy_off", "A:undead") if e.tick == first_death]
    assert summons_then and not offs_then


def test_armor_wall_beats_weak_fast_attackers(rules):
    assert all(fight(rules, WALL, BATS, s, log=False).winner == "A" for s in range(10))


def test_ghosts_counter_armor_wall(rules):
    assert all(fight(rules, GHOSTS, WALL, s, log=False).winner == "A" for s in range(10))
