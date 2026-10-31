"""MCP tool logic as plain functions (registered in server.py, unit-tested directly).

Every tool reads a ruleset file from the workspace; none of them writes to it.
"""

from __future__ import annotations

import math
import os
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Literal

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel

from neurisko.engine.game import Patch
from neurisko.games.autobattler import MonsterMash, RulesetError, load_ruleset
from neurisko.games.autobattler.patches import STAT_FIELDS, drop_invalid_archetypes
from neurisko.mcp.paths import relative, resolve_ruleset
from neurisko.report.detect import (
    RunOutcome,
    Thresholds,
    baseline_shares,
    make_specs,
    run_batch,
    share_table,
)
from neurisko.report.report import ReportConfig
from neurisko.report.schema import PartStat
from neurisko.report.verify import verify_patches
from neurisko.runs.session import default_seed_rules

QUICK_SEEDS = 4
QUICK_GENERATIONS = 8
BASELINE_N = 2000
MAX_LOG_LINES = 200
MAX_TEAM = 10
ABILITY_FIELDS = ("amount", "fraction", "chance", "multiplier", "max")
Field = Literal[
    "cost",
    "atk",
    "hp",
    "armor",
    "speed",
    "ability.amount",
    "ability.fraction",
    "ability.chance",
    "ability.multiplier",
    "ability.max",
]


def _workers() -> int:
    return min(QUICK_SEEDS, os.cpu_count() or 1)


# --- loading ---------------------------------------------------------------------------------

_games: OrderedDict[str, MonsterMash] = OrderedDict()  # by ruleset hash; keeps score caches
_games_lock = threading.Lock()


def load_game(path: str) -> tuple[MonsterMash, str, list[str]]:
    """(game, workspace-relative path, archetypes dropped as invalid)."""
    p = resolve_ruleset(path)
    try:
        rules = load_ruleset(p)
    except RulesetError as err:
        raise ToolError(str(err)) from None
    rules, dropped = drop_invalid_archetypes(rules)
    with _games_lock:
        game = _games.get(rules.hash)
        if game is None:
            game = MonsterMash(rules)
            _games[rules.hash] = game
            while len(_games) > 8:
                _games.popitem(last=False)
        _games.move_to_end(rules.hash)
    return game, relative(p), dropped


def _team(game: MonsterMash, team: list[str], label: str) -> tuple[str, ...]:
    if not team or len(team) > MAX_TEAM:
        raise ToolError(f"{label} must list 1 to {MAX_TEAM} unit ids, front first")
    d = tuple(str(u).strip() for u in team)
    errors = game.validate(d)
    if errors:
        raise ToolError(f"{label} is invalid: " + "; ".join(errors))
    return d


# --- check_ruleset -----------------------------------------------------------------------------


class RulesetSummary(BaseModel):
    path: str
    valid: bool
    errors: list[str] = []
    ruleset_hash: str | None = None
    limits: dict[str, int] | None = None
    units: list[dict[str, Any]] = []
    synergies: list[dict[str, Any]] = []
    dropped_archetypes: list[str] = []
    note: str = ""


def check_ruleset(path: str) -> RulesetSummary:
    p = resolve_ruleset(path)
    rel = relative(p)
    try:
        rules = load_ruleset(p)
    except RulesetError as err:
        lines = [ln.strip() for ln in str(err).splitlines()[1:] if ln.strip()] or [str(err)]
        return RulesetSummary(path=rel, valid=False, errors=lines)
    rules, dropped = drop_invalid_archetypes(rules)
    units = []
    for u in rules.units:
        d = u.model_dump(exclude={"ability"})
        d["ability"] = u.ability.model_dump() if u.ability else None
        units.append(d)
    note = (
        f"Archetype opponents no longer valid under these limits (ignored): {', '.join(dropped)}."
        if dropped
        else ""
    )
    return RulesetSummary(
        path=rel,
        valid=True,
        ruleset_hash=rules.hash,
        limits=rules.limits.model_dump(),
        units=units,
        synergies=[s.model_dump() for s in rules.synergies],
        dropped_archetypes=dropped,
        note=note,
    )


# --- simulate_battle / score_team --------------------------------------------------------------


class BattleSummary(BaseModel):
    ruleset_hash: str
    team_a: list[str]
    team_b: list[str]
    seed: int
    winner: Literal["A", "B", "draw"]
    ticks: int
    survivors_a: list[str]
    survivors_b: list[str]
    stats: list[dict[str, Any]]
    log: list[str]
    truncated: bool


def _event_line(e) -> str:
    match e.kind:
        case "attack":
            return f"t{e.tick} {e.actor} hits {e.target} for {e.amount}"
        case "dodge":
            return f"t{e.tick} {e.actor} dodges {e.target}"
        case "heal":
            return f"t{e.tick} {e.actor} heals {e.target} for {e.amount}"
        case "summon":
            return f"t{e.tick} {e.actor} raises {e.target}"
        case "death":
            return f"t{e.tick} {e.actor} dies"
        case _:
            return f"t{e.tick} synergy {'on' if e.kind == 'synergy_on' else 'off'} {e.actor}"


