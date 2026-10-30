import pytest

from neurisko.games.autobattler.combat import CompiledRules, simulate
from neurisko.games.autobattler.rules import Ruleset, load_ruleset, parse_ruleset


@pytest.fixture(scope="session")
def rules() -> Ruleset:
    return load_ruleset()


def unit(id: str, **kw) -> dict:
    """A plain test unit; override any stat via keyword arguments."""
    base = dict(id=id, faction="test", cost=1, hp=100, atk=10, armor=0, speed=10, range="melee")
    base.update(kw)
    return base


def make_rules(units: list[dict], synergies: list[dict] | None = None, **limits) -> Ruleset:
    lim = dict(budget=10, max_team_size=5, max_copies=2, max_ticks=600, front_line_size=2)
    lim.update(limits)
    return parse_ruleset(
        dict(name="test", version="t", limits=lim, units=units, synergies=synergies or [])
    )


def fight(rules: Ruleset, a, b, seed: int = 0, log: bool = True):
    return simulate(CompiledRules(rules), tuple(a), tuple(b), seed, log)
