"""Report summaries: a template built from the numbers, and an optional LLM summary.

The LLM summary is only kept if every number in it appears in the facts it was given.
"""

from __future__ import annotations

import json
import re
from typing import Any

from neurisko.llm import LLMClient, LLMError
from neurisko.report.schema import DominantEntry, PartStat

NUMBER = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(%?)(?![\w])")
SMALL_INTS = set(range(0, 11))
MAX_WORDS = 120


def pct(x: float) -> str:
    return f"{round(x * 100)}%"


def facts(
    parts: list[PartStat],
    dominant: list[DominantEntry],
    underused: list[str],
    runs: int,
    generations: int,
) -> dict[str, Any]:
    """The measured facts, rounded the way the template shows them."""
    dom = []
    for d in dominant:
        p = next(r for r in parts if r.part == d.part)
        entry: dict[str, Any] = {
            "part": d.part,
            "share_in_top_designs": round(p.evolved, 2),
            "share_range": [round(p.lo, 2), round(p.hi, 2)],
            "share_in_random_designs": round(p.baseline, 2),
            "lift": round(p.lift, 1),
            "champions_containing_it": f"{p.champion_runs}/{p.runs}",
            "score_lost_without_it": None
            if d.dependence.mean is None
            else round(d.dependence.mean, 2),
            "patches": [],
        }
        for r in d.patches:
            if r.effective:
                result = (
                    f"effective: nothing is dominant afterwards; most common is "
                    f"{r.top_after} at {pct(r.top_after_share)}"
                )
            else:
                result = "not effective: " + "; ".join(r.failed)
            entry["patches"].append(
                {
                    "change": r.change_text(),
                    "steps": [
                        {"part": b.target, "field": b.field, "old": b.old, "new": b.new}
                        for b in [*r.base_patches, r.patch]
                    ],
                    "effective": r.effective,
                    "result": result,
                }
            )
        dom.append(entry)
    recommended = next((p for d in dom for p in d["patches"] if p["effective"]), None)
    return {
        "recommended_change": recommended["change"] if recommended else None,
        "recommended_steps": recommended["steps"] if recommended else [],
        "runs": runs,
        "generations_per_run": generations,
        "dominant": dom,
        "underused": underused,
        "top_parts": [
            {"part": p.part, "share": round(p.evolved, 2), "random": round(p.baseline, 2)}
            for p in parts[:5]
        ],
    }


def template_summary(f: dict[str, Any]) -> str:
    lines = []
    if not f["dominant"]:
        lines.append(
            f"No part is dominant over {f['runs']} runs. Most common in strong designs: "
            + ", ".join(
                f"{p['part']} {pct(p['share'])} (random {pct(p['random'])})"
                for p in f["top_parts"][:3]
            )
            + "."
        )
    for d in f["dominant"]:
        lo, hi = d["share_range"]
        s = (
            f"{d['part']} is dominant: in {pct(d['share_in_top_designs'])} of top designs "
            f"(range {pct(lo)}-{pct(hi)} over {f['runs']} runs) against "
            f"{pct(d['share_in_random_designs'])} of random designs, and in "
            f"{d['champions_containing_it']} champions."
        )
        if d["score_lost_without_it"] is not None:
            s += f" Champions lose {d['score_lost_without_it']:.2f} without it."
        good = [p for p in d["patches"] if p["effective"]]
        if good:
            s += f" Effective fix: {good[0]['change']} ({good[0]['result'].split(': ', 1)[1]})."
        elif d["patches"]:
            s += (
                " No tested change fixed it: "
                + "; ".join(f"{p['change']}: {p['result'].split(': ', 1)[1]}" for p in d["patches"])
                + "."
            )
        lines.append(s)
    if f["underused"]:
        lines.append(f"Rarely used by strong designs: {', '.join(f['underused'])}.")
    return "\n\n".join(lines)


def _allowed(obj: Any, out: set[float]) -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        out.add(float(obj))
        if 0 <= obj <= 1:
            out.add(round(obj * 100))
    elif isinstance(obj, str):
        for m in NUMBER.finditer(obj):
            out.add(float(m.group(1)))
    elif isinstance(obj, dict):
        for v in obj.values():
            _allowed(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _allowed(v, out)


def unsupported_numbers(text: str, f: dict[str, Any]) -> list[str]:
    """Numbers in `text` that do not appear in the facts (with rounding tolerance)."""
    allowed: set[float] = set()
    _allowed(f, allowed)
    bad = []
    for m in NUMBER.finditer(text):
        x = float(m.group(1))
        if m.group(2) != "%" and x.is_integer() and int(x) in SMALL_INTS:
            continue
        if not any(abs(x - a) <= 0.006 * max(1.0, abs(a)) for a in allowed):
            bad.append(m.group(0))
    return bad


def missing_recommendation(text: str, f: dict[str, Any]) -> list[str]:
    """Steps of the recommended change whose unit or new value the text does not mention."""
    low = text.lower().replace("_", " ")
    numbers = {float(m.group(1)) for m in NUMBER.finditer(text)}
    missing = []
    for st in f.get("recommended_steps", []):
        name_ok = st["part"].replace("_", " ") in low
        value_ok = float(st["new"]) in numbers
        if not (name_ok and value_ok):
            missing.append(f"{st['part']}.{st['field']} -> {st['new']:g}")
    return missing


SYSTEM = (
    "You summarise a game balance report for a game designer. Use only the facts in the JSON "
    "the user gives you. Do not add any number that is not in the facts. Shares may be written "
    "as percentages. If recommended_change is set, state it first, with every step (unit, "
    "field, old and new value), and use each change's `result` text for what happened. Changes "
    "marked not effective were rejected; say why in a few words. At most "
    f'{MAX_WORDS} words, plain language. Reply with JSON: {{"summary": "..."}}'
)


def llm_summary(llm: LLMClient, f: dict[str, Any]) -> tuple[str | None, dict | None]:
    """(summary, rejection). Exactly one of them is None."""
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": json.dumps(f, ensure_ascii=False)},
    ]
    try:
        resp = llm.complete(messages)
    except LLMError as err:
        return None, {"reason": "llm error", "error": str(err)}
    try:
        text = json.loads(resp.text)["summary"].strip()
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError):
        return None, {"reason": "no summary in reply", "reply": resp.text[:500]}
    bad = unsupported_numbers(text, f)
    if bad:
        return None, {"reason": "numbers not in the facts", "numbers": bad, "text": text}
    missing = missing_recommendation(text, f)
    if missing:
        return None, {"reason": "recommended change not stated", "missing": missing, "text": text}
    if len(text.split()) > MAX_WORDS * 1.5:
        return None, {"reason": "too long", "words": len(text.split()), "text": text}
    return text, None