def simulate_battle(
    path: str, team_a: list[str], team_b: list[str], seed: int = 0
) -> BattleSummary:
    game, _, _ = load_game(path)
    a, b = _team(game, team_a, "team_a"), _team(game, team_b, "team_b")
    if not 0 <= seed < 2**31:
        raise ToolError("seed must be in 0..2^31-1")
    r = game.simulate(a, b, seed, log=True)
    lines = [_event_line(e) for e in r.events or []]
    return BattleSummary(
        ruleset_hash=game.ruleset_hash,
        team_a=list(a),
        team_b=list(b),
        seed=seed,
        winner=r.winner,
        ticks=r.ticks,
        survivors_a=r.survivors_a,
        survivors_b=r.survivors_b,
        stats=[
            {
                "unit": s.label,
                "damage_dealt": s.damage_dealt,
                "damage_taken": s.damage_taken,
                "kills": s.kills,
                "healing": s.healing,
                "survived": s.survived,
            }
            for s in r.stats
        ],
        log=lines[:MAX_LOG_LINES],
        truncated=len(lines) > MAX_LOG_LINES,
    )


class TeamScore(BaseModel):
    ruleset_hash: str
    team: list[str]
    score: float
    battles: int
    matchups: list[dict[str, Any]]
    note: str


def score_team(path: str, team: list[str]) -> TeamScore:
    game, _, _ = load_game(path)
    d = _team(game, team, "team")
    rep = game.score(d)
    designs = {o.name: list(o.design) for o in game.gauntlet}
    return TeamScore(
        ruleset_hash=game.ruleset_hash,
        team=list(d),
        score=round(rep.score, 4),
        battles=rep.battles,
        matchups=sorted(
            (
                {
                    "opponent": m.opponent,
                    "design": designs[m.opponent],
                    "wins": m.wins,
                    "draws": m.draws,
                    "losses": m.losses,
                    "score": round(m.score, 3),
                }
                for m in rep.matchups
            ),
            key=lambda m: m["score"],
        ),
        note=(
            f"Win rate (draw = 0.5) against {len(game.gauntlet)} fixed opponents, "
            f"{game.n_seeds} seeds x both sides each. Matchups sorted weakest first."
        ),
    )


# --- quick_balance / verify_patch --------------------------------------------------------------


class QuickBalance(BaseModel):
    path: str
    ruleset_hash: str
    seeds: int
    generations: int
    parts: list[PartStat]
    dominant: list[str]
    underused: list[str]
    champions: list[list[str]]
    dropped_archetypes: list[str]
    seconds: float
    note: str


_detect_cache: dict[str, tuple[list[RunOutcome], list[PartStat]]] = {}
_detect_lock = threading.Lock()


def _quick_config():
    return ReportConfig(generations=QUICK_GENERATIONS).engine_config()


def _detect(game: MonsterMash) -> tuple[list[RunOutcome], list[PartStat]]:
    with _detect_lock:
        hit = _detect_cache.get(game.ruleset_hash)
    if hit is not None:
        return hit
    specs = make_specs(game, range(QUICK_SEEDS), _quick_config(), default_seed_rules(game), top_k=5)
    outcomes = run_batch(specs, workers=_workers())
    table = share_table(game, outcomes, baseline_shares(game, BASELINE_N), Thresholds())
    with _detect_lock:
        _detect_cache[game.ruleset_hash] = (outcomes, table)
    return outcomes, table


def quick_balance(path: str) -> QuickBalance:
    t = time.perf_counter()
    game, rel, dropped = load_game(path)
    outcomes, table = _detect(game)
    return QuickBalance(
        path=rel,
        ruleset_hash=game.ruleset_hash,
        seeds=QUICK_SEEDS,
        generations=QUICK_GENERATIONS,
        parts=table,
        dominant=[p.part for p in table if "dominant" in p.flags],
        underused=[p.part for p in table if "underused" in p.flags],
        champions=[o.champion for o in outcomes],
        dropped_archetypes=dropped,
        seconds=round(time.perf_counter() - t, 1),
        note=(
            f"QUICK check: {QUICK_SEEDS} engine runs x {QUICK_GENERATIONS} generations. "
            "'evolved' = share of top-5 designs containing the unit (mean over runs, lo/hi = "
            "range); 'baseline' = share in random competitive teams; lift = evolved/baseline. "
            "Dominant: evolved >= 0.7 and lift >= 1.8. Shares near 0.5 are noisy at 4 seeds; "
            "use start_report for 8 seeds and verified fixes."
        ),
    )


class PatchCheck(BaseModel):
    path: str
    change: str
    target: str
    target_before: float
    target_after: float
    target_lift_after: float
    most_common_after: str
    most_common_after_share: float
    new_dominant: list[str]
    effective: bool
    failed: list[str]
    dropped_opponents: list[str]
    after: list[PartStat]
    seeds: int
    seconds: float
    note: str


