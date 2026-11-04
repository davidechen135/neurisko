"""The games Neurisko knows. Shared code (engine, runs, report, web, MCP) builds games only
through this module, so it never imports a concrete game."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from neurisko.engine.game import Game

DEFAULT_GAME = "monster-mash"
GAMES = ("monster-mash", "tcs-lite")


def load_game(
    name: str = DEFAULT_GAME,
    ruleset: str | Path | None = None,
    era: str | None = None,
    **settings: Any,
) -> Game:
    """A game from a ruleset file, or its packaged default (`era` picks a TCS-lite default)."""
    if name == "monster-mash":
        from neurisko.games.autobattler import MonsterMash

        return MonsterMash.from_file(ruleset, **settings)
    if name == "tcs-lite":
        from neurisko.games.tcs_lite.game import TcsLite

        return TcsLite.from_file(ruleset, era=era or "1981", **settings)
    raise ValueError(f"unknown game {name!r}; known: {', '.join(GAMES)}")


def make_game(name: str, ruleset_json: str, settings: dict[str, Any] | None = None) -> Game:
    """A game from its ruleset as JSON (used by worker processes and patched rulesets)."""
    settings = settings or {}
    data = json.loads(ruleset_json)
    if name == "monster-mash":
        from neurisko.games.autobattler import MonsterMash
        from neurisko.games.autobattler.rules import parse_ruleset

        return MonsterMash(parse_ruleset(data), **settings)
    if name == "tcs-lite":
        from neurisko.games.tcs_lite.game import TcsLite
        from neurisko.games.tcs_lite.rules import parse_ruleset as parse_tcs

        return TcsLite(parse_tcs(data), **settings)
    raise ValueError(f"unknown game {name!r}; known: {', '.join(GAMES)}")


def game_from_meta(meta: dict) -> Game:
    """Rebuild the game of a recorded run (older runs predate the `game` field)."""
    return load_game(
        meta.get("game") or DEFAULT_GAME,
        meta.get("ruleset"),
        era=meta.get("era"),
        **meta.get("game_settings", {}),
    )
