import random

import pytest

from neurisko.engine.game import Patch
from neurisko.games.autobattler import RulesetError
from neurisko.games.tcs_lite import NOTICE
from neurisko.games.tcs_lite import fleet as F
from neurisko.games.tcs_lite.combat import Compiled, simulate
from neurisko.games.tcs_lite.game import TcsLite
from neurisko.games.tcs_lite.rules import load_ruleset, parse_ruleset

MINI = (0, 0, 0, 0)
ELITE = (3, 3, 3, 2)


@pytest.fixture(scope="module")
def r81():
    return load_ruleset(era="1981")


@pytest.fixture(scope="module")
def r82():
    return load_ruleset(era="1982")


def rules_with(base, **era):
    d = base.model_dump()
    d["era"] = {**d["era"], **era}
    return parse_ruleset(d)


# --- rules ---------------------------------------------------------------------------------


def test_eras_differ_only_in_era(r81, r82):
    a, b = r81.model_dump(), r82.model_dump()
    assert a.pop("era") != b.pop("era")
    assert a == b
    assert r81.era.max_disabled_fraction == 1.0 and not r81.era.allow_scuttle
    assert r82.era.max_disabled_fraction < 1 and r82.era.allow_scuttle
    assert r81.hash != r82.hash


def test_invalid_rules_rejected(r81):
    d = r81.model_dump()
    d["components"]["hull"]["hp"] = [2, 4, 8]
    with pytest.raises(RulesetError, match="components.hull"):
        parse_ruleset(d)
    d = r81.model_dump()
    d["archetypes"][0]["doctrine"] = ["ram"]
    with pytest.raises(RulesetError, match="unknown doctrine"):
        parse_ruleset(d)


# --- fleets --------------------------------------------------------------------------------


def test_costs_by_hand(r81):
    # minimal ship: build 1+0+1+0 = 2; 99 ships = 6 + 2 + 98 * 2 * 0.8
    assert F.cost(r81, F.make_fleet([(MINI, 99)])) == pytest.approx(6 + 2 + 98 * 1.6)
    # elite: build 20+10+10+5 = 45; 4 ships = 6 + 45 + 3 * 45 * 0.8
    assert F.cost(r81, F.make_fleet([(ELITE, 4)])) == pytest.approx(6 + 45 + 3 * 36)
    two = F.make_fleet([(MINI, 10), (ELITE, 1)])
    assert F.cost(r81, two) == pytest.approx((6 + 2 + 9 * 1.6) + (6 + 45))


def test_canonical_form():
    a = F.make_fleet([(ELITE, 2), (MINI, 5)], ["scuttle_disabled"])
    b = F.make_fleet([(MINI, 3), (ELITE, 2), (MINI, 2)], ["scuttle_disabled", "scuttle_disabled"])
    assert a == b and hash(a) == hash(b)


def test_validation_messages(r81, r82):
    errors = F.validate(r81, F.make_fleet([((0, 3, 3, 3), 1), (ELITE, 9)], ["scuttle_disabled"]))
    text = " | ".join(errors)
    assert "exceeds 2 slots of hull 0" in text
    assert "not allowed in the 1981 era" in text
    assert F.validate(r82, F.make_fleet([(MINI, 1)], ["scuttle_disabled"])) == []
    assert "exceeds budget" in " ".join(F.validate(r81, F.make_fleet([(ELITE, 9)])))
    assert "not in 1..99" in " ".join(F.validate(r81, F.make_fleet([(MINI, 120)])))


def test_max_count(r81):
    f = F.make_fleet([(MINI, 1)])
    n = F.max_count(r81, f, MINI)
    assert n == 99  # capped by max_ships_per_class (budget would allow 120)
    f2 = F.make_fleet([(MINI, 1), (ELITE, 4)])
    n2 = F.max_count(r81, f2, MINI)
    assert not F.validate(r81, F.make_fleet([(MINI, n2), (ELITE, 4)]))
    assert F.validate(r81, F.make_fleet([(MINI, n2 + 1), (ELITE, 4)]))


# --- combat --------------------------------------------------------------------------------


def test_deterministic_and_symmetric(r81):
    c = Compiled(r81)
    a, b = F.make_fleet([(MINI, 40)]), F.make_fleet([(ELITE, 4)])
    assert simulate(c, a, b, 3, log=True) == simulate(c, a, b, 3, log=True)
    wins = [simulate(c, a, b, s).winner for s in range(20)]
    mirrored = [simulate(c, b, a, s).winner for s in range(20)]
    flip = {"A": "B", "B": "A", "draw": "draw"}
    # Not identical per seed (shot order differs), but the same overall picture.
    assert abs(wins.count("A") - [flip[w] for w in mirrored].count("A")) <= 6


