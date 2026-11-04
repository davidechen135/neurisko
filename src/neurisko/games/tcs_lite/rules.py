"""TCS-lite ruleset model, loading and hashing."""

from __future__ import annotations

import hashlib
import tomllib
from functools import cached_property
from importlib import resources
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from neurisko.games.autobattler.rules import RulesetError

COMPONENTS = ("hull", "armour", "guns", "drive")
LEVELS = 4
ERAS = {"1981": "tcs-1981.toml", "1982": "tcs-1982.toml"}


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _four(v: list) -> list:
    if len(v) != LEVELS:
        raise ValueError(f"needs exactly {LEVELS} levels")
    return v


class Hull(_Model):
    cost: list[int]
    hp: list[int]

    @model_validator(mode="after")
    def _check(self) -> Hull:
        _four(self.cost), _four(self.hp)
        if min(self.hp) < 1 or min(self.cost) < 0:
            raise ValueError("hull hp must be >= 1 and costs >= 0")
        return self


class Armour(_Model):
    cost: list[int]
    deflect: list[float]  # chance a hit does no damage

    @model_validator(mode="after")
    def _check(self) -> Armour:
        _four(self.cost), _four(self.deflect)
        if not all(0 <= d < 1 for d in self.deflect):
            raise ValueError("deflect must be in [0, 1)")
        return self


class Guns(_Model):
    cost: list[int]
    shots: list[int]

    @model_validator(mode="after")
    def _check(self) -> Guns:
        _four(self.cost), _four(self.shots)
        if min(self.shots) < 1:
            raise ValueError("every gun level must fire at least once")
        return self


class Drive(_Model):
    cost: list[int]
    evade: list[float]  # chance a shot at this ship misses

    @model_validator(mode="after")
    def _check(self) -> Drive:
        _four(self.cost), _four(self.evade)
        if not all(0 <= e < 1 for e in self.evade):
            raise ValueError("evade must be in [0, 1)")
        return self


class Components(_Model):
    hull: Hull
    armour: Armour
    guns: Guns
    drive: Drive


class Limits(_Model):
    budget: int = Field(ge=1)
    max_classes: int = Field(ge=1)
    max_ships_per_class: int = Field(ge=1)
    max_rounds: int = Field(ge=1)
    design_fee: int = Field(ge=0)
    repeat_discount: float = Field(gt=0, le=1)
    slots_per_hull_level: int = Field(ge=1)  # armour+guns+drive <= (hull+1) * this


class Era(_Model):
    year: str
    # Fleets withdraw (lose) when more than this share of their ships can no longer fire.
    max_disabled_fraction: float = Field(default=1.0, gt=0, le=1)
    allow_scuttle: bool = False


class ClassSpec(_Model):
    hull: int = Field(ge=0, lt=LEVELS)
    armour: int = Field(ge=0, lt=LEVELS)
    guns: int = Field(ge=0, lt=LEVELS)
    drive: int = Field(ge=0, lt=LEVELS)
    count: int = Field(default=1, ge=1)

    def levels(self) -> tuple[int, int, int, int]:
        return (self.hull, self.armour, self.guns, self.drive)


class Archetype(_Model):
    name: str
    classes: list[ClassSpec] = Field(min_length=1)
    doctrine: list[str] = Field(default_factory=list)


class Template(_Model):
    name: str
    hull: int = Field(ge=0, lt=LEVELS)
    armour: int = Field(ge=0, lt=LEVELS)
    guns: int = Field(ge=0, lt=LEVELS)
    drive: int = Field(ge=0, lt=LEVELS)

    def levels(self) -> tuple[int, int, int, int]:
        return (self.hull, self.armour, self.guns, self.drive)


class TcsRuleset(_Model):
    name: str
    version: str
    era: Era
    limits: Limits
    components: Components
    templates: list[Template] = Field(min_length=1)
    archetypes: list[Archetype] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check(self) -> TcsRuleset:
        for a in self.archetypes:
            for d in a.doctrine:
                if d != "scuttle_disabled":
                    raise ValueError(f"archetype {a.name!r}: unknown doctrine {d!r}")
        return self

    @cached_property
    def hash(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()[:12]


def parse_ruleset(data: dict, source: str = "<dict>") -> TcsRuleset:
    try:
        return TcsRuleset.model_validate(data)
    except ValidationError as err:
        lines = [
            f"  {'.'.join(str(p) for p in e['loc']) or '<root>'}: {e['msg']}" for e in err.errors()
        ]
        raise RulesetError(f"invalid ruleset {source}:\n" + "\n".join(lines)) from None


def load_ruleset(path: str | Path | None = None, era: str = "1981") -> TcsRuleset:
    try:
        if path is None:
            name = ERAS[era]
            text = resources.files(__package__).joinpath("data", name).read_text()
            source = f"<packaged {name}>"
        else:
            text, source = Path(path).read_text(), str(path)
        data = tomllib.loads(text)
    except (OSError, KeyError, tomllib.TOMLDecodeError) as err:
        raise RulesetError(f"cannot read ruleset {path or era}: {err}") from None
    return parse_ruleset(data, source)
