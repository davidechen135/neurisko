"""Live check against the endpoint in `.env`. Run with: uv run pytest -m llm"""

import pytest

from neurisko.engine.meta import MetaContext, invent
from neurisko.games.autobattler import MonsterMash
from neurisko.llm import OpenAICompatClient
from neurisko.runs import Recorder
from neurisko.settings import Settings


@pytest.mark.llm
def test_live_invent_returns_valid_heuristics():
    s = Settings()
    llm = OpenAICompatClient(
        s.llm_base_url, s.llm_model, s.llm_api_key.get_secret_value(), timeout_s=s.llm_timeout_s
    )
    game = MonsterMash()
    rec = Recorder()
    d = ("zombie", "zombie", "pumpkin_mage", "pumpkin_mage", "witch")
    r = game.score(d)
    evidence = {
        "designs": [{"text": game.describe(d), "score": r.score, "worst": [("armor_wall", 0.5)]}],
        "best": [],
        "worst": [],
    }
    import random

    ctx = MetaContext(
        game=game,
        rng=random.Random(0),
        generation=1,
        heuristics=[],
        features_of=lambda x: game.features(x, game.score(x)),
        recorder=rec,
        llm=llm,
        llm_budget=[2],
        evidence=lambda: evidence,
    )
    proposals = invent(ctx)
    assert proposals, rec.events
    assert rec.of_type("llm_call")
