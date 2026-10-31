import shutil
from importlib import resources
from pathlib import Path

import pytest

from neurisko.mcp import tools as T
from neurisko.mcp.paths import WORKSPACE_ENV

DEFAULT = Path(str(resources.files("neurisko.games.autobattler").joinpath("data", "default.toml")))


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """A workspace with rulesets/monster-mash.toml, set as the MCP workspace root."""
    (tmp_path / "rulesets").mkdir()
    shutil.copy(DEFAULT, tmp_path / "rulesets" / "monster-mash.toml")
    monkeypatch.setenv(WORKSPACE_ENV, str(tmp_path))
    T._games.clear()
    T._detect_cache.clear()
    return tmp_path


@pytest.fixture
def tiny_quick(monkeypatch):
    """Make quick_balance / verify_patch cheap: 2 seeds x 1 generation."""
    monkeypatch.setattr(T, "QUICK_SEEDS", 2)
    monkeypatch.setattr(T, "QUICK_GENERATIONS", 1)
    monkeypatch.setattr(T, "BASELINE_N", 200)
