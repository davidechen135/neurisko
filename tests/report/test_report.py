import json

import pytest

from neurisko.engine.game import Patch
from neurisko.games.autobattler import MonsterMash
from neurisko.llm import FakeClient
from neurisko.report import ReportConfig, build_report, write_report
from neurisko.report import summary as S
from neurisko.report.detect import (
    RunOutcome,
    Thresholds,
    baseline_shares,
    make_specs,
    run_batch,
    share_table,
)
from neurisko.report.explain import dependence, evidence
from neurisko.report.schema import PartStat, Report
from neurisko.report.verify import judge, needs_follow_up
from neurisko.runs.session import default_seed_rules

TINY_ENGINE = dict(population=8, design_apps=12, immigrants=2)
SETTINGS = dict(n_random=4, n_seeds=1)


def tiny_game():
    return MonsterMash(**SETTINGS)


def tiny_cfg(**kw):
    base = dict(
        seeds=2,
        verify_seeds=2,
        generations=2,
        fix_parts=1,
        baseline_n=200,
        engine=TINY_ENGINE,
        workers=1,
    )
    base.update(kw)
    return ReportConfig(**base)


def outcome(seed, top, champion=None, heuristics=()):
    return RunOutcome(seed=seed, champion=champion or top[0], top=top, heuristics=list(heuristics))


def test_run_batch_independent_of_workers():
    g = tiny_game()
    eng = tiny_cfg().engine_config()
    specs = make_specs(g, [0, 1], eng, default_seed_rules(g), 5)
    one = run_batch(specs, workers=1)
    two = run_batch(specs, workers=2)
    strip = lambda os: [(o.seed, o.champion, o.top, o.heuristics) for o in os]  # noqa: E731
    assert strip(one) == strip(two)
    assert [o.seed for o in one] == [0, 1]


def test_share_table_and_flags():
    g = tiny_game()
    outs = [
        outcome(0, [["witch", "zombie"]] * 4 + [["zombie"]]),
        outcome(1, [["witch", "ghost"]] * 5),
    ]
    base = dict.fromkeys(g.part_names(), 0.3)
    base["necromancer"] = 0.4
    rows = {r.part: r for r in share_table(g, outs, base, Thresholds())}
    w = rows["witch"]
    assert (w.evolved, w.lo, w.hi) == (0.9, 0.8, 1.0)
    assert w.lift == pytest.approx(3.0) and w.flags == ["dominant"] and w.champion_runs == 2
    assert rows["zombie"].evolved == 0.5 and rows["zombie"].flags == []
    assert rows["necromancer"].flags == ["underused"]
    assert rows["skeleton"].flags == ["underused"]


def test_baseline_shares_sum():
    g = tiny_game()
    b = baseline_shares(g, 300)
    assert set(b) == set(g.part_names()) and all(0 < v < 1 for v in b.values())


def test_judge_rules():
    def row(part, share, flags=()):
        return PartStat(
            part=part,
            evolved=share,
            lo=0,
            hi=1,
            baseline=0.3,
            lift=share / 0.3,
            champion_runs=0,
            runs=1,
            flags=list(flags),
        )

    ok = judge("witch", [row("witch", 0.4), row("ghost", 0.5)])
    assert ok == (True, [], [])
    still = judge("witch", [row("witch", 0.8, ["dominant"])])
    assert not still[0] and "still dominant" in still[1][0]
    dead = judge("witch", [row("witch", 0.05)])
    assert not dead[0] and "barely used" in dead[1][0]
    moved = judge("witch", [row("witch", 0.4), row("golem", 0.8, ["dominant"])])
    assert moved == (False, ["new dominant: golem"], ["golem"])


def test_dependence_matches_hand_computation():
    from neurisko.engine.scoring import pool_score

    g = tiny_game()
    champ = ("zombie", "witch", "ghost")
    outs = [outcome(0, [list(champ)]), outcome(1, [["gargoyle", "ghost"]])]
    dep = dependence(g, "witch", outs)
    [row] = dep.per_champion
    held = g.held_out()
    pool = [champ, ("gargoyle", "ghost")]
    best = max(
        pool_score(held, ("zombie", alt, "ghost"), pool, 0.5)
        for alt in g.part_names()
        if alt != "witch" and not g.validate(("zombie", alt, "ghost"))
    )
    assert row["drop"] == pytest.approx(pool_score(held, champ, pool, 0.5) - best, abs=1e-3)
    assert dependence(g, "necromancer", outs).mean is None


def test_evidence_merges_across_runs():
    h = {
        "text": "IF always THEN add witch",
        "action": {"kind": "add_unit", "unit": "witch", "position": "back"},
        "worth": 700,
        "applications": 4,
        "improvements": 3,
    }
    other = {**h, "text": "x", "action": {"kind": "remove_unit", "unit": "witch"}}
    outs = [
        outcome(0, [["witch"]], heuristics=[h, other]),
        outcome(1, [["witch"]], heuristics=[{**h, "worth": 800}]),
    ]
    [e] = evidence(tiny_game(), "witch", outs)
    assert (e.worth, e.applications, e.runs) == (800, 8, 2)


