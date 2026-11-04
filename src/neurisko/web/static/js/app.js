// Neurisko console. Loads data/manifest.json, which says whether this is a static replay
// (GitHub Pages) or the live server, and where the data lives. All URLs are relative, so the
// site works under any sub-path.
import { fill, el, gen } from "./dom.js";
import { at, emptyState, reduce, reduceAll } from "./reducer.js";
import { openBattle } from "./views/battle.js";
import { renderH59 } from "./views/h59.js";
import { renderLLM } from "./views/llm.js";
import { renderReport } from "./views/report.js";
import { renderRun } from "./views/run.js";
import { renderTCS } from "./views/tcs.js";

const $ = (id) => document.getElementById(id);
const TABS = ["run", "report", "h59", "tcs", "llm"];

const app = {
  manifest: null,
  run: null, // run view model (meta, events, battles)
  state: emptyState(),
  report: null,
  h59: null,
  tcs: null,
  g: 0,
  follow: true,
  playing: null,
  showAllAudits: false,
  live: null, // EventSource
};

async function getJSON(url) {
  const r = await fetch(url, { cache: "no-cache" });
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  return r.json();
}

// --- rendering ------------------------------------------------------------------------------

function currentTab() {
  const t = location.hash.slice(1);
  return TABS.includes(t) ? t : "run";
}

function render() {
  const tab = currentTab();
  for (const t of TABS) {
    $(`tab-${t}`).setAttribute("aria-selected", String(t === tab));
    $(`tab-${t}`).tabIndex = t === tab ? 0 : -1;
    $(`panel-${t}`).hidden = t !== tab;
  }
  // The scrubber only affects the run and LLM views.
  document.querySelector(".scrubber").hidden = !(tab === "run" || tab === "llm");
  $("chk-audits").parentElement.hidden = tab !== "run";
  const v = at(app.state, app.g);
  renderHeader(v);
  renderScrubber(v);
  if (tab === "run")
    renderRun($("panel-run"), v, {
      battles: app.run?.battles,
      playBattle: playBattle,
      showAllAudits: app.showAllAudits,
    });
  if (tab === "report") renderReport($("panel-report"), app.report);
  if (tab === "h59") renderH59($("panel-h59"), app.h59);
  if (tab === "tcs") renderTCS($("panel-tcs"), app.tcs, playBattle);
  if (tab === "llm") renderLLM($("panel-llm"), v, app.state, app.run?.system_prompt);
}

function renderHeader(v) {
  const start = app.state.start;
  const cfg = start?.config || app.run?.meta?.config || {};
  const status = app.state.end ? app.state.end.reason.toUpperCase() : app.live ? "RUNNING" : "";
  fill($("run-info"), 
    app.run ? `run ${app.run.id}` : "no run",
    " · ",
    el("span", { class: "amber" }, start?.llm ? `llm ${start.llm}` : "llm off"),
    " · ",
    cfg.auditor === false ? el("span", { class: "red" }, "AUDITOR OFF") : "auditor on",
    " · ",
    el("strong", {}, `${gen(v.gen)}/${v.total}`),
    status ? ` · ${status}` : "",
  );
}

function renderScrubber(v) {
  const range = $("gen-range");
  range.max = String(Math.max(1, v.total));
  range.value = String(v.gen || 1);
  range.disabled = v.total <= 1;
  range.setAttribute("aria-valuetext", `generation ${v.gen} of ${v.total}`);
  $("gen-label").textContent = `${gen(v.gen)} / ${v.total}`;
  $("btn-play").textContent = app.playing ? "❚❚ pause" : "▶ play";
}

function playBattle(b) {
  openBattle($("battle-dialog"), b);
}

// --- generation controls -------------------------------------------------------------------

function setGen(g, { user = true } = {}) {
  const n = app.state.gens.length;
  app.g = Math.max(1, Math.min(n, g));
  if (user) app.follow = app.g === n;
  render();
}

function togglePlay() {
  if (app.playing) {
    clearInterval(app.playing);
    app.playing = null;
    return render();
  }
  if (app.g >= app.state.gens.length) app.g = 0;
  app.playing = setInterval(() => {
    if (app.g >= app.state.gens.length) {
      clearInterval(app.playing);
      app.playing = null;
      return render();
    }
    setGen(app.g + 1);
  }, 700);
  render();
}

// --- data loading --------------------------------------------------------------------------

async function loadRun(url) {
  app.run = await getJSON(url);
  app.state = reduceAll(app.run.events);
  app.g = app.state.gens.length;
  app.follow = true;
}

