// Visual battle arena, drawn above the text log. `apply(i, animate)` shows step i of
// b.visual.steps (one step per log line). The text log stays the accessible record; the
// arena is aria-hidden.
import { el } from "../dom.js";

const ICONS = {
  skeleton: "💀", zombie: "🧟", necromancer: "🔮", werewolf: "🐺", bat_swarm: "🦇",
  hellhound: "🐕", witch: "🧙", pumpkin_mage: "🎃", ghost: "👻", flesh_golem: "🧌",
  gargoyle: "🗿", scarecrow: "🌾",
};
const icon = (id) => ICONS[id] || id.slice(0, 2).toUpperCase();

function popup(host, text, cls) {
  const p = el("span", { class: `pop ${cls}` }, text);
  host.append(p);
  setTimeout(() => p.remove(), 900);
}

function pulse(node, cls) {
  node.classList.remove(cls);
  void node.offsetWidth; // restart the CSS animation
  node.classList.add(cls);
}

// --- Monster Mash: two lines of monsters facing each other, front ranks at the centre -------
function monsterArena(v) {
  const cards = new Map();
  const sides = { A: el("div", { class: "side side-A" }), B: el("div", { class: "side side-B" }) };
  const syn = { A: el("div", { class: "syn" }), B: el("div", { class: "syn" }) };

  const card = (u) => {
    const fillBar = el("i");
    const hpText = el("span", { class: "hpn" });
    const node = el(
      "div",
      { class: `u u-${u.side}${u.ranged ? " ranged" : ""}`, title: u.label },
      el("div", { class: "ico" }, icon(u.id)),
      el("div", { class: "nm" }, u.id.replace(/_/g, " ")),
      el("div", { class: "hp" }, fillBar),
      hpText,
    );
    const c = { node, fillBar, hpText, hp: u.hp, max: u.hp, alive: true, side: u.side };
    cards.set(u.label, c);
    return c;
  };
  const draw = (c) => {
    c.fillBar.style.width = `${Math.max(0, Math.min(1, c.hp / c.max)) * 100}%`;
    c.fillBar.className = c.hp / c.max < 0.34 ? "low" : "";
    c.hpText.textContent = `${Math.max(0, c.hp)}/${c.max}`;
  };
  const front = () => {
    for (const s of ["A", "B"]) {
      let pos = 0;
      for (const c of cards.values()) {
        if (c.side !== s) continue;
        c.node.classList.toggle("front", c.alive && pos < v.front);
        if (c.alive) pos += 1;
      }
    }
  };
  const place = (u, pop) => {
    const c = card(u);
    draw(c);
    sides[u.side].append(c.node);
    if (pop) pulse(c.node, "spawn");
  };
  const reset = () => {
    cards.clear();
    sides.A.replaceChildren();
    sides.B.replaceChildren();
    syn.A.replaceChildren();
    syn.B.replaceChildren();
    v.units.filter((u) => !u.summoned).forEach((u) => place(u, false));
    front();
  };
  const unitOf = new Map(v.units.map((u) => [u.label, u]));

  const apply = (i, animate) => {
    const [kind, actor, target, amount, updates] = v.steps[i];
    if (kind === "summon") place(unitOf.get(target), animate);
    for (const [label, hp, max] of updates) {
      const c = cards.get(label);
      c.hp = hp;
      c.max = max;
      draw(c);
    }
    const a = cards.get(actor);
    const t = cards.get(target);
    if (kind === "attack") {
      if (animate) {
        pulse(a.node, a.node.classList.contains("ranged") ? "cast" : "lunge");
        pulse(t.node, "hit");
        popup(t.node, `-${amount}`, "dmg");
      }
    } else if (kind === "dodge") {
      if (animate) popup(a.node, "MISS", "miss");
    } else if (kind === "heal") {
      if (animate) {
        pulse(t.node, "healed");
        popup(t.node, `+${amount}`, "heal");
      }
    } else if (kind === "death") {
      a.alive = false;
      a.node.classList.add("dead");
      front();
    } else if (kind === "synergy_on" || kind === "synergy_off") {
      const [side, faction] = actor.split(":");
      const key = `syn-${faction}`;
      const old = syn[side].querySelector(`[data-f="${faction}"]`);
      if (kind === "synergy_on" && !old) {
        const chip = el("span", { class: `chip ${key}`, "data-f": faction }, `${faction} synergy`);
        syn[side].append(chip);
        if (animate) pulse(chip, "spawn");
      } else if (kind === "synergy_off" && old) old.remove();
    }
    if (kind === "summon") front();
  };

  const node = el(
    "div",
    { class: "arena arena-monster", "aria-hidden": "true" },
    el("div", { class: "wing" }, syn.A, sides.A),
    el("div", { class: "vs" }, "VS"),
    el("div", { class: "wing" }, syn.B, sides.B),
  );
  reset();
  return { node, apply, reset };
}

