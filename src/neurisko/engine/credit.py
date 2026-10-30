"""Credit assignment. Worth comes only from measured score changes (safety steering).

- reward r = clip(delta / scale, -1, 1)
- direct:  worth <- worth + alpha * (500 + 500 r - worth)
- lineage: the meta-heuristic that created the heuristic gets the same update with rate
  lambda * alpha. Each lineage contribution is logged so the auditor can revoke it.
"""

from __future__ import annotations

from dataclasses import dataclass

from neurisko.engine.heuristics import WORTH_INIT, WORTH_MAX, WORTH_MIN, Contribution, Heuristic


@dataclass(frozen=True, slots=True)
class CreditConfig:
    alpha: float = 0.2
    lam: float = 0.5
    scale: float = 0.05  # a 5-point win-rate gain is full credit


def reward(delta: float, scale: float) -> float:
    return max(-1.0, min(1.0, delta / scale))


def ema(worth: float, r: float, rate: float) -> float:
    target = WORTH_INIT + (WORTH_MAX - WORTH_INIT) * r
    return max(WORTH_MIN, min(WORTH_MAX, worth + rate * (target - worth)))


def credit_application(
    h: Heuristic, delta: float, metas: dict[str, Heuristic], cfg: CreditConfig
) -> dict:
    """Apply direct and lineage credit for one application of design heuristic `h`."""
    r = reward(delta, cfg.scale)
    before = h.worth
    s = h.stats
    s.applications += 1
    s.improvements += delta > 0
    s.direct_credit += r
    h.worth = ema(h.worth, r, cfg.alpha)
    info = {"reward": r, "worth_before": before, "worth_after": h.worth}
    meta = metas.get(h.origin.by)
    if meta is not None:
        meta.stats.lineage_credit += cfg.lam * r
        meta.stats.contributions.append(Contribution(child=h.id, reward=cfg.lam * r))
        meta.worth = ema(meta.worth, r, cfg.lam * cfg.alpha)
        info["lineage"] = {"meta": meta.id, "worth_after": meta.worth}
    return info


def recompute_meta_worth(meta: Heuristic, cfg: CreditConfig) -> None:
    """Replay the meta-heuristic's non-revoked contributions from the initial worth."""
    worth = WORTH_INIT
    total = 0.0
    for c in meta.stats.contributions:
        if not c.revoked:
            worth = ema(worth, c.reward / cfg.lam, cfg.lam * cfg.alpha)
            total += c.reward
    meta.worth = worth
    meta.stats.lineage_credit = total


def revoke_lineage(meta: Heuristic, child_id: str, cfg: CreditConfig) -> float:
    """Revoke every contribution `child_id` gave to `meta`; return the revoked total."""
    revoked = 0.0
    for c in meta.stats.contributions:
        if c.child == child_id and not c.revoked:
            c.revoked = True
            revoked += c.reward
    if revoked:
        recompute_meta_worth(meta, cfg)
    return revoked
