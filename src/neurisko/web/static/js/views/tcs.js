// The TCS tab: Eurisko's 1981/1982 tournament story, replayed by the engine on TCS-lite.
import { bar, el, f2, f3, fill } from "../dom.js";
import { chartWithTable } from "./chart.js";

function eraPanel(era, v) {
  const rep = v.report;
  const dominant = rep ? rep.parts.filter((p) => p.flags.includes("dominant")) : [];
  return el(
    "section",
    { class: "panel", "aria-label": `${era} era` },
    el("h2", {}, `${era} RULES `, el("span", { class: "dim" }, `run ${v.run_id}`)),
    chartWithTable(
      `${era}: champion score by generation`,
      [
        { label: "held-out + hall of fame", mark: "●", cls: "fg", values: v.series.map((s) => s[2]) },
        { label: "fixed opponents", mark: "·", cls: "dim", values: v.series.map((s) => s[1]) },
      ],
      { lo: 0.4, hi: 1, height: 7 },
    ),
    el("h3", {}, "Champion"),
    el("p", { class: "champion unit" }, v.champion_text),
    el("p", { class: "small" }, v.champion_parts.map((p) => el("span", { class: "flag flag-retired" }, p.toUpperCase()))),
    el("h3", {}, "Top heuristics"),
    el(
      "ul",
      { class: "evidence small" },
      v.heuristics.map((h) =>
        el("li", {}, el("span", { class: "id" }, h.id), ` ${Math.round(h.worth)} `, el("span", { class: "dim" }, `${h.by} `), h.text),
      ),
    ),
    rep
      ? [
          el("h3", {}, `Balance report (${rep.seeds} runs)`),
          dominant.map((p) =>
            el(
              "p",
              {},
              el("span", { class: "flag flag-dominant" }, `${p.part.toUpperCase()} DOMINANT`),
              ` in ${f2(p.evolved)} of top fleets vs ${f2(p.baseline)} of random ones`,
            ),
          ),
          el(
            "ul",
            { class: "small" },
            rep.patches.map((p) =>
              el(
                "li",
                {},
                p.effective ? el("span", { class: "flag flag-effective" }, "✓") : el("span", { class: "flag flag-failed" }, "✗"),
                " ",
                el("code", {}, p.change),
                p.effective ? "" : el("span", { class: "dim" }, `  ${p.failed.join("; ")}`),
              ),
            ),
          ),
        ]
      : null,
  );
}

export function renderTCS(root, t, playBattle) {
  if (!t) {
    fill(root, el("section", { class: "panel wide" }, el("h2", {}, "TCS"), el("p", {}, "No TCS-lite runs exported.")));
    return;
  }
  const x = t.crossover;
  fill(
    root,
    el(
      "section",
      { class: "panel wide", "aria-labelledby": "h-tcs" },
      el("h2", { id: "h-tcs" }, "1981 · THE TRILLION CREDIT SQUADRON"),
      el(
        "p",
        {},
        "In 1981 Eurisko won the U.S. Traveller TCS tournament with a fleet of 96 ships, 75 of them one cheap “Eurisko class”: ",
        "many small ships with many small weapons. The rules were changed. In 1982 it won again, because the rules let it destroy its own ships. ",
        "Here the same engine plays TCS-lite, a small game we wrote in that spirit, under a 1981 and a 1982 rule set. No LLM; seed heuristics only encode “naval officer” instincts.",
      ),
      el("p", { class: "dim small" }, t.notice, " Sources: Wikipedia “Eurisko” and “Traveller Adventure 5: Trillion Credit Squadron”, citing M. Gladwell, The New Yorker, 2009."),
    ),
    el(
      "section",
      { class: "panel wide", "aria-labelledby": "h-diff" },
      el("h2", { id: "h-diff" }, "THE RULE CHANGE"),
      el(
        "table",
        {},
        el("tr", {}, ["rule", "1981", "1982"].map((h) => el("th", { scope: "col" }, h))),
        t.rule_diff.map((d) => el("tr", {}, el("td", {}, el("code", {}, d.field)), el("td", {}, String(d.before)), el("td", { class: "amber" }, String(d.after)))),
      ),
      x
        ? el(
            "p",
            {},
            `The 1981 champion scores ${f3(x.champion_1981_under_1981)} on held-out opponents under 1981 rules and `,
            el("span", { class: "red" }, f3(x.champion_1981_under_1982)),
            ` under 1982 rules. The engine's 1982 champion, re-evolved from scratch, scores ${f3(x.champion_1982_under_1982)}.`,
          )
        : null,
      el(
        "div",
        { class: "battles" },
        el("p", { class: "dim small" }, "Replay:"),
        t.battles.map((b) => el("button", { type: "button", onclick: () => playBattle(b) }, `▶ ${b.title}`)),
      ),
    ),
    el("div", { class: "grid" }, eraPanel("1981", t.eras["1981"]), eraPanel("1982", t.eras["1982"])),
  );
}