def test_disable_destroy_and_withdraw(r81, r82):
    c81, c82 = Compiled(r81), Compiled(r82)
    swarm, elite = F.make_fleet([(MINI, 99)]), F.make_fleet([(ELITE, 4)])
    r = simulate(c81, elite, swarm, 0, log=True)
    kinds = {e.kind for e in r.events}
    assert {"attack", "disabled", "death"} <= kinds and "withdraw" not in kinds
    r = simulate(c82, swarm, elite, 0, log=True)
    assert any(e.kind == "withdraw" and e.actor.startswith("A") for e in r.events)
    assert r.winner == "B"


def test_scuttling_removes_disabled_ships(r82):
    c = Compiled(r82)
    swarm = F.make_fleet([(MINI, 99)], ["scuttle_disabled"])
    r = simulate(c, swarm, F.make_fleet([(ELITE, 4)]), 0, log=True)
    kinds = [e.kind for e in r.events if e.actor.startswith("A")]
    assert "scuttle" in kinds and "withdraw" not in kinds
    assert r.winner == "A"


def test_draw_at_round_limit(r81):
    d = r81.model_dump()
    d["limits"]["max_rounds"] = 1
    c = Compiled(parse_ruleset(d))
    big = F.make_fleet([((3, 3, 0, 3), 1)])
    assert simulate(c, big, big, 0).winner == "draw"


# --- game ----------------------------------------------------------------------------------


def test_actions_and_parse():
    g = TcsLite(n_random=2, n_seeds=1)
    rng = random.Random(0)
    f = g.parse_design("50x0000,2x3332")
    assert F.n_ships(f) == 52
    maxed = g.apply_action(f, {"kind": "set_count", "class": "@largest", "change": "max"}, rng)
    assert maxed is not None and F.n_ships(maxed) > 52 and not g.validate(maxed)
    up = g.apply_action(f, {"kind": "upgrade", "class": "@cheapest", "component": "guns"}, rng)
    assert ((0, 0, 1, 0), 50) in up[0] or not g.validate(up)
    assert g.apply_action(f, {"kind": "toggle_doctrine", "flag": "scuttle_disabled"}, rng) is None
    with pytest.raises(ValueError, match="bad class"):
        g.parse_design("50x000")
    assert "swarm" in g.parts(f) and "elite" not in g.parts(f)


def test_rule_patches():
    g = TcsLite(n_random=2, n_seeds=1)
    texts = [p.text() for p in g.patch_candidates("swarm")]
    assert texts[0] == "components.hull.cost.0 1->2"
    patched, _ = g.with_patch(Patch(target="swarm", field="components.hull.cost.0", old=1, new=2))
    assert patched.rules.components.hull.cost[0] == 2 and patched.ruleset_hash != g.ruleset_hash
    assert F.cost(patched.rules, F.make_fleet([(MINI, 99)])) > 200  # swarm archetype now over
    assert "swarm" not in [o.name for o in patched.gauntlet]


def test_notice_is_in_rules_text():
    assert NOTICE in TcsLite(n_random=2, n_seeds=1).describe_rules()


# --- story (R7) ----------------------------------------------------------------------------


@pytest.mark.slow
def test_story_1981_swarm_and_1982_scuttle():
    """Measured with the report's detection settings; not loosened to pass (R7.3)."""
    from neurisko.report.detect import (
        Thresholds,
        baseline_shares,
        make_specs,
        run_batch,
        share_table,
    )
    from neurisko.report.report import ReportConfig

    eng = ReportConfig().engine_config()
    tables, champs = {}, {}
    for era in ("1981", "1982"):
        g = TcsLite.from_file(era=era)
        outs = run_batch(make_specs(g, range(8), eng, g.seed_rules(), 5))
        tables[era] = {
            p.part: p for p in share_table(g, outs, baseline_shares(g, 2000), Thresholds())
        }
        champs[era] = [g.from_json(o.champion) for o in outs]
    assert "dominant" in tables["1981"]["swarm"].flags  # R7.1
    assert "dominant" in tables["1982"]["scuttle"].flags  # R7.2: scuttling in most runs
    assert tables["1982"]["scuttle"].champion_runs >= 6
    g82 = TcsLite.from_file(era="1982").held_out()
    g81 = TcsLite.from_file(era="1981").held_out()
    before = sum(g81.score(c).score for c in champs["1981"]) / 8
    after = sum(g82.score(c).score for c in champs["1981"]) / 8
    assert after < before - 0.3  # 1981 champions lose much of their score under 1982 rules
