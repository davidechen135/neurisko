// ASCII line chart in a <pre>, plus a visually hidden data table for screen readers.
import { el } from "../dom.js";

// series: [{label, mark, values: number[] (nullable)}], all of the same length.
export function asciiChart(series, { height = 8, lo = null, hi = null, colWidth = 2 } = {}) {
  const all = series.flatMap((s) => s.values).filter((v) => v !== null && v !== undefined);
  if (!all.length) return "(no data yet)";
  let min = lo ?? Math.min(...all);
  let max = hi ?? Math.max(...all);
  if (max - min < 1e-9) {
    min -= 0.05;
    max += 0.05;
  }
  const n = Math.max(...series.map((s) => s.values.length));
  const grid = Array.from({ length: height }, () => Array(n * colWidth).fill(" "));
  const rowOf = (v) => {
    const r = height - 1 - Math.round(((v - min) / (max - min)) * (height - 1));
    return Math.max(0, Math.min(height - 1, r)); // values outside [lo, hi] sit on the edge
  };
  // Draw later series first so the first series wins where they overlap.
  for (const s of [...series].reverse()) {
    s.values.forEach((v, i) => {
      if (v === null || v === undefined) return;
      grid[rowOf(v)][i * colWidth] = s.mark;
    });
  }
  const label = (r) => (max - ((max - min) * r) / (height - 1)).toFixed(2);
  const lines = grid.map((row, r) => {
    const axis = r === 0 || r === height - 1 || r === Math.floor(height / 2) ? label(r) : "    ";
    return `${axis} ┤${row.join("")}`;
  });
  const ticks = Array(n * colWidth + 2).fill(" ");
  for (let i = 0; i < n; i++) {
    const g = i + 1;
    if (g === 1 || g % 5 === 0) [...String(g)].forEach((c, k) => (ticks[i * colWidth + k] = c));
  }
  lines.push(`     └${"─".repeat(n * colWidth)}`);
  lines.push(`      ${ticks.join("")} gen`);
  return lines.join("\n");
}

export function chartWithTable(caption, series, opts) {
  const pre = el("pre", { class: "chart", "aria-hidden": "true" }, asciiChart(series, opts));
  const legend = el(
    "p",
    { class: "legend" },
    series.map((s, i) => [i ? "   " : "", el("span", { class: s.cls || "" }, s.mark), ` ${s.label}`]),
  );
  const n = Math.max(0, ...series.map((s) => s.values.length));
  const table = el(
    "table",
    { class: "sr-only" },
    el("caption", {}, caption),
    el("tr", {}, el("th", {}, "generation"), series.map((s) => el("th", {}, s.label))),
    Array.from({ length: n }, (_, i) =>
      el(
        "tr",
        {},
        el("td", {}, i + 1),
        series.map((s) => el("td", {}, s.values[i] === null ? "–" : Number(s.values[i]).toFixed(3))),
      ),
    ),
  );
  return [pre, legend, table];
}
