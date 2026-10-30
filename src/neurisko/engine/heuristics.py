"""Heuristics as validated data.

Design heuristics are `IF conditions on design features THEN action on the design`. Our code
interprets them; nothing written by the LLM is executed. Meta-heuristics are built-in code, but
they are recorded with the same model so their worth sits in the same table, as in Eurisko.
"""

from __future__ import annotations

import operator
import tomllib
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from neurisko.engine.game import ActionSchema

Op = Literal["<", "<=", ">", ">=", "==", "!="]
OPS = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "==": operator.eq,
    "!=": operator.ne,
}
WORTH_MIN, WORTH_INIT, WORTH_MAX = 0.0, 500.0, 1000.0
MAX_CONDITIONS = 3
MAX_RATIONALE = 200


class Condition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    feature: str
    op: Op
    value: float

    def holds(self, feats: dict[str, float]) -> bool:
        v = feats.get(self.feature)
        return v is not None and OPS[self.op](v, self.value)

    def text(self) -> str:
        v = int(self.value) if float(self.value).is_integer() else round(self.value, 3)
        return f"{self.feature}{self.op}{v}"


class RuleSpec(BaseModel):
    """The part of a design heuristic that the LLM or a seed file provides."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    name: str = Field(min_length=1, max_length=80)
    rationale: str = ""
    conditions: list[Condition] = Field(default_factory=list, alias="if")
    action: dict[str, Any] = Field(alias="then")

    @field_validator("rationale")
    @classmethod
    def _truncate(cls, v: str) -> str:
        return v[:MAX_RATIONALE]

    @field_validator("action")
    @classmethod
    def _stringify(cls, v: dict[str, Any]) -> dict[str, Any]:
        return {k: str(x) for k, x in v.items()}


class Origin(BaseModel):
    by: str  # "seed" or a meta-heuristic id
    parent: str | None = None
    generation: int = 0


class Contribution(BaseModel):
    """One piece of lineage credit a meta-heuristic received through a child heuristic."""

    child: str
    reward: float  # already scaled by lambda
    revoked: bool = False


class Stats(BaseModel):
    applications: int = 0
    improvements: int = 0
    direct_credit: float = 0.0
    lineage_credit: float = 0.0
    dormant_generations: int = 0
    contributions: list[Contribution] = Field(default_factory=list)
    # last (parent, child) designs, for the auditor; runtime only
    recent: list[tuple[Any, Any]] = Field(default_factory=list, exclude=True)


class Heuristic(BaseModel):
    id: str
    level: Literal["design", "meta"]
    name: str
    rationale: str = ""
    conditions: list[Condition] = Field(default_factory=list)
    action: dict[str, str] = Field(default_factory=dict)
    worth: float = WORTH_INIT
    origin: Origin
    stats: Stats = Field(default_factory=Stats)
    alive: bool = True
    flags: list[str] = Field(default_factory=list)

    def matches(self, feats: dict[str, float]) -> bool:
        return all(c.holds(feats) for c in self.conditions)

    def text(self) -> str:
        if self.level == "meta":
            return self.rationale
        cond = " AND ".join(c.text() for c in self.conditions) or "always"
        params = ", ".join(f"{k}={v}" for k, v in self.action.items() if k != "kind")
        return f"IF {cond} THEN {self.action.get('kind')}({params})"

    def summary(self) -> dict:
        """Compact record for events (no runtime-only fields, no contribution list)."""
        return self.model_dump(exclude={"stats": {"contributions"}})


def validate_rule(
    conditions: list[Condition], action: dict[str, str], features: list[str], schema: ActionSchema
) -> list[str]:
    """Every problem with a design heuristic's conditions and action; empty means valid."""
    errors: list[str] = []
    known = set(features)
    if len(conditions) > MAX_CONDITIONS:
        errors.append(f"at most {MAX_CONDITIONS} conditions allowed, got {len(conditions)}")
    for c in conditions:
        if c.feature not in known:
            errors.append(f"unknown feature {c.feature!r}")
    kind = action.get("kind")
    if kind not in schema:
        errors.append(f"unknown action kind {kind!r}; allowed: {', '.join(schema)}")
        return errors
    params = schema[kind]
    for p, allowed in params.items():
        if p not in action:
            errors.append(f"{kind} needs parameter {p!r}")
        elif action[p] not in allowed:
            errors.append(f"{kind}.{p}={action[p]!r} not allowed")
    extra = set(action) - set(params) - {"kind"}
    if extra:
        errors.append(f"{kind} has unknown parameters {sorted(extra)}")
    return errors


def parse_rule(
    raw: Any, features: list[str], schema: ActionSchema
) -> tuple[RuleSpec | None, list[str]]:
    """Parse and validate one raw rule (from JSON or TOML). Returns (spec, errors)."""
    try:
        spec = RuleSpec.model_validate(raw)
    except ValidationError as err:
        msgs = [f"{'.'.join(map(str, e['loc'])) or '<item>'}: {e['msg']}" for e in err.errors()]
        return None, msgs
    errors = validate_rule(spec.conditions, spec.action, features, schema)
    return (None, errors) if errors else (spec, [])


def load_seed_rules(path: Path, features: list[str], schema: ActionSchema) -> list[RuleSpec]:
    """Load a seed heuristic file; every rule must be valid."""
    data = tomllib.loads(path.read_text())
    specs: list[RuleSpec] = []
    for i, raw in enumerate(data.get("heuristics", [])):
        spec, errors = parse_rule(raw, features, schema)
        if spec is None:
            raise ValueError(f"{path}: seed heuristic {i} is invalid: {'; '.join(errors)}")
        specs.append(spec)
    return specs
