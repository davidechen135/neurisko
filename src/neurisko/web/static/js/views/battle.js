// Battle player: plays a battle log as teletype text in a modal dialog.
import { fill, el, pad, reducedMotion } from "../dom.js";

function line([tick, kind, actor, target, amount]) {
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

  const stop = () => {
    if (timer) clearTimeout(timer);
    timer = null;
  };
  const finish = () => {
    stop();
    while (i < b.events.length) step(false);
    showResult();
  };
  const showResult = () => {
    const banner = b.winner === "draw" ? "DRAW" : `TEAM ${b.winner} WINS`;
    result.textContent = `== ${banner} after ${b.ticks} ticks ==`;
  };
  const step = (scroll = true) => {
    const e = b.events[i++];
    const li = el("li", { class: `ev ev-${e[1]}` }, line(e));
    log.append(li);
    if (scroll) li.scrollIntoView({ block: "nearest" });
  };
  const tick = () => {
    if (i >= b.events.length) return showResult();
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
          if (!timer && i < b.events.length) tick();
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
      el("p", {}, el("span", { class: "fg" }, "A  "), b.a.join(" > ")),
      el("p", {}, el("span", { class: "amber" }, "B  "), b.b.join(" > ")),
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
