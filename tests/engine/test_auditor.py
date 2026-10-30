import pytest

from neurisko.engine.auditor import AuditConfig, Auditor
from neurisko.engine.credit import CreditConfig, credit_application
from neurisko.engine.evolve import Evolution
from neurisko.engine.meta import make_metas
from neurisko.runs import Recorder

from .conftest import heuristic, small_config, small_game

CFG = CreditConfig()


def _auditor(game, rec=None):
    return Auditor(game, AuditConfig(probes=16), CFG, rec or Recorder(), seed=0)


def test_duplicate_is_merged_and_its_lineage_revoked(game):
    rec = Recorder()
    aud = _auditor(game, rec)
    metas = make_metas()
    original = heuristic("H1", action={"kind": "remove_unit", "unit": "@cheapest"})
    copy = heuristic("H2", action={"kind": "remove_unit", "unit": "@cheapest"}, by="M5")
    different = heuristic("H3", action={"kind": "remove_unit", "unit": "@most_expensive"})
    for _ in range(3):
        credit_application(copy, 0.05, metas, CFG)
    assert metas["M5"].worth > 500
    hs = {h.id: h for h in (original, copy, different)}
    decisions = aud.audit(3, hs, metas, [])
    merged = [d for d in decisions if d["check"] == "duplicate"]
    assert [(d["target"], d["original"]) for d in merged] == [("H2", "H1")]
    assert not copy.alive and "duplicate-of:H1" in copy.flags
    assert original.stats.applications == 3
    # Revocation resets M5 to its initial worth ...
    assert merged[0]["revoked_lineage"] == pytest.approx(1.5)
    assert merged[0]["creator_worth_after"] == 500
    # ... and since all of its positive credit came from the duplicate, the same audit
    # then flags it as a parasite.
    parasite = next(d for d in decisions if d["check"] == "parasite" and d["target"] == "M5")
    assert parasite["decision"] == "demoted" and metas["M5"].worth == 300
    assert different.alive


def test_heuristics_that_apply_to_no_probe_are_not_duplicates(game):
    aud = _auditor(game)
    a = heuristic("H1", [{"feature": "cost", "op": ">", "value": 99}])
    b = heuristic("H2", [{"feature": "cost", "op": ">", "value": 98}])
    assert aud.signature(a) is None
    decisions = aud.audit(3, {"H1": a, "H2": b}, make_metas(), [])
    assert a.alive and b.alive and not [d for d in decisions if d["check"] == "duplicate"]


def test_non_replicating_gain_is_demoted(game):
    aud = _auditor(game)
    h = heuristic("H1", worth=900)
    h.stats.applications = 6
    strong, weak = ("hellhound", "hellhound", "witch", "witch"), ("skeleton",)
    h.stats.recent = [(strong, weak, 0.2)] * 3  # claims a gain that is really a big loss
    good = heuristic("H2", action={"kind": "remove_unit", "unit": "@cheapest"}, worth=900)
    good.stats.applications = 6
    good.stats.recent = [(weak, strong, 0.2)] * 3
    decisions = aud.audit(3, {"H1": h, "H2": good}, make_metas(), [])
    rep = {d["target"]: d for d in decisions if d["check"] == "replication"}
    assert rep["H1"]["decision"] == "demoted" and h.worth == 400
    assert "non-replicating" in h.flags and "H1" in aud.tainted
    assert rep["H2"]["decision"] == "passed" and good.worth == 900
    assert rep["H1"]["held_out_delta"] < 0 < rep["H2"]["held_out_delta"]


def test_parasite_meta_is_demoted(game):
    aud = _auditor(game)
    metas = make_metas()
    kids = [heuristic(f"H{i}", by="M5") for i in range(1, 5)]
    for k in kids:
        credit_application(k, 0.05, metas, CFG)
    honest = heuristic("H9", by="M2")
    for _ in range(4):
        credit_application(honest, 0.05, metas, CFG)
    aud.tainted |= {"H1", "H2", "H3"}
    decisions = aud.audit(3, {}, metas, [])
    by = {d["target"]: d for d in decisions if d["check"] == "parasite"}
    assert by["M5"]["decision"] == "demoted" and by["M5"]["tainted_ratio"] == 0.75
    assert metas["M5"].worth == 300 and "parasite" in metas["M5"].flags
    assert by["M2"]["decision"] == "clean" and "parasite" not in metas["M2"].flags


@pytest.mark.parametrize(
    "seed", [0, pytest.param(1, marks=pytest.mark.slow), pytest.param(2, marks=pytest.mark.slow)]
)
def test_h59_demo(seed, seeds):
    """Without the auditor Clone (M5) tops the meta table; with it, M5 is flagged and demoted.

    Measured on 8 seeds x 9 generations of this configuration: M5 ranked 1st every time without
    the auditor, and was flagged as a parasite every time with it.
    """
    results = {}
    for auditor in (False, True):
        ev = Evolution(small_game(), small_config(generations=9, seed=seed, auditor=auditor), seeds)
        ev.run()
        results[auditor] = ev
    off, on = results[False].metas, results[True].metas
    assert max(off.values(), key=lambda m: m.worth).id == "M5"
    assert "parasite" in on["M5"].flags
    assert on["M5"].worth < off["M5"].worth
    assert any(
        a["check"] == "parasite" and a["target"] == "M5" and a["decision"] == "demoted"
        for a in results[True].rec.of_type("audit")
    )
