// Tiny DOM helpers. Run data (including LLM text) is only ever inserted as text nodes.

export function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : String(value));
  }
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

// Replace a node's children; arrays are flattened, strings become text nodes.
export function fill(node, ...children) {
  node.replaceChildren(
    ...children
      .flat(Infinity)
      .filter((c) => c !== null && c !== undefined && c !== false)
      .map((c) => (c instanceof Node ? c : document.createTextNode(String(c)))),
  );
  return node;
}

export function clear(node) {
  node.replaceChildren();
  return node;
}

export function bar(fraction, width = 10) {
  const x = Math.max(0, Math.min(1, fraction)) * width;
  const full = Math.floor(x);
  const parts = ["", "▏", "▎", "▍", "▌", "▋", "▊", "▉"];
  const rest = parts[Math.round((x - full) * 7)] || "";
  return ("█".repeat(full) + rest).padEnd(width, " ");
}

export const f2 = (x) => (x === null || x === undefined ? "–" : Number(x).toFixed(2));
export const f3 = (x) => (x === null || x === undefined ? "–" : Number(x).toFixed(3));
export const pct = (x) => `${Math.round(x * 100)}%`;
export const pad = (s, n) => String(s).padEnd(n, " ");
export const gen = (g) => `G${String(g).padStart(2, "0")}`;

export const reducedMotion = () =>
  window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
