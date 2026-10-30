import random

from neurisko.games.autobattler.design import mutations, random_design, validate

from .conftest import make_rules, unit


def test_random_designs_are_valid(rules):
    for seed in range(500):
        d = random_design(rules, random.Random(seed))
        assert validate(rules, d) == [], d


def test_mutations_are_valid_distinct_and_new(rules):
    for seed in range(60):
        rng = random.Random(seed)
        d = random_design(rules, rng)
        ms = mutations(rules, d, rng)
        assert ms, d
        assert d not in ms
        assert len(set(ms)) == len(ms)
        for m in ms:
            assert validate(rules, m) == [], (d, m)


def test_mutation_kinds_are_present(rules):
    d = ("zombie", "ghost", "witch")
    ms = set(mutations(rules, d, random.Random(0)))
    assert ("zombie", "ghost", "witch", "skeleton") in ms  # add
    assert ("zombie", "ghost") in ms  # remove
    assert ("zombie", "ghost", "werewolf") in ms  # replace
    assert ("ghost", "zombie", "witch") in ms  # swap


def test_mutations_are_seeded(rules):
    d = ("zombie", "ghost", "witch")
    assert mutations(rules, d, random.Random(3)) == mutations(rules, d, random.Random(3))


def test_validate_reports_every_violation(rules):
    d = ("hellhound",) * 3 + ("flesh_golem",) * 3 + ("lich",)
    errors = validate(rules, d)
    joined = " | ".join(errors)
    assert "team size 7" in joined
    assert "unknown units: lich" in joined
    assert "exceeds budget" in joined
    assert "hellhound appears 3 times" in joined
    assert "flesh_golem appears 3 times" in joined
    assert validate(rules, ()) == ["team size 0 not in 1..5"]


def test_no_mutation_possible_returns_empty():
    r = make_rules([unit("x")], budget=1, max_team_size=1)
    assert mutations(r, ("x",), random.Random(0)) == []
