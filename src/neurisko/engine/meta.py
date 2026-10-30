"""Meta-heuristics: rules that create design heuristics.

M1 Invent asks the LLM. M2-M5 are plain code. M5 Clone exists on purpose: it is the cheapest
way to reproduce the pattern of Eurisko's parasitic heuristic H59 (credit for work that other
heuristics already do), so the auditor's fix can be demonstrated. It is an analogue, not a
recreation of Lenat's code.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from neurisko.engine.game import ActionSchema, Game
from neurisko.engine.heuristics import (
    MAX_CONDITIONS,
    Condition,
    Heuristic,
    Origin,
    parse_rule,
)
from neurisko.llm import LLMClient, LLMError, prompts
from neurisko.runs import Recorder

META_DEFS = [
    ("M1", "Invent", "Asks the LLM to propose new heuristics from the evidence."),
    ("M2", "Specialize", "Adds a condition taken from a design where the heuristic worked."),
    ("M3", "Generalize", "Drops one condition from a heuristic."),
    ("M4", "Retarget", "Changes one parameter of a heuristic's action."),
    ("M5", "Clone", "Copies a high-worth heuristic unchanged (H59 analogue)."),
]
NAME_MAX = 80


def make_metas() -> dict[str, Heuristic]:
    return {
        mid: Heuristic(id=mid, level="meta", name=name, rationale=text, origin=Origin(by="builtin"))
        for mid, name, text in META_DEFS
    }


@dataclass(slots=True)
class Proposal:
    name: str
    rationale: str
    conditions: list[Condition]
    action: dict[str, str]
    parent: str | None = None


@dataclass
class MetaContext:
    game: Game
    rng: random.Random
    generation: int
    heuristics: list[Heuristic]  # alive design heuristics
    features_of: Callable[[Any], dict[str, float]]
    recorder: Recorder
    llm: LLMClient | None = None
    llm_budget: list[int] = field(default_factory=lambda: [0])  # mutable: calls left this gen
    evidence: Callable[[], dict] | None = None
    invent_k: int = 3


def _short(name: str) -> str:
    return name if len(name) <= NAME_MAX else name[: NAME_MAX - 1] + "…"


def _pick_by_worth(rng: random.Random, hs: list[Heuristic]) -> Heuristic | None:
    if not hs:
        return None
    return rng.choices(hs, weights=[h.worth + 1 for h in hs])[0]


def specialize(ctx: MetaContext) -> list[Proposal]:
    pool = [
        h
        for h in ctx.heuristics
        if len(h.conditions) < MAX_CONDITIONS and any(d > 0 for _, _, d in h.stats.recent)
    ]
    h = _pick_by_worth(ctx.rng, pool)
    if h is None:
        return []
    parent = ctx.rng.choice([p for p, _, d in h.stats.recent if d > 0])
    feats = ctx.features_of(parent)
    used = {c.feature for c in h.conditions}
    options = [f for f in ctx.game.feature_names() if f not in used and f in feats]
    if not options:
        return []
    f = ctx.rng.choice(options)
    cond = Condition(feature=f, op=ctx.rng.choice([">=", "<="]), value=feats[f])
    return [
        Proposal(
            _short(f"{h.name} [when {cond.text()}]"),
            h.rationale,
            [*h.conditions, cond],
            dict(h.action),
            h.id,
        )
    ]


def generalize(ctx: MetaContext) -> list[Proposal]:
    h = _pick_by_worth(ctx.rng, [h for h in ctx.heuristics if h.conditions])
    if h is None:
        return []
    drop = ctx.rng.randrange(len(h.conditions))
    conds = [c for i, c in enumerate(h.conditions) if i != drop]
    gone = h.conditions[drop].text()
    return [Proposal(_short(f"{h.name} [not {gone}]"), h.rationale, conds, dict(h.action), h.id)]


def retarget(ctx: MetaContext) -> list[Proposal]:
    schema: ActionSchema = ctx.game.action_schema()
    h = _pick_by_worth(ctx.rng, ctx.heuristics)
    if h is None:
        return []
    params = schema.get(h.action.get("kind"), {})
    choices = [p for p, allowed in params.items() if len(allowed) > 1]
    if not choices:
        return []
    p = ctx.rng.choice(choices)
    value = ctx.rng.choice([v for v in params[p] if v != h.action[p]])
    action = {**h.action, p: value}
    return [
        Proposal(_short(f"{h.name} [{p}={value}]"), h.rationale, list(h.conditions), action, h.id)
    ]


def clone(ctx: MetaContext) -> list[Proposal]:
    used = [h for h in ctx.heuristics if h.stats.applications > 0]
    if not used:
        return []
    h = max(used, key=lambda x: (x.worth, x.id))
    return [
        Proposal(
            _short(f"{h.name} (copy)"),
            f"Copy of {h.id}. {h.rationale}",
            list(h.conditions),
            dict(h.action),
            h.id,
        )
    ]


def invent(ctx: MetaContext) -> list[Proposal]:
    """Ask the LLM for new heuristics; keep the valid ones. One retry if none are valid."""
    if ctx.llm is None or ctx.evidence is None:
        return []
    game = ctx.game
    features, schema = game.feature_names(), game.action_schema()
    messages = [
        {
            "role": "system",
            "content": prompts.system_prompt(game.describe_rules(), features, schema),
        },
        {
            "role": "user",
            "content": prompts.user_prompt(ctx.generation, ctx.evidence(), ctx.invent_k),
        },
    ]
    for attempt in (0, 1):
        if ctx.llm_budget[0] <= 0:
            ctx.recorder.emit("llm_skipped", ctx.generation, reason="budget", attempt=attempt)
            return []
        ctx.llm_budget[0] -= 1
        try:
            resp = ctx.llm.complete(messages)
        except LLMError as err:
            ctx.recorder.emit("llm_error", ctx.generation, error=str(err), attempt=attempt)
            return []
        ctx.recorder.emit(
            "llm_call",
            ctx.generation,
            model=ctx.llm.model,
            attempt=attempt,
            messages=messages,
            response=resp.text,
            prompt_tokens=resp.prompt_tokens,
            completion_tokens=resp.completion_tokens,
            latency_s=round(resp.latency_s, 3),
        )
        items, problem = prompts.extract_items(resp.text)
        errors = [problem] if problem else []
        out: list[Proposal] = []
        for i, raw in enumerate(items[: ctx.invent_k]):
            spec, errs = parse_rule(raw, features, schema)
            if spec is None:
                ctx.recorder.emit(
                    "heuristic_rejected", ctx.generation, by="M1", item=raw, errors=errs
                )
                errors += [f"item {i}: {e}" for e in errs]
            else:
                out.append(
                    Proposal(_short(spec.name), spec.rationale, spec.conditions, spec.action)
                )
        if out:
            return out
        messages = [
            *messages,
            {"role": "assistant", "content": resp.text},
            {"role": "user", "content": prompts.retry_prompt(errors or ["no heuristics given"])},
        ]
    return []


RUNNERS: dict[str, Callable[[MetaContext], list[Proposal]]] = {
    "M1": invent,
    "M2": specialize,
    "M3": generalize,
    "M4": retarget,
    "M5": clone,
}
