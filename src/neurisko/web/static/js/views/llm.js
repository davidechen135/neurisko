// The LLM tab: every Invent call with the evidence sent, the reply and what was kept.
import { fill, el, gen } from "../dom.js";

export function renderLLM(root, v, state, systemPrompt) {
  const byGen = new Map();
  for (const h of v.invented) {
    if (!byGen.has(h.gen)) byGen.set(h.gen, []);
    byGen.get(h.gen).push(h);
  }
  const rejected = new Map();
  for (const r of v.rejected.filter((r) => r.by === "M1")) {
    rejected.set(r.gen, (rejected.get(r.gen) || 0) + 1);
  }
  const calls = v.llm;
  const model = state.start?.llm;
  const tokens = calls.reduce((s, c) => s + (c.prompt_tokens || 0) + (c.completion_tokens || 0), 0);
  const secs = calls.reduce((s, c) => s + (c.latency_s || 0), 0);
  fill(root, 
    el(
      "section",
      { class: "panel wide", "aria-labelledby": "h-llm" },
      el("h2", { id: "h-llm" }, "M1 INVENT ", el("span", { class: "amber" }, model ? `· ${model}` : "· LLM off")),
      el(
        "p",
        {},
        "The LLM takes part in exactly one meta-heuristic. It reads the evidence and proposes rules; ",
        "every rule is validated against the game vocabulary before it can be used. All numbers in its ",
        "evidence come from the simulator.",
      ),
      el(
        "p",
        { class: "dim" },
        `${calls.length} calls · ${tokens.toLocaleString("en")} tokens · ${secs.toFixed(0)} s · `,
        `${v.invented.length} heuristics kept · ${v.rejected.filter((r) => r.by === "M1").length} rejected · `,
        `${v.llmErrors.length} errors/skips`,
      ),
      systemPrompt
        ? el("details", {}, el("summary", {}, "System prompt (rules and vocabulary)"), el("pre", { class: "prompt" }, systemPrompt))
        : null,
      calls.length
        ? el(
            "ol",
            { class: "llm-calls" },
            calls.map((c) =>
              el(
                "li",
                {},
                el(
                  "details",
                  {},
                  el(
                    "summary",
                    {},
                    `${gen(c.gen)}${c.attempt ? " retry" : ""} · ${c.latency_s?.toFixed(1)} s · `,
                    `${c.prompt_tokens}+${c.completion_tokens} tokens · kept ${(byGen.get(c.gen) || []).length}`,
                    rejected.get(c.gen) ? ` · rejected ${rejected.get(c.gen)}` : "",
                  ),
                  el("h3", {}, "Evidence sent"),
                  el("pre", { class: "prompt" }, c.prompt),
                  el("h3", {}, "Reply"),
                  el("pre", { class: "prompt amber" }, c.response),
                ),
                el(
                  "ul",
                  { class: "kept" },
                  (byGen.get(c.gen) || []).map((h) =>
                    el("li", {}, el("span", { class: "id" }, h.id), " ", h.name, el("span", { class: "dim" }, `  ${h.text}`)),
                  ),
                ),
              ),
            ),
          )
        : el("p", {}, "This run did not use an LLM."),
    ),
  );
}