def verify_patch(path: str, unit: str, field: Field, new_value: float) -> PatchCheck:
    t = time.perf_counter()
    game, rel, _ = load_game(path)
    if unit not in game.rules.unit_map:
        raise ToolError(f"unknown unit {unit!r}; units: {', '.join(game.part_names())}")
    if not isinstance(new_value, (int, float)) or not math.isfinite(new_value):
        raise ToolError("new_value must be a finite number")
    u = game.rules.unit_map[unit]
    if field in STAT_FIELDS:
        old = getattr(u, field)
    else:
        param = field.split(".", 1)[1]
        params = u.ability.model_dump() if u.ability else {}
        if param not in params:
            raise ToolError(f"{unit} has no ability parameter {param!r}")
        old = params[param]
    if float(old) == float(new_value):
        raise ToolError(f"{unit}.{field} is already {old}")
    patch = Patch(target=unit, field=field, old=old, new=new_value)
    try:
        game.with_patch(patch)  # validate the new value before spending CPU
    except RulesetError as err:
        raise ToolError(str(err).replace("\n", " ")) from None
    before, _ = _detect(game)
    [res], _ = verify_patches(
        game,
        [patch],
        before,
        list(range(QUICK_SEEDS)),
        _quick_config(),
        default_seed_rules(game),
        Thresholds(),
        5,
        BASELINE_N,
        _workers(),
    )
    return PatchCheck(
        path=rel,
        change=patch.text(),
        target=unit,
        target_before=res.target_before,
        target_after=res.target_after,
        target_lift_after=res.target_lift_after,
        most_common_after=res.top_after,
        most_common_after_share=res.top_after_share,
        new_dominant=res.new_dominant,
        effective=res.effective,
        failed=res.failed,
        dropped_opponents=res.dropped_opponents,
        after=res.after,
        seeds=QUICK_SEEDS,
        seconds=round(time.perf_counter() - t, 1),
        note=(
            "Effective = the unit is no longer dominant, still used (share >= 0.1), and no other "
            f"unit became dominant. Same {QUICK_SEEDS} seeds before and after. The file was not "
            "changed."
        ),
    )


# --- report jobs ------------------------------------------------------------------------------


class JobStatus(BaseModel):
    job_id: str
    state: Literal["running", "done", "failed", "unknown"]
    path: str | None = None
    elapsed_s: float | None = None
    progress: str | None = None
    message: str | None = None
    report_md: str | None = None
    summary: str | None = None
    dominant: list[str] | None = None
    effective_changes: list[str] | None = None


class ReportJobs:
    """At most one full report at a time, in a background thread."""

    def __init__(self, reports_dir: Path = Path("reports"), config: ReportConfig | None = None):
        self.reports_dir = reports_dir
        self.config = config or ReportConfig()
        self.lock = threading.Lock()
        self.jobs: dict[str, dict[str, Any]] = {}
        self.running: str | None = None

    def start(self, path: str) -> JobStatus:
        game, rel, _ = load_game(path)
        with self.lock:
            if self.running is not None:
                st = self.status(self.running)
                st.message = "A report is already running; poll report_status with this job_id."
                return st
            job_id = f"mcp-{time.strftime('%Y%m%d-%H%M%S')}"
            n = 1
            while job_id in self.jobs or (self.reports_dir / job_id).exists():
                n += 1
                job_id = f"mcp-{time.strftime('%Y%m%d-%H%M%S')}-{n}"
            job = {"path": rel, "start": time.time(), "state": "running", "progress": "starting"}
            self.jobs[job_id] = job
            self.running = job_id

        def work() -> None:
            from neurisko.report import build_report, write_report

            try:
                report = build_report(
                    game,
                    default_seed_rules(game),
                    self.config,
                    ruleset_source=rel,
                    progress=lambda m: job.__setitem__("progress", m),
                )
                out = self.reports_dir / job_id
                write_report(report, out)
                job.update(
                    state="done",
                    report_md=str(out / "report.md"),
                    summary=report.summary.template,
                    dominant=[d.part for d in report.dominant],
                    effective=[
                        p.change_text() for d in report.dominant for p in d.patches if p.effective
                    ],
                )
            except Exception as err:  # reported through report_status
                job.update(state="failed", message=f"{type(err).__name__}: {err}")
            finally:
                job["end"] = time.time()
                with self.lock:
                    self.running = None

        threading.Thread(target=work, name=f"report-{job_id}", daemon=True).start()
        st = self.status(job_id)
        st.message = "Started. A full report takes about 2 minutes; poll report_status."
        return st

    def status(self, job_id: str) -> JobStatus:
        job = self.jobs.get(job_id)
        if job is None:
            return JobStatus(
                job_id=job_id,
                state="unknown",
                message="No such job in this server session (jobs are kept in memory only).",
            )
        end = job.get("end", time.time())
        return JobStatus(
            job_id=job_id,
            state=job["state"],
            path=job["path"],
            elapsed_s=round(end - job["start"], 1),
            progress=job.get("progress"),
            message=job.get("message"),
            report_md=job.get("report_md"),
            summary=job.get("summary"),
            dominant=job.get("dominant"),
            effective_changes=job.get("effective"),
        )
