"""Which ruleset files the MCP tools may read: `.toml` files inside the workspace only."""

from __future__ import annotations

import os
from pathlib import Path

from mcp.server.mcpserver.exceptions import ToolError

WORKSPACE_ENV = "NEURISKO_WORKSPACE"


def workspace_root() -> Path:
    """Kiro starts workspace MCP servers in the workspace root; the env var overrides it."""
    return Path(os.environ.get(WORKSPACE_ENV) or Path.cwd()).resolve()


def resolve_ruleset(path: str, root: Path | None = None) -> Path:
    root = (root or workspace_root()).resolve()
    if not path or "\x00" in path:
        raise ToolError("path is empty or invalid")
    p = (root / path).resolve()  # an absolute `path` resolves as given, then must be inside
    if not p.is_relative_to(root):
        raise ToolError(f"{path!r} is outside the workspace; use a path like rulesets/my.toml")
    if p.suffix != ".toml":
        raise ToolError(f"{path!r} is not a .toml ruleset file")
    if not p.is_file():
        raise ToolError(f"{path!r} does not exist")
    return p


def relative(p: Path, root: Path | None = None) -> str:
    return str(p.relative_to((root or workspace_root()).resolve()))
