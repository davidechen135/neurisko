"""The view model the frontend renders: compact events plus run metadata.

`compact_event` is the single place that decides what the UI sees. It is used both by the static
export and by the live SSE stream, so both modes render identically.
"""

from __future__ import annotations

import json
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


def battle_view(game: Game, a: Any, b: Any, seed: int) -> dict[str, Any]:
    """A battle between two designs (game objects, not JSON), ready for the player."""
    r = game.simulate(a, b, seed, log=True)
    return {
        "a": game.to_json(a),
        "b": game.to_json(b),
        "a_text": game.describe(a),
        "b_text": game.describe(b),
        "seed": seed,
        "winner": r.winner,
        "ticks": r.ticks,
        "time_unit": "round" if game.name == "tcs-lite" else "tick",
        "lines": [[ev.kind, game.describe_event(ev)] for ev in r.events or []],
        "stats": [
            [s.label, s.damage_dealt, s.damage_taken, s.kills, s.healing, s.summons, s.survived]
            for s in r.stats
        ],
    }


def featured_battles(game: Game, events: list[dict], n_worst: int = 3) -> dict[str, dict]:
    """Battles worth showing: the final champion against its weakest fixed matchups and the
    strongest other hall-of-fame design."""
    gens = [e for e in events if e["type"] == "generation"]
    if not gens:
        return {}
    last = gens[-1]
    champ = game.from_json(last["best"])
    opponents = game.featured_opponents(champ, n_worst)
    others = [game.from_json(h) for h in last.get("hof", [])]
    others = [h for h in others if h != champ]
    if others:
        opponents.append(max(others, key=lambda h: game.score(h).score))
    return {f"{i}": battle_view(game, champ, opp, 0) for i, opp in enumerate(opponents)}


def _with_texts(game: Game, events: list[dict]) -> list[dict]:
    """Add game-described texts for designs that the frontend shows (hall of fame)."""
    out = []
    for e in events:
        if e["type"] == "generation" and "hof" in e:
            e = {**e, "hof_text": [game.describe(game.from_json(h)) for h in e["hof"]]}
        out.append(e)
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
        "game": game.name,
        "events": _with_texts(game, compact_events(events)),
        "battles": featured_battles(game, events) if battles else {},
    }


def _era_diff(a: dict, b: dict, prefix: str = "") -> list[dict]:
    out = []
    for k in sorted(set(a) | set(b)):
        x, y = a.get(k), b.get(k)
        if isinstance(x, dict) and isinstance(y, dict):
            out += _era_diff(x, y, f"{prefix}{k}.")
        elif x != y:
            out.append({"field": f"{prefix}{k}", "before": x, "after": y})
    return out


def tcs_view(
    runs: dict[str, tuple[str, dict, list[dict]]], reports: dict[str, dict] | None = None
) -> dict[str, Any]:
    """The TCS tab: both eras' runs and reports, the rule diff, and story battles.

    `runs` maps era ("1981"/"1982") to (run id, meta, events)."""
    from neurisko.games.registry import game_from_meta
    from neurisko.games.tcs_lite import NOTICE

    games = {era: game_from_meta(meta) for era, (_, meta, _) in runs.items()}
    eras: dict[str, Any] = {}
    champs = {}
    for era, (run_id, _meta, events) in runs.items():
        g = games[era]
        gens = [e for e in events if e["type"] == "generation"]
        made = {e["heuristic"]["id"]: e for e in events if e["type"] == "heuristic_created"}
        worth = gens[-1]["worth"]
        top = sorted((h for h in worth if h.startswith("H")), key=lambda h: -worth[h])[:5]
        champ = g.from_json(gens[-1]["best"])
        champs[era] = champ
        rep = (reports or {}).get(era)
        eras[era] = {
            "run_id": run_id,
            "series": [[e["gen"], e["best_gauntlet"], e.get("best_held_out_pool")] for e in gens],
            "champion": g.to_json(champ),
            "champion_text": g.describe(champ),
            "champion_parts": sorted(g.parts(champ)),
            "heuristics": [
                {
                    "id": h,
                    "worth": worth[h],
                    "by": made[h]["heuristic"]["origin"]["by"],
                    "text": made[h]["text"],
                }
                for h in top
                if h in made
            ],
            "report": None
            if rep is None
            else {
                "parts": rep["parts"],
                "summary": rep["summary"]["template"],
                "seeds": len(rep["seeds"]),
                "patches": [
                    {
                        "change": " + ".join(
                            p.get("label") or p["field"]
                            for p in [*d_p.get("base_patches", []), d_p["patch"]]
                        ),
                        "effective": d_p["effective"],
                        "failed": d_p["failed"],
                    }
                    for d in rep["dominant"]
                    for d_p in d["patches"]
                ],
            },
        }
    out: dict[str, Any] = {"notice": NOTICE, "eras": eras, "battles": []}
    if {"1981", "1982"} <= set(games):
        g81, g82 = games["1981"], games["1982"]
        out["rule_diff"] = _era_diff(
            json.loads(g81.ruleset_json())["era"], json.loads(g82.ruleset_json())["era"]
        )
        c81, c82 = champs["1981"], champs["1982"]
        out["crossover"] = {
            "champion_1981_under_1981": round(g81.held_out().score(c81).score, 3),
            "champion_1981_under_1982": round(g82.held_out().score(c81).score, 3),
            "champion_1982_under_1982": round(g82.held_out().score(c82).score, 3),
        }
        elite = next(o.design for o in g81.gauntlet if o.name == "elite")
        outcome = {"A": "{a} wins", "B": "{b} wins", "draw": "draw"}
        for era, g, a, b, na, nb in (
            ("1981", g81, c81, elite, "the 1981 swarm", "the elite fleet"),
            ("1982", g82, c81, elite, "the 1981 swarm", "the elite fleet"),
            ("1982", g82, c81, c82, "the 1981 swarm", "the 1982 scuttling fleet"),
        ):
            bv = battle_view(g, a, b, 0)
            result = outcome[bv["winner"]].format(a=na, b=nb)
            rounds = f"{bv['ticks']} round" + ("" if bv["ticks"] == 1 else "s")
            title = f"{era} rules: {na} vs {nb}: {result} in {rounds}"
            out["battles"].append({"title": title, "era": era, **bv})
    return out


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
