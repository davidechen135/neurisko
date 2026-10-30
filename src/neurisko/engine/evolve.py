"""The generation loop.

Each generation: rescore the population against the current pool (gauntlet + hall of fame),
apply design heuristics chosen by the agenda, run meta-heuristics, update the population and
hall of fame, audit when due, retire weak heuristics, and record a summary.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

from neurisko.engine.agenda import design_tasks, meta_tasks
from neurisko.engine.auditor import AuditConfig, Auditor
from neurisko.engine.credit import CreditConfig, credit_application
from neurisko.engine.game import Game, ScoreReport
from neurisko.engine.heuristics import Heuristic, Origin, RuleSpec, validate_rule
from neurisko.engine.meta import RUNNERS, MetaContext, Proposal, make_metas
from neurisko.engine.scoring import pool_score
from neurisko.llm import LLMClient
from neurisko.runs import Recorder


@dataclass(frozen=True)
class EvolveConfig:
    generations: int = 20
    max_generations: int = 50
    seed: int = 0
    population: int = 20
    immigrants: int = 4  # random designs that replace the weakest each generation
    design_apps: int = 40
    meta_apps: int = 3
    hof_cap: int = 12
    hof_weight: float = 0.5  # share of the pool score that comes from the hall of fame
    audit_every: int = 3
    auditor: bool = True
    retire_below: float = 100
    dormant_limit: int = 5
    min_design_heuristics: int = 8
    max_design_heuristics: int = 60
    per_heuristic_cap: int = 6
    ucb_c: float = 0.3
    invent_k: int = 3
    max_llm_calls_per_generation: int = 2
    recent_keep: int = 8
    credit: CreditConfig = field(default_factory=CreditConfig)
    audit: AuditConfig = field(default_factory=AuditConfig)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RunResult:
    reason: str  # "completed" | "budget" | "interrupted"
    generations: int
    best: Any
    best_score: float
    summaries: list[dict]


class Evolution:
    def __init__(
        self,
        game: Game,
        cfg: EvolveConfig,
        seed_rules: list[RuleSpec],
        llm: LLMClient | None = None,
        recorder: Recorder | None = None,
        on_generation: Callable[[int, dict, Evolution], None] | None = None,
    ) -> None:
        self.game = game
        self.cfg = cfg
        self.llm = llm
        self.on_generation = on_generation
        self.rec = recorder or Recorder()
        self.rng = random.Random(cfg.seed)
        self.metas = make_metas()
        self.heuristics: dict[str, Heuristic] = {}
        self._next_id = 1
        self.population: list[Any] = []
        self.explored: set[tuple[Any, Any]] = set()  # every (parent, child) ever credited
        self.hof: list[Any] = []
        self.total_apps = 0
        self.total_meta_runs = 0
        self.flags: list[str] = []
        self.held = game.held_out()
        self.auditor = (
            Auditor(game, cfg.audit, cfg.credit, self.rec, cfg.seed) if cfg.auditor else None
        )
        self._seed_rules = seed_rules

    # --- helpers ---------------------------------------------------------------------------

    def score(self, design: Any) -> ScoreReport:
        """Full report against gauntlet + hall of fame (used for features and evidence)."""
        return self.game.score(design, self.hof)

    def value(self, design: Any) -> float:
        """The number the engine optimises: hall-of-fame-weighted pool score."""
        return pool_score(self.game, design, self.hof, self.cfg.hof_weight)

    def features_of(self, design: Any) -> dict[str, float]:
        return self.game.features(design, self.score(design))

    def design_heuristics(self, alive_only: bool = True) -> list[Heuristic]:
        return [h for h in self.heuristics.values() if h.alive or not alive_only]

    def add_heuristic(self, p: Proposal, by: str, gen: int) -> Heuristic | None:
        errors = validate_rule(
            p.conditions, p.action, self.game.feature_names(), self.game.action_schema()
        )
        if errors:
            self.rec.emit("heuristic_rejected", gen, by=by, item=p.name, errors=errors)
            return None
        h = Heuristic(
            id=f"H{self._next_id}",
            level="design",
            name=p.name,
            rationale=p.rationale,
            conditions=list(p.conditions),
            action=dict(p.action),
            origin=Origin(by=by, parent=p.parent, generation=gen),
        )
        self._next_id += 1
        self.heuristics[h.id] = h
        self.rec.emit("heuristic_created", gen, heuristic=h.summary(), text=h.text())
        return h

    def _evidence(self) -> dict:
        designs = []
        for d in self.population[:3]:
            r = self.score(d)
            worst = sorted(r.matchups, key=lambda m: m.score)[:2]
            designs.append(
                {
                    "text": self.game.describe(d),
                    "score": r.score,
                    "worst": [(m.opponent, m.score) for m in worst],
                }
            )
        used = sorted(
            (h for h in self.design_heuristics() if h.stats.applications),
            key=lambda h: h.worth,
            reverse=True,
        )

        def line(h: Heuristic) -> dict:
            s = h.stats
            return {
                "line": f"{h.id} {h.worth:.0f} (apps {s.applications}, impr {s.improvements}) "
                f"{h.text()}"
            }

        return {
            "designs": designs,
            "best": [line(h) for h in used[:5]],
            "worst": [line(h) for h in used[-3:]] if len(used) > 5 else [],
            "flags": self.flags[-5:],
        }

    # --- run -------------------------------------------------------------------------------

    def run(self) -> RunResult:
        cfg = self.cfg
        n_gens = min(cfg.generations, cfg.max_generations)
        self.rec.emit(
            "run_start",
            0,
            game=self.game.name,
            ruleset_hash=self.game.ruleset_hash,
            config=cfg.to_dict(),
            llm=self.llm.model if self.llm else None,
        )
        for m in self.metas.values():
            self.rec.emit("heuristic_created", 0, heuristic=m.summary(), text=m.text())
        for spec in self._seed_rules:
            self.add_heuristic(
                Proposal(spec.name, spec.rationale, spec.conditions, spec.action), "seed", 0
            )
        seen: set[Any] = set()
        for _ in range(cfg.population * 50):
            d = self.game.random_design(self.rng)
            if d not in seen:
                seen.add(d)
                self.population.append(d)
            if len(self.population) == cfg.population:
                break
        self.population.sort(key=lambda d: self.value(d), reverse=True)

        summaries: list[dict] = []
        reason = "completed" if cfg.generations <= cfg.max_generations else "budget"
        done = 0
        try:
            for gen in range(1, n_gens + 1):
                summaries.append(self.step(gen))
                done = gen
                if self.on_generation is not None:
                    self.on_generation(gen, summaries[-1], self)
        except KeyboardInterrupt:
            reason = "interrupted"
        best = self.population[0]
        best_score = self.value(best)
        self.rec.emit(
            "run_end",
            done,
            reason=reason,
            generations=done,
            best=self.game.to_json(best),
            best_score=best_score,
        )
        return RunResult(reason, done, best, best_score, summaries)

    def step(self, gen: int) -> dict:
        cfg = self.cfg
        t0 = time.perf_counter()

        # 1. Rescore the population against the current pool.
        self.population.sort(key=lambda d: self.value(d), reverse=True)
        pop_feats = [(d, self.features_of(d)) for d in self.population]

        # 2. Design heuristics chosen by the agenda.
        alive = self.design_heuristics()
        tasks, active = design_tasks(
            alive,
            pop_feats,
            self.game,
            self.rng,
            cfg.design_apps,
            cfg.per_heuristic_cap,
            cfg.ucb_c,
            self.total_apps,
            explored=self.explored,
        )
        for h in alive:
            h.stats.dormant_generations = 0 if h.id in active else h.stats.dormant_generations + 1
        children: list[Any] = []
        improvements = 0
        for t in tasks:
            h = t.heuristic
            parent_score = self.value(t.parent)
            child_score = self.value(t.child)
            delta = child_score - parent_score
            info = credit_application(h, delta, self.metas, cfg.credit)
            h.stats.recent = [*h.stats.recent, (t.parent, t.child, delta)][-cfg.recent_keep :]
            self.total_apps += 1
            improvements += delta > 0
            children.append(t.child)
            self.explored.add((t.parent, t.child))
            self.rec.emit(
                "applied",
                gen,
                heuristic=h.id,
                parent=self.game.to_json(t.parent),
                child=self.game.to_json(t.child),
                parent_score=parent_score,
                child_score=child_score,
                delta=delta,
                **info,
            )

        # 3. Meta-heuristics.
        llm_budget = [cfg.max_llm_calls_per_generation if self.llm else 0]
        available = [m for m in self.metas.values() if m.id != "M1" or llm_budget[0] > 0]
        ctx = MetaContext(
            game=self.game,
            rng=self.rng,
            generation=gen,
            heuristics=self.design_heuristics(),
            features_of=self.features_of,
            recorder=self.rec,
            llm=self.llm,
            llm_budget=llm_budget,
            evidence=self._evidence,
            invent_k=cfg.invent_k,
        )
        created = 0
        for m in meta_tasks(available, self.rng, cfg.meta_apps, cfg.ucb_c, self.total_meta_runs):
            proposals = RUNNERS[m.id](ctx)
            m.stats.applications += 1
            self.total_meta_runs += 1
            new = [self.add_heuristic(p, m.id, gen) for p in proposals]
            created += sum(h is not None for h in new)
            self.rec.emit(
                "meta_applied",
                gen,
                heuristic=m.id,
                created=[h.id for h in new if h is not None],
            )

        # 4. Population and hall of fame.
        pool = list(dict.fromkeys([*self.population, *children]))
        pool.sort(key=lambda d: self.value(d), reverse=True)
        keep = cfg.population - cfg.immigrants
        self.population = pool[:keep]
        # Fresh random designs keep the agenda supplied with untried parents; without them
        # the population converges and every reachable move has been tried by generation ~8.
        immigrants: list[Any] = []
        for _ in range(cfg.immigrants * 50):
            if len(immigrants) == cfg.immigrants:
                break
            d = self.game.random_design(self.rng)
            if d not in self.population and d not in immigrants:
                immigrants.append(d)
        self.population += immigrants
        self.population.sort(key=lambda d: self.value(d), reverse=True)
        # The strongest design not yet in the hall of fame joins it, so the pool keeps getting
        # harder even when the best design does not change.
        newcomer = next((d for d in self.population if d not in self.hof), None)
        if newcomer is not None:
            self.hof.append(newcomer)
            self.rec.emit("hof_added", gen, design=self.game.to_json(newcomer))
            if len(self.hof) > cfg.hof_cap:
                weakest = min(self.hof, key=lambda d: self.value(d))
                self.hof.remove(weakest)
                self.rec.emit("hof_removed", gen, design=self.game.to_json(weakest))
            # The pool changed, so the ranking may have too.
            self.population.sort(key=lambda d: self.value(d), reverse=True)

        # 5. Audit.
        audits: list[dict] = []
        if self.auditor and gen % cfg.audit_every == 0:
            audits = self.auditor.audit(gen, self.heuristics, self.metas, self.hof, cfg.hof_weight)
            for a in audits:
                if a["decision"] in ("demoted", "merged"):
                    self.flags.append(f"{a['target']} {a['check']} {a['decision']}")

        # 6. Retire.
        self._retire(gen)

        # 7. Summary. Scores against the fixed gauntlet and the held-out pool are comparable
        #    across generations; the pool score is not, because the hall of fame grows.
        best = self.population[0]
        summary = {
            "best": self.game.to_json(best),
            "best_text": self.game.describe(best),
            "best_pool": self.value(best),
            "best_gauntlet": self.game.score(best).score,
            "best_held_out": self.held.score(best).score,
            "best_held_out_pool": pool_score(self.held, best, self.hof, cfg.hof_weight),
            "population": [[self.game.to_json(d), self.value(d)] for d in self.population],
            "hof": [self.game.to_json(d) for d in self.hof],
            "applications": len(tasks),
            "improvements": improvements,
            "created": created,
            "audit_actions": sum(a["decision"] in ("demoted", "merged") for a in audits),
            "worth": {
                h.id: round(h.worth, 1) for h in [*self.metas.values(), *self.design_heuristics()]
            },
        }
        self.rec.emit("generation", gen, **summary, elapsed_s=round(time.perf_counter() - t0, 3))
        return summary

    def _retire(self, gen: int) -> None:
        cfg = self.cfg
        alive = self.design_heuristics()
        reasons: dict[str, str] = {}
        for h in sorted(alive, key=lambda h: h.worth):
            if h.worth < cfg.retire_below:
                reasons[h.id] = "low worth"
            elif h.stats.dormant_generations >= cfg.dormant_limit:
                reasons[h.id] = "dormant"
        excess = len(alive) - cfg.max_design_heuristics
        for h in sorted(alive, key=lambda h: h.worth):
            if excess <= 0:
                break
            if h.id not in reasons:
                reasons[h.id] = "over capacity"
                excess -= 1
        keep = len(alive)
        for h in sorted(alive, key=lambda h: h.worth):
            if h.id in reasons and keep > cfg.min_design_heuristics:
                h.alive = False
                keep -= 1
                self.rec.emit(
                    "retired", gen, heuristic=h.id, reason=reasons[h.id], worth=round(h.worth, 1)
                )
