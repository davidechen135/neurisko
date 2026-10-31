"""The report.json schema (version 1)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from neurisko.engine.game import Patch

SCHEMA_VERSION = 1


class PartStat(BaseModel):
    part: str
    evolved: float  # mean share in top designs over runs
    lo: float
    hi: float
    baseline: float
    lift: float
    champion_runs: int
    runs: int
    flags: list[str] = Field(default_factory=list)  # "dominant", "underused"


class Dependence(BaseModel):
    mean: float | None  # None if no champion contains the part
    per_champion: list[dict[str, Any]]  # {seed, champion, score, best_alternative, alt_score}


class Evidence(BaseModel):
    text: str
    worth: float
    applications: int
    improvements: int
    runs: int  # how many detection runs contained this rule


class MatchupGain(BaseModel):
    opponent: str
    with_part: float
    without_part: float
    gain: float


class PatchResult(BaseModel):
    patch: Patch
    base_patches: list[Patch] = Field(default_factory=list)  # applied before `patch` (step 2)
    before: list[PartStat]
    after: list[PartStat]
    target_before: float
    target_after: float
    target_lift_after: float
    top_after: str
    top_after_share: float
    new_dominant: list[str]
    champion_held_out: float
    effective: bool
    failed: list[str]
    dropped_opponents: list[str]
    seconds: float

    def change_text(self) -> str:
        return " + ".join(p.text() for p in [*self.base_patches, self.patch])


class DominantEntry(BaseModel):
    part: str
    dependence: Dependence
    evidence: list[Evidence]
    matchups: list[MatchupGain] | None  # None if too few champions on either side
    matchups_note: str = ""
    patches: list[PatchResult]


class Summary(BaseModel):
    template: str
    llm: str | None = None
    llm_model: str | None = None
    llm_rejected: dict[str, Any] | None = None


class Champion(BaseModel):
    seed: int
    design: list[str]
    held_out: float


class Report(BaseModel):
    schema_version: int = SCHEMA_VERSION
    game: str
    ruleset_hash: str
    ruleset_source: str | None
    config: dict[str, Any]
    engine_config: dict[str, Any]
    seeds: list[int]
    seconds: float
    baseline_n: int
    parts: list[PartStat]
    dominant: list[DominantEntry]
    underused: list[str]
    champions: list[Champion]
    summary: Summary
