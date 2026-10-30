"""The auditor: checks that worth reflects real contribution.

1. Replication: a high-worth heuristic's recent gains must also appear on a held-out pool.
2. Duplicates: heuristics that behave identically on fixed probe designs are merged, and the
   lineage credit the copy earned for its creator is revoked.
3. Parasites: a meta-heuristic whose positive lineage credit came mostly from duplicate or
   non-replicating children is demoted. This is the Eurisko H59 pattern.

Every decision is recorded as an `audit` event with its numbers.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from neurisko.engine.credit import CreditConfig, revoke_lineage
from neurisko.engine.game import Game
from neurisko.engine.heuristics import Heuristic
from neurisko.engine.scoring import pool_score
from neurisko.runs import Recorder


@dataclass(frozen=True, slots=True)
class AuditConfig:
    replication_min_worth: float = 600
    replication_min_apps: int = 5
    replication_pairs: int = 5
    demote_non_replicating_to: float = 400
    parasite_ratio: float = 0.5
    parasite_min_contributions: int = 3
    demote_parasite_to: float = 300
    probes: int = 32


class Auditor:
    def __init__(
        self,
        game: Game,
        cfg: AuditConfig,
        credit: CreditConfig,
        recorder: Recorder,
        seed: int = 0,
    ) -> None:
        self.game = game
        self.cfg = cfg
        self.credit = credit
        self.recorder = recorder
        self.held = game.held_out()
        rng = random.Random(f"probes-{seed}")
        probes: list[Any] = []
        for _ in range(cfg.probes * 50):
            d = game.random_design(rng)
            if d not in probes:
                probes.append(d)
            if len(probes) == cfg.probes:
                break
        self.probes = probes
        self.probe_features = [game.features(p, game.score(p)) for p in probes]
        self._rng = random.Random(0)
        self.tainted: set[str] = set()

    def signature(self, h: Heuristic) -> tuple | None:
        """What `h` does to each probe design; None if it applies to none of them."""
        out = tuple(
            self.game.apply_action(p, h.action, self._rng) if h.matches(f) else None
            for p, f in zip(self.probes, self.probe_features, strict=True)
        )
        return None if all(o is None for o in out) else out

    def _emit(self, gen: int, check: str, target: str, decision: str, **numbers) -> dict:
        return self.recorder.emit(
            "audit", gen, check=check, target=target, decision=decision, **numbers
        )

    def audit(
        self,
        gen: int,
        heuristics: dict[str, Heuristic],
        metas: dict[str, Heuristic],
        hof: list[Any],
        hof_weight: float = 0.5,
    ) -> list[dict]:
        decisions: list[dict] = []
        alive = [h for h in heuristics.values() if h.alive and h.level == "design"]
        decisions += self._replication(gen, alive, hof, hof_weight)
        decisions += self._duplicates(gen, alive, metas)
        decisions += self._parasites(gen, metas)
        return decisions

    def _replication(
        self, gen: int, alive: list[Heuristic], hof: list[Any], hof_weight: float
    ) -> list[dict]:
        c = self.cfg
        out = []
        for h in alive:
            if h.worth <= c.replication_min_worth or h.stats.applications < c.replication_min_apps:
                continue
            pairs = h.stats.recent[-c.replication_pairs :]
            if not pairs:
                continue
            claimed = sum(d for _, _, d in pairs) / len(pairs)
            held = [
                pool_score(self.held, child, hof, hof_weight)
                - pool_score(self.held, parent, hof, hof_weight)
                for parent, child, _ in pairs
            ]
            mean_held = sum(held) / len(held)
            numbers = {
                "worth": round(h.worth, 1),
                "pairs": len(pairs),
                "claimed_delta": round(claimed, 4),
                "held_out_delta": round(mean_held, 4),
            }
            if mean_held <= 0:
                h.worth = min(h.worth, c.demote_non_replicating_to)
                if "non-replicating" not in h.flags:
                    h.flags.append("non-replicating")
                self.tainted.add(h.id)
                out.append(
                    self._emit(gen, "replication", h.id, "demoted", worth_after=h.worth, **numbers)
                )
            else:
                out.append(self._emit(gen, "replication", h.id, "passed", **numbers))
        return out

    def _duplicates(
        self, gen: int, alive: list[Heuristic], metas: dict[str, Heuristic]
    ) -> list[dict]:
        out = []
        first: dict[tuple, Heuristic] = {}
        for h in alive:  # creation order: the older heuristic is kept
            sig = self.signature(h)
            if sig is None:
                continue
            original = first.get(sig)
            if original is None:
                first[sig] = h
                continue
            s, o = h.stats, original.stats
            o.applications += s.applications
            o.improvements += s.improvements
            o.direct_credit += s.direct_credit
            h.alive = False
            h.flags.append(f"duplicate-of:{original.id}")
            self.tainted.add(h.id)
            revoked = 0.0
            meta = metas.get(h.origin.by)
            if meta is not None:
                revoked = revoke_lineage(meta, h.id, self.credit)
            out.append(
                self._emit(
                    gen,
                    "duplicate",
                    h.id,
                    "merged",
                    original=original.id,
                    creator=h.origin.by,
                    revoked_lineage=round(revoked, 4),
                    creator_worth_after=round(meta.worth, 1) if meta else None,
                )
            )
        return out

    def _parasites(self, gen: int, metas: dict[str, Heuristic]) -> list[dict]:
        c = self.cfg
        out = []
        for m in metas.values():
            positive = [x for x in m.stats.contributions if x.reward > 0]
            if len(positive) < c.parasite_min_contributions:
                continue
            total = sum(x.reward for x in positive)
            tainted = sum(x.reward for x in positive if x.child in self.tainted)
            ratio = tainted / total
            numbers = {
                "worth": round(m.worth, 1),
                "positive_contributions": len(positive),
                "tainted_ratio": round(ratio, 3),
            }
            if ratio > c.parasite_ratio:
                m.worth = min(m.worth, c.demote_parasite_to)
                if "parasite" not in m.flags:
                    m.flags.append("parasite")
                out.append(
                    self._emit(gen, "parasite", m.id, "demoted", worth_after=m.worth, **numbers)
                )
            else:
                out.append(self._emit(gen, "parasite", m.id, "clean", **numbers))
        return out
