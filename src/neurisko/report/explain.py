"""Why a dominant part works: dependence, evidence heuristics and matchup gains."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from neurisko.engine.game import Game
from neurisko.engine.scoring import pool_score
from neurisko.report.detect import RunOutcome
from neurisko.report.schema import Dependence, Evidence, MatchupGain

EXAM_WEIGHT = 0.5


def exam_pool(outcomes: Sequence[RunOutcome]) -> list[tuple]:
    """All distinct champions of a batch; with the held-out gauntlet this is the 'exam'."""
    return list(dict.fromkeys(tuple(o.champion) for o in outcomes))


def dependence(game: Game, part: str, outcomes: Sequence[RunOutcome]) -> Dependence:
    """Score lost when one copy of `part` is replaced by the best valid alternative."""
    held = game.held_out()
    pool = exam_pool(outcomes)
    rows = []
    for o in outcomes:
        champ = tuple(o.champion)
        if part not in game.parts(champ):
            continue
        base = pool_score(held, champ, pool, EXAM_WEIGHT)
        i = champ.index(part)
        best_alt, best_score = None, None
        for alt in game.part_names():
            if alt == part:
                continue
            d = champ[:i] + (alt,) + champ[i + 1 :]
            if game.validate(d):
                continue
            s = pool_score(held, d, pool, EXAM_WEIGHT)
            if best_score is None or s > best_score:
                best_alt, best_score = alt, s
        if best_alt is None:  # no valid swap; try removing it
            d = champ[:i] + champ[i + 1 :]
            if d and not game.validate(d):
                best_alt, best_score = "(removed)", pool_score(held, d, pool, EXAM_WEIGHT)
        if best_alt is not None:
            rows.append(
                {
                    "seed": o.seed,
                    "champion": list(champ),
                    "score": round(base, 4),
                    "best_alternative": best_alt,
                    "alt_score": round(best_score, 4),
                    "drop": round(base - best_score, 4),
                }
            )
    mean = round(sum(r["drop"] for r in rows) / len(rows), 4) if rows else None
    return Dependence(mean=mean, per_champion=rows)


def _adds(action: dict, part: str) -> bool:
    kind = action.get("kind")
    return (kind == "add_unit" and action.get("unit") == part) or (
        kind == "replace_unit" and action.get("new") == part
    )


def evidence(part: str, outcomes: Sequence[RunOutcome], limit: int = 5) -> list[Evidence]:
    """Highest-worth heuristics across runs whose action adds the part."""
    merged: dict[str, dict] = {}
    for o in outcomes:
        seen_in_run: set[str] = set()
        for h in o.heuristics:
            if not _adds(h["action"], part) or not h["applications"]:
                continue
            m = merged.setdefault(
                h["text"],
                {"text": h["text"], "worth": 0.0, "applications": 0, "improvements": 0, "runs": 0},
            )
            m["worth"] = max(m["worth"], h["worth"])
            m["applications"] += h["applications"]
            m["improvements"] += h["improvements"]
            if h["text"] not in seen_in_run:
                m["runs"] += 1
                seen_in_run.add(h["text"])
    rows = sorted(merged.values(), key=lambda m: (m["worth"], m["runs"]), reverse=True)
    return [Evidence(**m) for m in rows[:limit]]


def matchup_gains(
    game: Game, part: str, outcomes: Sequence[RunOutcome], limit: int = 3
) -> tuple[list[MatchupGain] | None, str]:
    held = game.held_out()
    champs = exam_pool(outcomes)
    with_p = [c for c in champs if part in game.parts(c)]
    without = [c for c in champs if part not in game.parts(c)]
    if len(with_p) < 2 or len(without) < 2:
        return None, (
            f"skipped: {len(with_p)} distinct champions with {part}, {len(without)} without "
            "(need 2 of each)"
        )
    scores: dict[str, dict[str, list[float]]] = defaultdict(lambda: {"w": [], "wo": []})
    for group, key in ((with_p, "w"), (without, "wo")):
        for c in group:
            for m in held.score(c).matchups:
                scores[m.opponent][key].append(m.score)
    rows = []
    for opp, s in scores.items():
        w, wo = sum(s["w"]) / len(s["w"]), sum(s["wo"]) / len(s["wo"])
        rows.append(
            MatchupGain(
                opponent=opp,
                with_part=round(w, 3),
                without_part=round(wo, 3),
                gain=round(w - wo, 3),
            )
        )
    rows.sort(key=lambda r: r.gain, reverse=True)
    return rows[:limit], ""