// --- TCS-lite: two fleets of ship glyphs; hits fly across as tracers --------------------------
const SHIP_STATE = { a: "able", d: "disabled", x: "destroyed", s: "scuttled" };

function fleetArena(v) {
  const panels = {};
  const make = (side) => {
    const f = v.sides[side];
    const ships = f.ships.map((k) =>
      el("span", { class: `ship hull${f.classes[k].hull} able` }, side === "A" ? "▶" : "◀"),
    );
    const count = el("div", { class: "count" });
    const banner = el("div", { class: "banner" });
    const grid = el("div", { class: "ships" }, ships);
    const node = el(
      "div",
      { class: `fleet fleet-${side}` },
      el("div", { class: "fleet-head" }, el("b", {}, `FLEET ${side}`), count),
      grid,
      banner,
    );
    panels[side] = { node, ships, count, banner, grid, state: "a".repeat(ships.length) };
  };
  make("A");
  make("B");
  const counts = (p) => {
    const n = (ch) => [...p.state].filter((c) => c === ch).length;
    p.count.textContent = `able ${n("a")} · disabled ${n("d")} · sunk ${n("x")}${n("s") ? ` · scuttled ${n("s")}` : ""}`;
  };
  const setState = (side, state, animate) => {
    const p = panels[side];
    [...state].forEach((ch, k) => {
      if (p.state[k] === ch) return;
      const s = p.ships[k];
      s.className = s.className.replace(/ (able|disabled|destroyed|scuttled)/, ` ${SHIP_STATE[ch]}`);
      if (animate && ch !== "a") pulse(s, "boom");
    });
    p.state = state;
    counts(p);
  };
  const tracers = el("div", { class: "tracers" });
  const reset = () => {
    for (const side of ["A", "B"]) {
      setState(side, "a".repeat(panels[side].ships.length), false);
      panels[side].banner.textContent = "";
      panels[side].node.classList.remove("out");
    }
    tracers.replaceChildren();
  };
  const volley = (from, hits) => {
    const n = Math.min(hits, 24);
    for (let k = 0; k < n; k++) {
      const t = el("i", { class: `tracer from-${from}` });
      t.style.top = `${8 + Math.random() * 84}%`;
      t.style.animationDelay = `${Math.random() * 0.25}s`;
      tracers.append(t);
      setTimeout(() => t.remove(), 900);
    }
  };
  const apply = (i, animate) => {
    const [kind, actor, , amount, snap] = v.steps[i];
    const side = actor[0];
    if (kind === "attack" && animate) volley(side, amount);
    if (kind === "withdraw") {
      panels[side].banner.textContent = "WITHDRAWS";
      panels[side].node.classList.add("out");
    }
    if (kind === "scuttle") {
      panels[side].banner.textContent = "SCUTTLES!";
      if (animate) pulse(panels[side].banner, "flash");
    }
    for (const s of ["A", "B"]) if (snap[s]) setState(s, snap[s], animate);
  };
  const node = el(
    "div",
    { class: "arena arena-fleet", "aria-hidden": "true" },
    panels.A.node,
    tracers,
    panels.B.node,
  );
  reset();
  return { node, apply, reset };
}

export function makeArena(b) {
  if (!b.visual) return null;
  return b.visual.kind === "fleet" ? fleetArena(b.visual) : monsterArena(b.visual);
}
