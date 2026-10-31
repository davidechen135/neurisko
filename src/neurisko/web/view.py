"""The view model the frontend renders: compact events plus run metadata.

`compact_event` is the single place that decides what the UI sees. It is used both by the static
export and by the live SSE stream, so both modes render identically.
"""

from __future__ import annotations

from typing import Any

from neurisko.engine.game import Game

KEEP_CONFIG = (
    "generations",
    "seed",
    "auditor",
    "population",
    "hof_cap",
    "hof_weight",
    "audit_every",
    "max_llm_calls_per_generation",
)
GEN_KEYS = (
    "best",
    "best_text",
    "best_pool",
    "best_gauntlet",
    "best_held_out",
    "best_held_out_pool",
    "hof",
    "applications",
    "improvements",
    "created",
    "audit_actions",
    "worth",
    "elapsed_s",
)
MAX_TEXT = 4000


def _clip(text: str, n: int = MAX_TEXT) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


def compact_event(e: dict) -> dict | None:
    """The UI form of a recorded event, or None if the UI does not need it."""
    t = e["type"]
    base = {"t": e["t"], "gen": e["gen"], "type": t}
    if t == "run_start":
        cfg = e.get("config", {})
        return {
            **base,
            "game": e.get("game"),
            "ruleset_hash": e.get("ruleset_hash"),
            "llm": e.get("llm"),
            "config": {k: cfg[k] for k in KEEP_CONFIG if k in cfg},
        }
    if t == "heuristic_created":
        h = e["heuristic"]
        return {
            **base,
            "id": h["id"],
            "level": h["level"],
            "name": h["name"],
            "rationale": h.get("rationale", ""),
            "by": h["origin"]["by"],
            "parent": h["origin"].get("parent"),
            "text": e.get("text", ""),
        }
    if t == "heuristic_rejected":
        return {**base, "by": e.get("by"), "errors": e.get("errors", [])[:5]}
    if t == "generation":
        out = {**base, **{k: e[k] for k in GEN_KEYS if k in e}}
        out["population"] = e.get("population", [])[:5]
        return out
    if t == "llm_call":
        msgs = e.get("messages", [])
        user = next((m["content"] for m in reversed(msgs) if m["role"] == "user"), "")
        return {
            **base,
            "model": e.get("model"),
            "attempt": e.get("attempt"),
            "prompt": _clip(user),
            "response": _clip(e.get("response", "")),
            "prompt_tokens": e.get("prompt_tokens"),
            "completion_tokens": e.get("completion_tokens"),
            "latency_s": e.get("latency_s"),
        }
    if t in ("llm_error", "llm_skipped", "audit", "hof_added", "hof_removed", "retired"):
        return {**base, **{k: v for k, v in e.items() if k not in base}}
    if t == "meta_applied":
        return {**base, "heuristic": e["heuristic"], "created": e.get("created", [])}
    if t == "run_end":
        return {**base, **{k: v for k, v in e.items() if k not in base}}
    return None  # "applied" and anything new: summarised in `generation`


def compact_events(events: list[dict]) -> list[dict]:
    return [c for c in (compact_event(e) for e in events) if c is not None]


def system_prompt_of(events: list[dict]) -> str | None:
    """The (constant) Invent system prompt, shown once in the LLM tab."""
    for e in events:
        if e["type"] == "llm_call":
            return next(
                (m["content"] for m in e.get("messages", []) if m["role"] == "system"), None
            )
    return None


def battle_key(a: list[str], b: list[str], seed: int) -> str:
    return f"{','.join(a)}|{','.join(b)}|{seed}"


def battle_view(game: Game, a: list[str], b: list[str], seed: int) -> dict[str, Any]:
    r = game.simulate(tuple(a), tuple(b), seed, log=True)
    return {
        "a": a,
        "b": b,
        "seed": seed,
        "winner": r.winner,
        "ticks": r.ticks,
        "events": [[ev.tick, ev.kind, ev.actor, ev.target, ev.amount] for ev in r.events or []],
        "stats": [
            [s.label, s.damage_dealt, s.damage_taken, s.kills, s.healing, s.summons, s.survived]
            for s in r.stats
        ],
    }


def featured_battles(game: Game, events: list[dict], n_worst: int = 3) -> dict[str, dict]:
    """Battles worth showing: the final champion against its weakest gauntlet matchups and
    the strongest other hall-of-fame design."""
    gens = [e for e in events if e["type"] == "generation"]
    if not gens:
        return {}
    last = gens[-1]
    champ = list(last["best"])
    report = game.score(tuple(champ))
    names = {o.name: list(o.design) for o in game.gauntlet}
    worst = sorted(report.matchups, key=lambda m: m.score)[:n_worst]
    opponents = [names[m.opponent] for m in worst if m.opponent in names]
    others = [list(h) for h in last.get("hof", []) if list(h) != champ]
    if others:
        opponents.append(max(others, key=lambda h: game.score(tuple(h)).score))
    out = {}
    for opp in opponents:
        key = battle_key(champ, opp, 0)
        out[key] = battle_view(game, champ, opp, 0)
    return out


def run_view(
    run_id: str, meta: dict, events: list[dict], game: Game, battles: bool = True
) -> dict[str, Any]:
    return {
        "id": run_id,
        "meta": {
            "game": meta.get("game"),
            "ruleset_hash": meta.get("ruleset_hash"),
            "llm_model": meta.get("llm_model"),
            "started": meta.get("started"),
            "finished": meta.get("finished"),
            "battles": meta.get("battles"),
            "llm_calls": meta.get("llm_calls"),
            "git_commit": meta.get("git_commit"),
            "config": {k: meta.get("config", {}).get(k) for k in KEEP_CONFIG},
        },
        "rules_text": game.describe_rules(),
        "system_prompt": system_prompt_of(events),
        "events": compact_events(events),
        "battles": featured_battles(game, events) if battles else {},
    }


def h59_view(off: tuple[dict, list[dict]], on: tuple[dict, list[dict]]) -> dict[str, Any]:
    """Meta-heuristic worth per generation for the same run without and with the auditor."""

    def series(events: list[dict]) -> dict[str, Any]:
        gens = [e for e in events if e["type"] == "generation"]
        metas = sorted({k for g in gens for k in g["worth"] if k.startswith("M")})
        return {
            "worth": {m: [g["worth"].get(m) for g in gens] for m in metas},
            "audits": [
                {k: a[k] for k in ("gen", "check", "target", "decision") if k in a}
                | {"numbers": {k: v for k, v in a.items() if k not in ("t", "type")}}
                for a in events
                if a["type"] == "audit" and a["target"].startswith("M")
            ],
        }

    meta_off, ev_off = off
    meta_on, ev_on = on
    return {
        "config": meta_off.get("config"),
        "game_settings": meta_off.get("game_settings"),
        "off": series(ev_off),
        "on": series(ev_on),
    }
