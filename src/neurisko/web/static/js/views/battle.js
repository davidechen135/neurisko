// Battle player: plays a battle log as teletype text in a modal dialog.
import { fill, el, pad, reducedMotion } from "../dom.js";

// Monster Mash logs: [kind, text]; text already formatted by the game.
function legacyLine([tick, kind, actor, target, amount]) {
  const t = `t${String(tick).padStart(4, " ")}  `;
  switch (kind) {
    case "attack":
      return [t, pad(actor, 18), " hits   ", pad(target, 18), String(amount).padStart(4)];
    case "dodge":
      return [t, pad(actor, 18), " dodges ", target];
    case "heal":
      return [t, pad(actor, 18), " heals  ", pad(target, 18), String(amount).padStart(4)];
    case "summon":
      return [t, pad(actor, 18), " raises ", target];
    case "death":
      return [t, pad(actor, 18), " DIES"];
    default:
      return [t, `synergy ${kind === "synergy_on" ? "ON " : "OFF"} ${actor}`];
  }
}

const SPEEDS = [
  ["1×", 120],
  ["4×", 30],
  ["16×", 8],
];

export function openBattle(dialog, b) {
  let timer = null;
  let i = 0;
  let speed = 0; // index into SPEEDS
  const log = el("ol", { class: "teletype battle-log" });
  const result = el("p", { class: "result", role: "status" });
  const items = b.lines || (b.events || []).map((e) => [e[1], legacyLine(e).join("")]);

  const stop = () => {
    if (timer) clearTimeout(timer);
    timer = null;
  };
  const finish = () => {
    stop();
    while (i < items.length) step(false);
    showResult();
  };
  const showResult = () => {
    const banner = b.winner === "draw" ? "DRAW" : `TEAM ${b.winner} WINS`;
    const unit = b.time_unit || "tick";
    result.textContent = `== ${banner} after ${b.ticks} ${unit}${b.ticks === 1 ? "" : "s"} ==`;
  };
  const step = (scroll = true) => {
    const e = items[i++];
    const li = el("li", { class: `ev ev-${e[0]}` }, e[1]);
    log.append(li);
    if (scroll) li.scrollIntoView({ block: "nearest" });
  };
  const tick = () => {
    if (i >= items.length) return showResult();
    step();
    timer = setTimeout(tick, SPEEDS[speed][1]);
  };

  const speedBtns = SPEEDS.map(([label], k) =>
    el(
      "button",
      {
        type: "button",
        "aria-pressed": String(k === speed),
        onclick: (ev) => {
          speed = k;
          speedBtns.forEach((btn, j) => btn.setAttribute("aria-pressed", String(j === k)));
          if (!timer && i < items.length) tick();
          ev.currentTarget.focus();
        },
      },
      label,
    ),
  );
  fill(dialog, 
    el(
      "div",
      { class: "dialog-body" },
      el("h2", { id: "battle-title" }, "BATTLE REPLAY ", el("span", { class: "dim" }, `seed ${b.seed}`)),
      el("p", {}, el("span", { class: "fg" }, "A  "), b.a_text || b.a.join(" > ")),
      el("p", {}, el("span", { class: "amber" }, "B  "), b.b_text || b.b.join(" > ")),
      el(
        "div",
        { class: "controls" },
        el("span", { class: "dim" }, "speed "),
        speedBtns,
        el("button", { type: "button", onclick: finish }, "skip to end"),
        el("button", { type: "button", onclick: () => dialog.close() }, "close"),
      ),
      log,
      result,
    ),
  );
  dialog.setAttribute("aria-labelledby", "battle-title");
  dialog.addEventListener("close", stop, { once: true });
  dialog.showModal();
  if (reducedMotion()) finish(); // no teletype animation
  else tick();
}
