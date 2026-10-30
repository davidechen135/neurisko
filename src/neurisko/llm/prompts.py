"""Prompts for the Invent meta-heuristic, built from the game's own vocabulary."""

from __future__ import annotations

import json
from typing import Any

from neurisko.engine.game import ActionSchema

SYSTEM_TEMPLATE = """\
You are the Invent meta-heuristic of Neurisko, a modern re-implementation of Douglas Lenat's \
Eurisko (1981). You write heuristics that turn a team design into a stronger one.

{rules}

A heuristic is JSON:
{{"name": short title,
 "rationale": why it should work, at most 200 characters,
 "if": a list of 0 to 3 conditions {{"feature": FEATURE, "op": "<"|"<="|">"|">="|"=="|"!=", \
"value": number}},
 "then": exactly one action}}

Actions:
{actions}

FEATURE is one of: {features}
winrate_vs_X is the design's win rate (0 to 1) against opponent X.

Reply with JSON only: {{"heuristics": [ ... ]}}. Use only the features, actions and values listed \
above. Propose rules that are different from the existing ones and that fix the weaknesses shown \
in the evidence."""


def _action_lines(schema: ActionSchema) -> str:
    lines = []
    for kind, params in schema.items():
        fields = ", ".join([f'"kind": "{kind}"'] + [f'"{p}": {p.upper()}' for p in params])
        domains = "; ".join(f"{p.upper()} in {{{', '.join(v)}}}" for p, v in params.items())
        lines.append(f"  {{{fields}}}  where {domains}")
    return "\n".join(lines)


def system_prompt(rules_text: str, features: list[str], schema: ActionSchema) -> str:
    return SYSTEM_TEMPLATE.format(
        rules=rules_text, actions=_action_lines(schema), features=", ".join(features)
    )


def user_prompt(generation: int, evidence: dict[str, Any], k: int) -> str:
    lines = [
        f"Generation {generation}. Score = win rate against the opponent pool (a fixed gauntlet "
        "plus a hall of fame of the strongest designs found so far).",
        "",
        "Best designs:",
    ]
    for i, d in enumerate(evidence["designs"], 1):
        worst = ", ".join(f"{name} {s:.2f}" for name, s in d["worst"])
        lines.append(f"  {i}. {d['text']} score {d['score']:.3f}; worst matchups: {worst}")
    for title, key in (("Best heuristics", "best"), ("Worst heuristics", "worst")):
        lines.append(f"{title} (worth 0-1000, applications, improvements):")
        for h in evidence[key] or [{"line": "(none yet)"}]:
            lines.append(f"  {h['line']}")
    if evidence.get("flags"):
        lines.append("Recent audit findings: " + "; ".join(evidence["flags"]))
    lines += ["", f"Propose up to {k} new heuristics."]
    return "\n".join(lines)


def retry_prompt(errors: list[str]) -> str:
    listed = "\n".join(f"- {e}" for e in errors[:12])
    return (
        f"None of those heuristics were valid:\n{listed}\n"
        'Reply again with JSON {"heuristics": [...]} using only the allowed features, actions and '
        "values."
    )


def extract_items(text: str) -> tuple[list[Any], str | None]:
    """The list of raw heuristic objects in a reply, or an error message."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as err:
        return [], f"reply is not JSON: {err.msg}"
    if isinstance(data, dict) and isinstance(data.get("heuristics"), list):
        return data["heuristics"], None
    if isinstance(data, list):
        return data, None
    if isinstance(data, dict) and "then" in data:
        return [data], None
    return [], 'reply has no "heuristics" list'
