// The RUN tab: score chart, heuristic worth table, audit teletype, champion.
import { bar, fill, el, f2, f3, gen, pad } from "../dom.js";
import { chartWithTable } from "./chart.js";

const ORIGIN = { seed: "seed", M1: "M1 LLM", M2: "M2 spec", M3: "M3 gen", M4: "M4 retg", M5: "M5 clone" };

const FLAG_HELP = {
  parasite:
    "Auditor: most of this meta-heuristic's credit came from copies or from gains that did not replicate. Eurisko's H59 pattern.",
  duplicate: "Auditor: behaves exactly like an older heuristic on every probe design; merged into it.",
  "non-replicating": "Auditor: its claimed gains vanished on a held-out opponent pool.",
  retired: "Removed for low worth, or because it no longer applied to any design.",
  cleared: "Was flagged as a parasite earlier; later audits found most of its credit genuine again.",
};

function flagBadges(flags) {
  return (flags || []).map((f) =>
    el("span", { class: `flag flag-${f.kind}`, tabindex: "0", title: FLAG_HELP[f.kind] }, f.text),
  );
}

export function scorePanel(v) {
  const series = [
    {
      label: "held-out + hall of fame",
      mark: "●",
      cls: "fg",
      values: v.history.map((s) => s.best_held_out_pool ?? null),
    },
    { label: "fixed gauntlet", mark: "·", cls: "dim", values: v.history.map((s) => s.best_gauntlet) },
  ];
  const s = v.summary;
  return el(
    "section",
    { class: "panel", "aria-labelledby": "h-score" },
    el("h2", { id: "h-score" }, "SCORE OF THE CHAMPION"),
    chartWithTable("Champion score by generation", series, { lo: 0.5, hi: 1.0, height: 9 }),
    s
      ? el(
          "p",
          { class: "dim small" },
          `${gen(v.gen)}: ${s.improvements}/${s.applications} applications improved a design, `,
          `${s.created} heuristics created, hall of fame ${s.hof.length}.`,
        )
      : null,
  );
}

function worthRow(h, worth, flags, isMeta) {
  const w = worth[h.id];
  const row = el(
    "tr",
    { class: flags?.some((f) => f.kind === "parasite") ? "row-parasite" : "" },
    el("td", { class: "id" }, h.id),
    el("td", { class: "worth" }, el("span", { class: "bar", "aria-hidden": "true" }, bar((w ?? 0) / 1000, 10)), ` ${w === undefined ? "–" : Math.round(w)}`),
    el("td", { class: "origin dim" }, isMeta ? "meta" : ORIGIN[h.by] || h.by),
    el("td", { class: "rule" }, isMeta ? h.name : el("span", { title: h.name }, h.text)),
    el("td", { class: "flags" }, flagBadges(flags)),
  );
  return row;
}

export function worthPanel(v, limit = 8) {
  const head = el(
    "tr",
    {},
    ["id", "worth", "origin", "rule", "audit"].map((t) => el("th", { scope: "col" }, t)),
  );
  return el(
    "section",
    { class: "panel", "aria-labelledby": "h-worth" },
    el("h2", { id: "h-worth" }, "HEURISTIC UNITS ", el("span", { class: "dim" }, "(worth 0–1000)")),
    el(
      "table",
      { class: "worth-table" },
      el("thead", {}, head),
      el(
        "tbody",
        {},
        v.metas.map((h) => worthRow(h, v.worth, v.flags.get(h.id), true)),
        el("tr", { class: "sep", "aria-hidden": "true" }, el("td", { colspan: "5" }, "")),
        v.designs.slice(0, limit).map((h) => worthRow(h, v.worth, v.flags.get(h.id), false)),
      ),
    ),
    el(
      "p",
      { class: "dim small" },
      `${v.alive} of ${v.created} design heuristics alive · ${v.invented.length} invented by the LLM`,
    ),
  );
}

function auditLine(a) {
  if (a.check === "duplicate")
    return `${pad(a.target, 5)} ≡ ${pad(a.original, 5)} merged · ${a.creator} −${f2(a.revoked_lineage)} → ${Math.round(a.creator_worth_after ?? 0)}`;
  if (a.check === "parasite")
    return `${pad(a.target, 5)} tainted ${f2(a.tainted_ratio)} → worth ${Math.round(a.worth_after ?? a.worth)}`;
  if (a.check === "replication")
    return `${pad(a.target, 5)} claimed ${f3(a.claimed_delta)}, held-out ${f3(a.held_out_delta)}${a.decision === "demoted" ? ` → worth ${Math.round(a.worth_after)}` : ""}`;
  return `${a.target} ${a.decision}`;
}

export function auditPanel(v, showAll) {
  const list = v.audits.filter((a) => showAll || a.decision === "demoted" || a.decision === "merged");
  const log = el(
    "ol",
    { class: "teletype", "aria-live": "polite", "aria-relevant": "additions" },
    list.slice(-60).map((a) =>
      el(
        "li",
        { class: `audit audit-${a.decision}` },
        el("span", { class: "dim" }, `${gen(a.gen)} `),
        el("span", { class: `check check-${a.check}` }, pad(a.check.toUpperCase(), 12)),
        auditLine(a),
      ),
    ),
  );
  return el(
    "section",
    { class: "panel", "aria-labelledby": "h-audit" },
    el("h2", { id: "h-audit" }, "AUDITOR"),
    v.audits.length || v.gen < 3
      ? log
      : el("p", { class: "dim" }, "Auditor is off for this run."),
    el("p", { class: "dim small" }, `${list.length} of ${v.audits.length} audit decisions shown`),
  );
}

export function championPanel(v, battles, onPlay) {
  const s = v.summary;
  if (!s) return el("section", { class: "panel" }, el("h2", {}, "CHAMPION"), el("p", {}, "waiting…"));
  const champ = s.best;
  const playable = Object.values(battles || {}).filter((b) => b.a.join() === champ.join());
  return el(
    "section",
    { class: "panel", "aria-labelledby": "h-champ" },
    el("h2", { id: "h-champ" }, "CHAMPION"),
    el("p", { class: "champion" }, champ.map((u, i) => [i ? el("span", { class: "dim" }, " > ") : "", el("span", { class: "unit" }, u)])),
    el("p", { class: "small" }, `held-out + hall of fame ${f3(s.best_held_out_pool)} · fixed gauntlet ${f3(s.best_gauntlet)}`),
    playable.length
      ? el(
          "div",
          { class: "battles" },
          el("p", { class: "dim small" }, "Replay a battle against:"),
          playable.map((b) =>
            el("button", { type: "button", onclick: () => onPlay(b) }, `▶ ${b.b.join(" > ")}`),
          ),
        )
      : el("p", { class: "dim small" }, v.final ? "" : "Battles are available at the final generation."),
    el(
      "details",
      {},
      el("summary", {}, `Hall of fame (${s.hof.length})`),
      el("ol", { class: "small" }, s.hof.map((d) => el("li", {}, d.join(" > ")))),
    ),
  );
}

export function renderRun(root, v, ctx) {
  fill(root, 
    el(
      "div",
      { class: "grid" },
      scorePanel(v),
      worthPanel(v),
      auditPanel(v, ctx.showAllAudits),
      championPanel(v, ctx.battles, ctx.playBattle),
    ),
    el(
      "aside",
      { class: "legend-box small", "aria-label": "Audit flags" },
      Object.entries(FLAG_HELP).map(([k, text]) =>
        el("p", {}, el("span", { class: `flag flag-${k}` }, k.toUpperCase()), " ", text),
      ),
    ),
  );
}
