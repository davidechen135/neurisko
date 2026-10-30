"""Ruleset data model, TOML loading, validation and hashing."""

from __future__ import annotations

import hashlib
import tomllib
from functools import cached_property
from importlib import resources
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

DEFAULT_RULESET = "default.toml"


class RulesetError(ValueError):
    """Raised when a ruleset file cannot be read or fails validation."""


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --- Abilities (discriminated on `kind`, so unknown kinds are rejected) -----------------


class Lifesteal(_Model):
    kind: Literal["lifesteal"]
    fraction: float = Field(gt=0, le=1)


class Dodge(_Model):
    kind: Literal["dodge"]
    chance: float = Field(gt=0, lt=1)


class FirstStrike(_Model):
    kind: Literal["first_strike"]
    multiplier: float = Field(ge=1)


class HealLowestAlly(_Model):
    kind: Literal["heal_lowest_ally"]
    amount: int = Field(ge=1)


class Splash(_Model):
    kind: Literal["splash"]
    fraction: float = Field(gt=0, le=1)  # share of ATK dealt to the enemy behind the target


class IgnoreArmor(_Model):
    kind: Literal["ignore_armor"]


class SummonOnAllyDeath(_Model):
    kind: Literal["summon_on_ally_death"]
    unit: str
    max: int = Field(ge=1)


Ability = Annotated[
    Lifesteal | Dodge | FirstStrike | HealLowestAlly | Splash | IgnoreArmor | SummonOnAllyDeath,
    Field(discriminator="kind"),
]


# --- Rules ------------------------------------------------------------------------------


class UnitDef(_Model):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    faction: str
    cost: int = Field(ge=1)
    hp: int = Field(ge=1)
    atk: int = Field(ge=0)
    armor: int = Field(ge=0)
    speed: int = Field(ge=1, description="Ticks between attacks; lower is faster.")
    range: Literal["melee", "ranged"]
    ability: Ability | None = None


class Synergy(_Model):
    faction: str
    threshold: int = Field(ge=1)
    hp_pct: float = Field(default=0, ge=0)
    atk_pct: float = Field(default=0, ge=0)
    armor_flat: int = Field(default=0, ge=0)
    ability_pct: float = Field(default=0, ge=0)


class Limits(_Model):
    budget: int = Field(ge=1)
    max_team_size: int = Field(ge=1)
    max_copies: int = Field(ge=1)
    max_ticks: int = Field(ge=1)
    front_line_size: int = Field(ge=1)


class Archetype(_Model):
    name: str
    units: list[str] = Field(min_length=1)


class Ruleset(_Model):
    name: str
    version: str
    limits: Limits
    units: list[UnitDef] = Field(min_length=1)
    synergies: list[Synergy] = Field(default_factory=list)
    archetypes: list[Archetype] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_references(self) -> Ruleset:
        ids = [u.id for u in self.units]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate unit ids: {dupes}")
        known = set(ids)
        factions = {u.faction for u in self.units}
        for s in self.synergies:
            if s.faction not in factions:
                raise ValueError(f"synergy references unknown faction {s.faction!r}")
        for u in self.units:
            if isinstance(u.ability, SummonOnAllyDeath) and u.ability.unit not in known:
                raise ValueError(f"unit {u.id!r} summons unknown unit {u.ability.unit!r}")
        for a in self.archetypes:
            unknown = [x for x in a.units if x not in known]
            if unknown:
                raise ValueError(f"archetype {a.name!r} uses unknown units {unknown}")
        if min(u.cost for u in self.units) > self.limits.budget:
            raise ValueError("no unit is affordable within the budget")
        return self

    @cached_property
    def unit_map(self) -> dict[str, UnitDef]:
        return {u.id: u for u in self.units}

    @cached_property
    def hash(self) -> str:
        """Stable short hash of the full ruleset content."""
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()[:12]


def _format_validation_error(err: ValidationError) -> str:
    lines = []
    for e in err.errors():
        loc = ".".join(str(p) for p in e["loc"]) or "<root>"
        lines.append(f"  {loc}: {e['msg']}")
    return "\n".join(lines)


def parse_ruleset(data: dict, source: str = "<dict>") -> Ruleset:
    try:
        return Ruleset.model_validate(data)
    except ValidationError as err:
        raise RulesetError(f"invalid ruleset {source}:\n{_format_validation_error(err)}") from None


def load_ruleset(path: str | Path | None = None) -> Ruleset:
    """Load a ruleset from `path`, or the packaged default ruleset if `path` is None."""
    try:
        if path is None:
            text = resources.files(__package__).joinpath("data", DEFAULT_RULESET).read_text()
            source = f"<packaged {DEFAULT_RULESET}>"
        else:
            text = Path(path).read_text()
            source = str(path)
        data = tomllib.loads(text)
    except (OSError, tomllib.TOMLDecodeError) as err:
        raise RulesetError(f"cannot read ruleset {path}: {err}") from None
    return parse_ruleset(data, source)
