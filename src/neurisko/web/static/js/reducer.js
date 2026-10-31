// Pure reducer over compact run events (see neurisko/web/view.py: compact_event).
// No DOM access, so it runs under `node --test` too.

export function emptyState() {
  return {
    start: null,
    end: null,
    gens: [], // generation summaries, in order
    heuristics: new Map(), // id -> created event
    audits: [],
    llm: [],
    llmErrors: [],
    rejected: [],
    retired: [],
    hof: [],
    metaApplied: [],
    count: 0,
  };
}

const LISTS = {
  generation: "gens",
  audit: "audits",
  llm_call: "llm",
  llm_error: "llmErrors",
  llm_skipped: "llmErrors",
  heuristic_rejected: "rejected",
  retired: "retired",
  hof_added: "hof",
  hof_removed: "hof",
  meta_applied: "metaApplied",
};

export function reduce(state, e) {
  state.count += 1;
  if (e.type === "run_start") state.start = e;
  else if (e.type === "run_end") state.end = e;
  else if (e.type === "heuristic_created") state.heuristics.set(e.id, e);
  else if (LISTS[e.type]) state[LISTS[e.type]].push(e);
  return state;
}

export function reduceAll(events) {
  return events.reduce(reduce, emptyState());
}

const upTo = (list, g) => list.filter((e) => e.gen <= g);

// Flags the auditor has attached to each heuristic by generation g.
export function flagsAt(state, g) {
  const flags = new Map();
  const add = (id, flag) => {
    if (!flags.has(id)) flags.set(id, []);
    if (!flags.get(id).some((f) => f.kind === flag.kind)) flags.get(id).push(flag);
  };
  for (const a of upTo(state.audits, g)) {
    if (a.check === "duplicate" && a.decision === "merged")
      add(a.target, { kind: "duplicate", of: a.original, text: `DUPLICATE OF ${a.original}` });
    if (a.check === "replication" && a.decision === "demoted")
      add(a.target, { kind: "non-replicating", text: "NON-REPLICATING" });
  }
  // Parasite status can clear: show the latest parasite audit's verdict.
  const lastParasite = new Map();
  for (const a of upTo(state.audits, g)) if (a.check === "parasite") lastParasite.set(a.target, a);
  const firstDemoted = new Map();
  for (const a of upTo(state.audits, g))
    if (a.check === "parasite" && a.decision === "demoted" && !firstDemoted.has(a.target))
      firstDemoted.set(a.target, a.gen);
  for (const [id, first] of firstDemoted) {
    const current = lastParasite.get(id).decision === "demoted";
    const g0 = `G${String(first).padStart(2, "0")}`;
    add(id, current
      ? { kind: "parasite", text: "PARASITE" }
      : { kind: "cleared", text: `PARASITE ${g0}, CLEARED` });
  }
  for (const r of upTo(state.retired, g)) add(r.heuristic, { kind: "retired", text: "RETIRED" });
  return flags;
}

// Everything a view needs to show the run as of generation g (1-based).
export function at(state, g) {
  const n = state.gens.length;
  g = Math.max(n ? 1 : 0, Math.min(g, n));
  const summary = g ? state.gens[g - 1] : null;
  const worth = summary ? summary.worth : {};
  const flags = flagsAt(state, g);
  const created = [...state.heuristics.values()].filter((h) => h.gen <= g);
  const dead = new Set(
    [...flags].filter(([, fs]) => fs.some((f) => f.kind === "duplicate" || f.kind === "retired"))
      .map(([id]) => id),
  );
  const rank = (h) => worth[h.id] ?? -1;
  const metas = created.filter((h) => h.level === "meta");
  const designs = created
    .filter((h) => h.level === "design" && h.id in worth && !dead.has(h.id))
    .sort((a, b) => rank(b) - rank(a) || a.id.localeCompare(b.id, "en", { numeric: true }));
  return {
    gen: g,
    total: n,
    final: state.end !== null && g === n,
    summary,
    history: state.gens.slice(0, g),
    worth,
    flags,
    metas,
    designs,
    alive: designs.length,
    created: created.filter((h) => h.level === "design").length,
    audits: upTo(state.audits, g),
    llm: upTo(state.llm, g),
    llmErrors: upTo(state.llmErrors, g),
    rejected: upTo(state.rejected, g),
    invented: created.filter((h) => h.by === "M1"),
  };
}