function startLiveStream(runId) {
  if (app.live) app.live.close();
  app.run = { id: runId, events: [], battles: {}, system_prompt: null, meta: {} };
  app.state = emptyState();
  app.g = 0;
  app.follow = true;
  const src = new EventSource(`api/live/${encodeURIComponent(runId)}/events`);
  app.live = src;
  src.onmessage = (msg) => {
    const e = JSON.parse(msg.data);
    reduce(app.state, e);
    if (e.type === "generation" && app.follow) app.g = app.state.gens.length;
    if (e.type === "run_end") {
      src.close();
      app.live = null;
      refreshRunList(runId).then(() => loadRun(`api/runs/${encodeURIComponent(runId)}`)).then(render);
    }
    render();
  };
  src.onerror = () => {
    if (src.readyState === EventSource.CLOSED) app.live = null;
  };
}

async function refreshRunList(select) {
  if (app.manifest.mode !== "live") return;
  const runs = await getJSON("api/runs");
  const sel = $("run-select");
  fill(sel, 
    runs.map((r) =>
      el("option", { value: r.id, selected: r.id === select }, `${r.id}${r.llm ? " · llm" : ""}${r.auditor === false ? " · no auditor" : ""}`),
    ),
  );
}

function setupLive() {
  $("live-controls").hidden = false;
  $("run-select").addEventListener("change", async (e) => {
    await loadRun(`api/runs/${encodeURIComponent(e.target.value)}`);
    render();
  });
  $("live-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    const body = {
      seed: Number(f.get("seed")),
      generations: Number(f.get("generations")),
      llm: f.get("llm") === "on",
      auditor: f.get("auditor") === "on",
    };
    const out = $("live-status");
    const r = await fetch("api/live", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const data = await r.json();
    if (!r.ok) {
      out.textContent = data.detail?.message || JSON.stringify(data.detail || data);
      return;
    }
    out.textContent = `started ${data.id}`;
    location.hash = "run";
    startLiveStream(data.id);
  });
}

// --- startup ---------------------------------------------------------------------------------

function setupChrome() {
  const crtSaved = localStorage.getItem("neurisko-crt");
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const crt = crtSaved === null ? !reduced : crtSaved === "on";
  document.body.classList.toggle("crt", crt);
  const btn = $("btn-crt");
  btn.setAttribute("aria-pressed", String(crt));
  btn.addEventListener("click", () => {
    const on = !document.body.classList.contains("crt");
    document.body.classList.toggle("crt", on);
    btn.setAttribute("aria-pressed", String(on));
    localStorage.setItem("neurisko-crt", on ? "on" : "off");
  });

  for (const t of TABS) $(`tab-${t}`).addEventListener("click", () => (location.hash = t));
  $("tabs").addEventListener("keydown", (e) => {
    const i = TABS.indexOf(currentTab());
    const next = e.key === "ArrowRight" ? i + 1 : e.key === "ArrowLeft" ? i - 1 : null;
    if (next === null) return;
    const t = TABS[(next + TABS.length) % TABS.length];
    location.hash = t;
    $(`tab-${t}`).focus();
  });
  window.addEventListener("hashchange", render);

  $("gen-range").addEventListener("input", (e) => setGen(Number(e.target.value)));
  $("btn-prev").addEventListener("click", () => setGen(app.g - 1));
  $("btn-next").addEventListener("click", () => setGen(app.g + 1));
  $("btn-play").addEventListener("click", togglePlay);
  $("chk-audits").addEventListener("change", (e) => {
    app.showAllAudits = e.target.checked;
    render();
  });
}

async function main() {
  setupChrome();
  try {
    app.manifest = await getJSON("data/manifest.json");
    const m = app.manifest;
    const [, report, h59, tcs] = await Promise.all([
      m.run_url ? loadRun(m.run_url) : null,
      m.report_url ? getJSON(m.report_url).catch(() => null) : null,
      m.h59_url ? getJSON(m.h59_url).catch(() => null) : null,
      m.tcs_url ? getJSON(m.tcs_url).catch(() => null) : null,
    ]);
    app.tcs = tcs;
    app.report = report;
    app.h59 = h59;
    if (m.mode === "live") {
      setupLive();
      await refreshRunList(app.run?.id);
      if (m.live_id) startLiveStream(m.live_id); // a run is in progress: follow it
    }
  } catch (err) {
    fill($("panel-run"), el("p", { class: "red" }, `Could not load data: ${err.message}`));
    console.error(err);
    return;
  }
  render();
}

main();
