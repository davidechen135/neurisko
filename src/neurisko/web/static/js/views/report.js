// The REPORT tab: balance report (see neurisko/report/schema.py).
import { bar, fill, el, f2, f3, pct } from "../dom.js";

const changeText = (p) => [...(p.base_patches || []), p.patch].map(patchText).join(" + ");
function patchText(p) {
  const num = (x) => (Number.isInteger(x) ? String(x) : String(+x.toFixed(3)));
  return p.label || `${p.target}.${p.field} ${num(p.old)}→${num(p.new)}`;
}

function sharesTable(parts) {
  return el(
    "table",
    { class: "shares" },
    el("caption", { class: "sr-only" }, "Share of each unit in strong designs versus random designs"),
    el(
      "thead",
      {},
      el("tr", {}, ["unit", "in top designs", "range", "random", "lift", "champions", ""].map((t) => el("th", { scope: "col" }, t))),
    ),
    el(
      "tbody",
      {},
      parts.map((p) =>
        el(
          "tr",
          { class: p.flags.includes("dominant") ? "row-dominant" : p.flags.includes("underused") ? "row-underused" : "" },
          el("th", { scope: "row" }, p.part),
          el("td", {}, el("span", { class: "bar", "aria-hidden": "true" }, bar(p.evolved, 20)), ` ${f2(p.evolved)}`),
          el("td", { class: "dim" }, `${f2(p.lo)}–${f2(p.hi)}`),
          el("td", {}, f2(p.baseline)),
          el("td", {}, p.lift.toFixed(1)),
          el("td", {}, `${p.champion_runs}/${p.runs}`),
          el("td", {}, p.flags.map((f) => el("span", { class: `flag flag-${f}` }, f.toUpperCase()))),
        ),
      ),
    ),
  );
}

function patchesTable(d, verifySeeds) {
  return el(
    "table",
    { class: "patches" },
    el("caption", {}, `Candidate fixes, each verified by re-running the engine on ${verifySeeds} seeds`),
    el(
      "thead",
      {},
      el("tr", {}, ["change", "changed unit before → after", "most common after", "verdict"].map((t) => el("th", { scope: "col" }, t))),
    ),
    el(
      "tbody",
      {},
      d.patches.map((p) =>
        el(
          "tr",
          { class: p.effective ? "row-effective" : "" },
          el("td", {}, el("code", {}, changeText(p))),
          el("td", {}, `${p.patch.target} ${f2(p.target_before)} → ${f2(p.target_after)}`),
          el("td", {}, `${p.top_after} ${f2(p.top_after_share)}`),
          el(
            "td",
            {},
            p.effective
              ? el("span", { class: "flag flag-effective" }, "✓ EFFECTIVE")
              : [el("span", { class: "flag flag-failed" }, "✗ NOT EFFECTIVE"), " ", p.failed.join("; ")],
            p.dropped_opponents.length
              ? el("span", { class: "dim small" }, ` (opponents dropped as over budget: ${p.dropped_opponents.join(", ")})`)
              : null,
          ),
        ),
      ),
    ),
  );
}

function dominantSection(d, cfg) {
  const dep = d.dependence;
  return el(
    "section",
    { class: "panel wide", "aria-labelledby": `h-dom-${d.part}` },
    el("h2", { id: `h-dom-${d.part}` }, `${d.part.toUpperCase()} `, el("span", { class: "flag flag-dominant" }, "DOMINANT")),
    dep.mean !== null
      ? el(
          "p",
          {},
          `Why it works: champions lose ${f3(dep.mean)} of their score on average when one ${d.part} `,
          `is swapped for the best alternative (${dep.per_champion.length} champions).`,
        )
      : null,
    d.evidence.length
      ? [
          el("h3", {}, "Heuristics that keep adding it"),
          el(
            "ul",
            { class: "evidence" },
            d.evidence.map((e) =>
              el(
                "li",
                {},
                el("code", {}, e.text),
                el("span", { class: "dim" }, ` worth ${Math.round(e.worth)}, ${e.applications} applications, ${pct(e.applications ? e.improvements / e.applications : 0)} improved, ${e.runs} run(s)`),
              ),
            ),
          ),
        ]
      : null,
    d.matchups
      ? [
          el("h3", {}, "Where it helps most"),
          el("ul", {}, d.matchups.map((m) => el("li", {}, `${m.opponent}: ${f2(m.with_part)} with vs ${f2(m.without_part)} without`))),
        ]
      : el("p", { class: "dim small" }, `Matchup comparison ${d.matchups_note}.`),
    patchesTable(d, cfg.verify_seeds),
  );
}

export function renderReport(root, r) {
  if (!r) {
    fill(root, el("section", { class: "panel wide" }, el("h2", {}, "BALANCE REPORT"), el("p", {}, "No report for this run. Create one with: uv run neurisko report")));
    return;
  }
  const c = r.config;
  fill(root, 
    el(
      "section",
      { class: "panel wide", "aria-labelledby": "h-report" },
      el("h2", { id: "h-report" }, "BALANCE REPORT ", el("span", { class: "dim" }, `ruleset ${r.ruleset_hash}`)),
      el(
        "p",
        { class: "dim small" },
        `${r.seeds.length} engine runs × ${c.generations} generations; top ${c.top_k} designs per run compared with `,
        `${r.baseline_n.toLocaleString("en")} random competitive designs. Measured in ${Math.round(r.seconds)} s.`,
      ),
      el("div", { class: "summary" }, r.summary.template.split("\n\n").map((p) => el("p", {}, p))),
      r.summary.llm
        ? el(
            "figure",
            { class: "llm-summary" },
            el("figcaption", { class: "amber" }, `LLM-WRITTEN SUMMARY · ${r.summary.llm_model} · every number checked against the measurements`),
            el("blockquote", {}, r.summary.llm),
          )
        : r.summary.llm_rejected
          ? el("p", { class: "dim small" }, `LLM summary discarded: ${r.summary.llm_rejected.reason}.`)
          : null,
    ),
    el("section", { class: "panel wide", "aria-labelledby": "h-shares" }, el("h2", { id: "h-shares" }, "UNIT SHARES"), sharesTable(r.parts)),
    r.dominant.map((d) => dominantSection(d, c)),
    r.underused.length
      ? el("section", { class: "panel wide" }, el("h2", {}, "RARELY USED"), el("p", {}, `${r.underused.join(", ")}: common in random teams, avoided by strong ones.`))
      : null,
  );
}
