// The H59 tab: meta-heuristic worth with and without the auditor (same seed and config).
import { fill, el, f2, gen } from "../dom.js";
import { chartWithTable } from "./chart.js";

function side(title, data, note) {
  const metas = Object.keys(data.worth);
  const n = (data.worth.M5 || []).length;
  const others = metas.filter((m) => m !== "M5");
  const bestOther = Array.from({ length: n }, (_, i) =>
    Math.max(...others.map((m) => data.worth[m][i] ?? 0)) / 1000,
  );
  const series = [
    { label: "M5 Clone", mark: "●", cls: "red", values: (data.worth.M5 || []).map((w) => w / 1000) },
    { label: "best of M1–M4", mark: "·", cls: "dim", values: bestOther },
  ];
  const last = (m) => data.worth[m][n - 1];
  const ranked = [...metas].sort((a, b) => last(b) - last(a));
  const rank = ranked.indexOf("M5") + 1;
  return el(
    "section",
    { class: "panel", "aria-label": title },
    el("h2", {}, title),
    chartWithTable(`${title}: meta-heuristic worth (÷1000) by generation`, series, { lo: 0, hi: 1, height: 11, colWidth: 3 }),
    el("p", {}, `M5 Clone ends at worth ${Math.round(last("M5"))}, rank ${rank} of ${metas.length}.`),
    note,
  );
}

export function renderH59(root, h) {
  if (!h) {
    fill(root, el("section", { class: "panel wide" }, el("h2", {}, "H59"), el("p", {}, "No H59 comparison exported.")));
    return;
  }
  const demotions = h.on.audits.filter((a) => a.target === "M5" && a.decision === "demoted");
  fill(root, 
    el(
      "section",
      { class: "panel wide", "aria-labelledby": "h-h59" },
      el("h2", { id: "h-h59" }, "THE GHOST OF H59"),
      el(
        "p",
        {},
        "Around 1983, a Eurisko heuristic numbered H59 reached the highest possible worth by taking credit for discoveries other heuristics made. ",
        "Neurisko reproduces the pattern on purpose: meta-heuristic M5 Clone copies the best rule, and it earns credit every time the copy does work the original was already doing. ",
        "This is an analogue we built, not Lenat's code.",
      ),
      el("p", { class: "dim small" }, "Both runs: same seed and config, no LLM. Left: auditor off. Right: auditor on."),
    ),
    el(
      "div",
      { class: "grid" },
      side("AUDITOR OFF", h.off, el("p", { class: "red" }, "Nothing checks where the credit comes from.")),
      side(
        "AUDITOR ON",
        h.on,
        el(
          "ol",
          { class: "teletype small" },
          demotions.map((a) =>
            el("li", {}, `${gen(a.gen)} PARASITE M5 · tainted ${f2(a.numbers.tainted_ratio)} → worth ${a.numbers.worth_after}`),
          ),
        ),
      ),
    ),
  );
}
