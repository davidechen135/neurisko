"""Rebuild a game from its name and ruleset JSON (used by worker processes)."""

from __future__ import annotations

import json
from typing import Any

from neurisko.engine.game import Game


def make_game(name: str, ruleset_json: str, settings: dict[str, Any] | None = None) -> Game:
    settings = settings or {}
    if name == "monster-mash":
        from neurisko.games.autobattler import MonsterMash
        from neurisko.games.autobattler.rules import parse_ruleset

        return MonsterMash(parse_ruleset(json.loads(ruleset_json)), **settings)
    raise ValueError(f"unknown game {name!r}")
