import pytest

from neurisko.engine.evolve import EvolveConfig
from neurisko.engine.heuristics import Condition, Heuristic, Origin
from neurisko.games.autobattler import MonsterMash
from neurisko.runs.session import default_seed_rules


def small_game() -> MonsterMash:
    """A cheaper gauntlet (12 opponents x 2 seeds) so engine tests stay fast."""
    return MonsterMash(n_random=6, n_seeds=2)


def small_config(**kw) -> EvolveConfig:
    base = dict(generations=4, seed=0, population=12, design_apps=24, immigrants=2)
    base.update(kw)
    return EvolveConfig(**base)


@pytest.fixture
def game() -> MonsterMash:
    return small_game()


@pytest.fixture
def seeds(game):
    return default_seed_rules(game)


def heuristic(id: str, conditions=(), action=None, by="seed", worth=500.0) -> Heuristic:
    return Heuristic(
        id=id,
        level="design",
        name=id,
        conditions=[Condition(**c) for c in conditions],
        action=action or {"kind": "add_unit", "unit": "skeleton", "position": "back"},
        worth=worth,
        origin=Origin(by=by),
    )
