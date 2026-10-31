import time

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from neurisko.mcp import tools as T
from neurisko.report.report import ReportConfig

RS = "rulesets/monster-mash.toml"


@pytest.mark.parametrize(
    ("path", "message"),
    [
        ("../outside.toml", "outside the workspace"),
        ("/etc/hosts", "outside the workspace"),
        ("rulesets/missing.toml", "does not exist"),
        ("pyproject.py", "not a .toml"),
        ("", "empty"),
    ],
)
def test_path_rejection(workspace, path, message):
    with pytest.raises(ToolError, match=message):
        T.check_ruleset(path)


def test_symlink_escape_rejected(workspace, tmp_path_factory):
    outside = tmp_path_factory.mktemp("out") / "x.toml"
    outside.write_text((workspace / RS).read_text())
    (workspace / "rulesets" / "link.toml").symlink_to(outside)
    with pytest.raises(ToolError, match="outside the workspace"):
        T.check_ruleset("rulesets/link.toml")


def test_check_ruleset(workspace):
    s = T.check_ruleset(RS)
    assert s.valid and s.ruleset_hash and len(s.units) == 12 and s.limits["budget"] == 10
    witch = next(u for u in s.units if u["id"] == "witch")
    assert witch["ability"] == {"kind": "heal_lowest_ally", "amount": 12}


def test_check_ruleset_reports_errors(workspace):
    p = workspace / RS
    p.write_text(p.read_text().replace("cost = 2\nhp = 45", "cost = -2\nhp = 45"))
    s = T.check_ruleset(RS)
    assert not s.valid and any("cost" in e for e in s.errors)
    with pytest.raises(ToolError, match="invalid ruleset"):
        T.score_team(RS, ["zombie"])


def test_cheaper_budget_drops_archetypes(workspace):
    p = workspace / RS
    p.write_text(p.read_text().replace("budget = 10", "budget = 8"))
    s = T.check_ruleset(RS)
    assert s.valid and s.dropped_archetypes and "no longer valid" in s.note
    assert T.score_team(RS, ["zombie", "ghost"]).score >= 0  # still usable


def test_simulate_and_score(workspace):
    b = T.simulate_battle(RS, ["ghost", "pumpkin_mage"], ["gargoyle", "werewolf"], seed=3)
    assert b.winner == "B" and b.log and not b.truncated
    assert b.log[0].startswith("t0 synergy on")
    s = T.score_team(RS, ["zombie", "ghost", "witch"])
    assert 0 <= s.score <= 1 and s.matchups[0]["score"] <= s.matchups[-1]["score"]
    with pytest.raises(ToolError, match="unknown units: lich"):
        T.score_team(RS, ["lich"])
    with pytest.raises(ToolError, match="team_a must list"):
        T.simulate_battle(RS, [], ["zombie"])
    with pytest.raises(ToolError, match="seed"):
        T.simulate_battle(RS, ["zombie"], ["zombie"], seed=-1)


def test_battle_log_truncated(workspace, monkeypatch):
    monkeypatch.setattr(T, "MAX_LOG_LINES", 5)
    b = T.simulate_battle(RS, ["flesh_golem", "witch"], ["flesh_golem", "witch"])
    assert len(b.log) == 5 and b.truncated


def test_quick_balance_and_cache(workspace, tiny_quick):
    q = T.quick_balance(RS)
    assert q.seeds == 2 and q.generations == 1 and len(q.parts) == 12 and len(q.champions) == 2
    assert "QUICK" in q.note
    t = time.perf_counter()
    assert T.quick_balance(RS).parts == q.parts  # cached by ruleset hash
    assert time.perf_counter() - t < 1


@pytest.mark.parametrize(
    ("unit", "field", "value", "message"),
    [
        ("lich", "cost", 3, "unknown unit"),
        ("ghost", "ability.amount", 3, "no ability parameter"),
        ("witch", "cost", 2, "already"),
        ("witch", "cost", 2.5, "whole number"),
        ("bat_swarm", "ability.chance", 1.5, "dodge"),
        ("witch", "cost", float("nan"), "finite"),
    ],
)
def test_verify_patch_validation(workspace, tiny_quick, unit, field, value, message):
    with pytest.raises(ToolError, match=message):
        T.verify_patch(RS, unit, field, value)


def test_verify_patch_does_not_edit_file(workspace, tiny_quick):
    before = (workspace / RS).read_text()
    r = T.verify_patch(RS, "witch", "cost", 3)
    assert r.change == "witch.cost 2->3" and r.seeds == 2
    assert r.dropped_opponents == ["arcane_backline"]
    assert (workspace / RS).read_text() == before


def test_report_job_lifecycle(workspace):
    cfg = ReportConfig(
        seeds=1,
        verify_seeds=1,
        generations=1,
        fix_parts=0,
        baseline_n=100,
        workers=1,
        engine=dict(population=6, design_apps=6, immigrants=1),
    )
    jobs = T.ReportJobs(reports_dir=workspace / "reports", config=cfg)
    first = jobs.start(RS)
    assert first.state == "running" and "Started" in first.message
    second = jobs.start(RS)
    assert second.job_id == first.job_id and "already running" in second.message
    for _ in range(300):
        st = jobs.status(first.job_id)
        if st.state != "running":
            break
        time.sleep(0.1)
    assert st.state == "done", st
    assert st.report_md and (workspace / "reports" / first.job_id / "report.md").exists()
    assert st.summary and st.elapsed_s is not None
    assert jobs.status("nope").state == "unknown"
    third = jobs.start(RS)
    assert third.job_id != first.job_id


@pytest.mark.slow
def test_quick_tools_within_budget(workspace):
    """R2: the slow tools answer within 60 s with the real settings."""
    t = time.perf_counter()
    q = T.quick_balance(RS)
    assert time.perf_counter() - t < 60 and "witch" in q.dominant
    t = time.perf_counter()
    T.verify_patch(RS, "witch", "cost", 3)
    assert time.perf_counter() - t < 60