def test_number_check():
    f = {
        "runs": 8,
        "dominant": [
            {
                "part": "witch",
                "share": 0.95,
                "lift": 3.0,
                "patches": [{"change": "witch.cost 2->3", "share_after": 0.4}],
            }
        ],
    }
    assert S.unsupported_numbers("witch is in 95% of designs (0.95), lift 3.0, 8 runs", f) == []
    assert S.unsupported_numbers("cost 2->3 drops it to 40%", f) == []
    assert S.unsupported_numbers("witch wins 73% of fights", f) == ["73%"]
    assert S.unsupported_numbers("a 0.81 share", f) == ["0.81"]
    assert S.unsupported_numbers("ruleset f22da09334d3 and unit H27", f) == []  # not numbers


def test_llm_summary_accept_and_reject():
    f = {"runs": 8, "share": 0.95}
    good = FakeClient(replies=[json.dumps({"summary": "witch appears in 95% over 8 runs"})])
    assert S.llm_summary(good, f) == ("witch appears in 95% over 8 runs", None)
    bad = FakeClient(replies=[json.dumps({"summary": "witch wins 73% of fights"})])
    text, rej = S.llm_summary(bad, f)
    assert text is None and rej["numbers"] == ["73%"]
    broken = FakeClient(replies=["nope"])
    assert S.llm_summary(broken, f)[1]["reason"] == "no summary in reply"
    down = FakeClient(replies=[TimeoutError("slow")])
    assert S.llm_summary(down, f)[1]["reason"] == "llm error"


def test_summary_must_state_the_recommended_change():
    """A real Qwen failure: correct numbers, but the effective fix was described as failing."""
    steps = [
        {"part": "witch", "field": "cost", "old": 2, "new": 3},
        {"part": "flesh_golem", "field": "atk", "old": 10, "new": 8},
    ]
    f = {
        "recommended_change": "witch.cost 2->3 + flesh_golem.atk 10->8",
        "recommended_steps": steps,
        "share": 0.67,
    }
    good = "Raise witch cost from 2 to 3 and lower flesh golem attack from 10 to 8 (witch 67%)."
    assert S.missing_recommendation(good, f) == []
    vague = "Adjusting flesh_golem's attack to 8 keeps witch dominant at 67%."
    assert S.missing_recommendation(vague, f) == ["witch.cost -> 3"]
    llm = FakeClient(replies=[json.dumps({"summary": vague})])
    assert S.llm_summary(llm, f)[1]["reason"] == "recommended change not stated"


def test_needs_follow_up():
    from neurisko.report.schema import PatchResult

    def res(target_after, failed, new_dom, eff=False):
        return PatchResult(
            patch=Patch(target="witch", field="cost", old=2, new=3),
            before=[],
            after=[],
            target_before=0.9,
            target_after=target_after,
            target_lift_after=target_after / 0.3,
            top_after="golem",
            top_after_share=0.8,
            new_dominant=new_dom,
            champion_held_out=1,
            effective=eff,
            failed=failed,
            dropped_opponents=[],
            seconds=0,
        )

    moved = res(0.4, ["new dominant: golem"], ["golem"])
    still = res(0.8, ["witch is still dominant"], [])
    assert needs_follow_up([still, moved]) is moved
    assert needs_follow_up([still]) is None
    assert needs_follow_up([moved, res(0.3, [], [], eff=True)]) is None


def test_build_and_write_report_end_to_end(tmp_path):
    """Tiny config with thresholds lowered so the pipeline exercises every stage."""
    g = tiny_game()
    th = Thresholds(dominant_share=0.0, dominant_lift=0.0)
    cfg = tiny_cfg(thresholds=th)
    llm = FakeClient(replies=[json.dumps({"summary": "made-up 73% claim"})])
    msgs = []
    r = build_report(g, default_seed_rules(g), cfg, llm=llm, progress=msgs.append)
    assert r.dominant and r.dominant[0].patches
    assert r.summary.template and r.summary.llm is None
    assert r.summary.llm_rejected["numbers"] == ["73%"]
    assert any(m.startswith("detect") for m in msgs) and any("verify" in m for m in msgs)
    write_report(r, tmp_path / "rep")
    assert Report.model_validate_json((tmp_path / "rep" / "report.json").read_text()) == r
    md = (tmp_path / "rep" / "report.md").read_text()
    assert "## Summary" in md and "Candidate fixes" in md and "LLM summary was discarded" in md
    with pytest.raises(FileExistsError):
        write_report(r, tmp_path / "rep")


def test_cli_report(tmp_path, capsys):
    from neurisko.cli import main

    args = [
        "report",
        "--seeds",
        "1",
        "--verify-seeds",
        "1",
        "--generations",
        "1",
        "--fix-parts",
        "0",
        "--workers",
        "1",
        "--reports-dir",
        str(tmp_path),
        "--report-id",
        "r",
    ]
    assert main(args) == 0
    assert (tmp_path / "r" / "report.md").exists()
    assert "report written" in capsys.readouterr().out


@pytest.mark.slow
def test_default_ruleset_acceptance():
    """R8: witch is flagged and an effective change starting with a witch patch is found."""
    g = MonsterMash()
    r = build_report(g, default_seed_rules(g), ReportConfig())
    dom = {d.part: d for d in r.dominant}
    assert "witch" in dom
    effective = [p for p in dom["witch"].patches if p.effective]
    assert effective
    first = (effective[0].base_patches or [effective[0].patch])[0]
    assert first.target == "witch"
    assert r.seconds < 300
