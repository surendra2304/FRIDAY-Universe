/**
 * FRIDAY PRIME — neural console logic
 *
 * - One-time owner key gate -> short-lived control sessions (auto-refresh).
 * - Chat goes to POST /api/chat (the friend persona + cognitive pipeline),
 *   NOT the autonomous-goal engine. It talks back with POST /api/voice/speak.
 * - Fleet panel polls GET /api/agents/status.
 * - Ambient: starfield canvas + waveform canvas + parallax core glow.
 */
"use strict";

const BASE = (() => {
  const p = window.location.pathname;
  return p === "/friday" || p.startsWith("/friday/") ? "/friday" : "";
})();

const KEY_STORAGE = "friday_prime_key";
const $ = (id) => document.getElementById(id);

/* ------------------------------------------------------------------ */
/* state                                                               */
/* ------------------------------------------------------------------ */
let apiKey = "";
try { apiKey = localStorage.getItem(KEY_STORAGE) || ""; } catch { /* private mode */ }
let sessionToken = null;
let sessionRefreshTimer = null;
let busy = false;
let speakEnabled = true;
let audioEl = null;
let recognition = null;
let recording = false;

const AGENT_META = {
  FRIDAY:   { role: "Orchestrator",  core: true },
  Inference:{ role: "Reasoning",     core: false },
  Memora:   { role: "Memory",        core: false },
  Stratex:  { role: "Trading",       core: false },
  Futuris:  { role: "Forecasting",   core: false },
  IntelX:   { role: "Research",      core: false },
  Forge:    { role: "Code",          core: false },
  Cortex:   { role: "Decisions",     core: false },
  Sentinel: { role: "Security",      core: false },
  VyralX:   { role: "Content",       core: false },
};

/* ------------------------------------------------------------------ */
/* boot sequence                                                       */
/* ------------------------------------------------------------------ */
const BOOT_LINES = [
  ["FRIDAY PRIME v2.0 — neural link initiator", ""],
  ["establishing quantum tunnel to friday-universe.duckdns.org", "ok"],
  ["mesh handshake: 10 agents expected", "ok"],
  ["memory fabric [MEMORA] ......... SYNCED", "ok"],
  ["inference grid [GROQ / OPENROUTER] .... ONLINE", "ok"],
  ["persona core: FRIEND MODE ......... LOADED", "ok"],
  ["security lattice ..................... ARMED", "ok"],
  ["awaiting owner authorization", "warn"],
];

async function runBoot() {
  const log = $("bootlog");
  log.innerHTML = "";
  for (const [text, cls] of BOOT_LINES) {
    const div = document.createElement("div");
    div.textContent = "> " + text;
    if (cls) div.className = cls;
    log.appendChild(div);
    await sleep(230);
  }
  if (apiKey) {
    const ok = await trySession();
    if (ok) return enterHud();
  }
  $("gate").classList.add("show");
}

function enterHud() {
  $("boot").classList.add("wiped");
  $("hud").classList.add("live");
  setTimeout(() => { $("boot").style.display = "none"; }, 1000);
  greet();
  startAmbient();
}

function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

/* ------------------------------------------------------------------ */
/* auth: key gate + control session                                    */
/* ------------------------------------------------------------------ */
async function mintSession() {
  const headers = { "Content-Type": "application/json" };
  if (apiKey) headers["x-friday-api-key"] = apiKey;
  const res = await fetch(BASE + "/api/control/session", { headers, cache: "no-store" });
  if (!res.ok) throw Object.assign(new Error("session " + res.status), { status: res.status });
  const data = await res.json();
  sessionToken = data.token;
  const ttl = Number(data.ttl_seconds || 1200);
  clearTimeout(sessionRefreshTimer);
  sessionRefreshTimer = setTimeout(() => mintSession().catch(() => setLink(false)), Math.max(60, ttl - 300) * 1000);
  setLink(true);
  return true;
}

async function trySession() {
  try { return await mintSession(); }
  catch (e) {
    setLink(false);
    if (e.status === 401 || e.status === 403 || e.status === 503) return false;
    return false;
  }
}

function setLink(up) {
  const dot = $("linkDot");
  const text = $("linkText");
  if (!dot || !text) return;
  dot.classList.toggle("off", !up);
  text.textContent = up ? "NEURAL LINK" : "LINK DOWN";
}

async function apiFetch(path, opts = {}) {
  opts.headers = Object.assign({}, opts.headers || {}, {
    "X-FRIDAY-Control-Token": sessionToken || "",
    "Content-Type": "application/json",
  });
  let res = await fetch(BASE + path, opts);
  if (res.status === 401) {
    await mintSession();
    opts.headers["X-FRIDAY-Control-Token"] = sessionToken;
    res = await fetch(BASE + path, opts);
  }
  return res;
}

function bindGate() {
  const input = $("keyInput");
  const btn = $("authorizeBtn");
  const err = $("gateError");
  const attempt = async () => {
    const key = (input.value || "").trim();
    if (!key) { err.textContent = "Enter the access key first."; return; }
    btn.disabled = true; btn.textContent = "Authenticating…";
    try {
      apiKey = key;
      try { localStorage.setItem(KEY_STORAGE, key); } catch { /* private mode */ }
      const ok = await trySession();
      if (ok) { enterHud(); return; }
      apiKey = "";
      try { localStorage.removeItem(KEY_STORAGE); } catch { /* private mode */ }
      err.textContent = "Key rejected. Check it on the server and try again.";
    } catch (e) {
      err.textContent = "Could not reach FRIDAY. Check your connection.";
    } finally {
      btn.disabled = false; btn.textContent = "Authorize Neural Link";
    }
  };
  btn.addEventListener("click", attempt);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") attempt(); });
}

/* ------------------------------------------------------------------ */
/* chat                                                                */
/* ------------------------------------------------------------------ */
function addMsg(who, text, meta) {
  const scroll = $("chatScroll");
  const wrap = document.createElement("div");
  wrap.className = "msg " + who;
  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = who === "friday" ? "F" : "YOU";
  if (who === "user") avatar.textContent = "S";
  const col = document.createElement("div");
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  col.appendChild(bubble);
  if (meta) {
    const m = document.createElement("div");
    m.className = "meta-line";
    m.textContent = meta;
    col.appendChild(m);
  }
  wrap.appendChild(avatar);
  wrap.appendChild(col);
  scroll.appendChild(wrap);
  scroll.scrollTop = scroll.scrollHeight;
}

function showTyping() {
  const scroll = $("chatScroll");
  const wrap = document.createElement("div");
  wrap.className = "msg friday";
  wrap.id = "typingRow";
  wrap.innerHTML =
    '<div class="avatar">F</div><div class="bubble typing"><i></i><i></i><i></i></div>';
  scroll.appendChild(wrap);
  scroll.scrollTop = scroll.scrollHeight;
}
function clearTyping() { const t = $("typingRow"); if (t) t.remove(); }

function setCore(state, label) {
  const r = $("reactor");
  if (r) r.dataset.state = state;
  const cap = $("coreCaption");
  if (cap && label) cap.textContent = label;
}

async function sendMessage(text) {
  text = (text || "").trim();
  if (!text || busy) return;
  busy = true;
  $("sendBtn").disabled = true;
  addMsg("user", text);
  const input = $("textInput");
  if (input) input.value = "";
  setCore("thinking", "Thinking…");
  showTyping();
  const t0 = performance.now();
  try {
    const res = await apiFetch("/api/chat", { method: "POST", body: JSON.stringify({ message: text }) });
    if (!res.ok) throw new Error("chat " + res.status);
    const data = await res.json();
    clearTyping();
    const reply = data.reply || "(no reply)";
    const secs = ((performance.now() - t0) / 1000).toFixed(1);
    const cap = data.metadata && data.metadata.routed_capability;
    addMsg("friday", reply, `${secs}s${cap ? " · " + cap : ""}`);
    if (speakEnabled && reply) speakReply(reply);
  } catch (e) {
    clearTyping();
    addMsg("friday", "I lost the link for a second there — give me a moment and try again.", "link error");
  } finally {
    busy = false;
    $("sendBtn").disabled = false;
    if (!audioEl || audioEl.paused) setCore("idle", "Online");
  }
}

async function speakReply(text) {
  try {
    setCore("speaking", "Speaking…");
    const res = await apiFetch("/api/voice/speak", {
      method: "POST",
      body: JSON.stringify({ text: String(text).slice(0, 1800), lang: "en" }),
    });
    if (!res.ok) { setCore("idle", "Online"); return; }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    if (!audioEl) {
      audioEl = new Audio();
      audioEl.onended = () => { setCore("idle", "Online"); stopWave(); };
    }
    audioEl.src = url;
    playWave();
    await audioEl.play();
  } catch (e) {
    setCore("idle", "Online");
  }
}

function greet() {
  const hour = new Date().getHours();
  const part = hour < 5 ? "Working late" : hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
  const hello = `${part}, Surendra. All ten of my agents are awake and the neural link is secure. What are we doing today?`;
  addMsg("friday", hello, "friend persona · live");
}

/* ------------------------------------------------------------------ */
/* mic (browser speech recognition)                                    */
/* ------------------------------------------------------------------ */
function bindMic() {
  const btn = $("micBtn");
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR || !btn) { if (btn) btn.style.display = "none"; return; }
  recognition = new SR();
  recognition.lang = "en-IN";
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;
  recognition.onresult = (e) => {
    const said = e.results[0][0].transcript;
    const input = $("textInput");
    if (input) input.value = said;
    sendMessage(said);
  };
  recognition.onend = () => {
    recording = false;
    btn.classList.remove("recording");
    setCore("idle", "Online");
  };
  recognition.onerror = () => {
    recording = false;
    btn.classList.remove("recording");
    setCore("idle", "Online");
  };
  btn.addEventListener("click", () => {
    if (recording) { recognition.stop(); return; }
    try {
      recognition.start();
      recording = true;
      btn.classList.add("recording");
      setCore("listening", "Listening…");
      playWave();
    } catch { /* already started */ }
  });
}

/* ------------------------------------------------------------------ */
/* fleet + health                                                      */
/* ------------------------------------------------------------------ */
async function pollFleet() {
  const list = $("fleetList");
  const summary = $("fleetSummary");
  if (!list || !summary) return;
  try {
    const res = await fetch(BASE + "/api/agents/status", { cache: "no-store" });
    if (!res.ok) throw new Error("status " + res.status);
    const data = await res.json();
    const agents = (data.agents || []).map((a) => ({
      name: (a.agent || a.name || "").toUpperCase(),
      status: a.status || "UNKNOWN",
      latency: a.latency_ms != null ? a.latency_ms : null,
    }));
    // FRIDAY itself is implied online if the API answered:
    const rows = [{ name: "FRIDAY", status: "ONLINE", latency: null }].concat(
      agents.filter((a) => a.name && a.name !== "FRIDAY")
    );
    renderFleet(rows);
  } catch (e) {
    summary.textContent = "MESH UNREACHABLE";
    summary.style.color = "var(--red)";
  }
}

function renderFleet(rows) {
  const list = $("fleetList");
  const summary = $("fleetSummary");
  list.innerHTML = "";
  let online = 0;
  rows.forEach((row, i) => {
    const meta = AGENT_META[row.name] || { role: "Agent", core: false };
    const cls = row.status === "ONLINE" || row.status === "REACHABLE" ? "" :
                row.status === "DEGRADED" ? "warn" : "off";
    if (!cls) online++;
    const div = document.createElement("div");
    div.className = "agent";
    div.style.animationDelay = (i * 60) + "ms";
    div.innerHTML =
      `<span class="a-dot ${cls}"></span>` +
      `<div><div class="a-name">${row.name}</div>` +
      `<div class="a-role">${meta.role}</div></div>` +
      (row.latency != null ? `<span class="a-lat">${row.latency}ms</span>` : `<span class="a-lat">${row.status.toLowerCase()}</span>`);
    list.appendChild(div);
  });
  const all = rows.length;
  summary.textContent = `${online}/${all} UNITS ONLINE`;
  summary.style.color = online === all ? "var(--green)" : "var(--amber)";
  const mesh = $("statMesh");
  if (mesh) {
    mesh.querySelector("b").textContent = online === all ? "10/10 CONNECTED" : `${online}/${all} CONNECTED`;
    mesh.classList.toggle("ok", online === all);
  }
}

async function pollHealth() {
  try {
    const res = await fetch(BASE + "/health", { cache: "no-store" });
    const data = await res.json();
    const v = $("versionPill");
    if (v && data.version) v.textContent = "PRIME v" + data.version;
  } catch { /* transient */ }
}

/* ------------------------------------------------------------------ */
/* ambient: starfield, waveform, clock                                 */
/* ------------------------------------------------------------------ */
function startAmbient() {
  startCosmos();
  startWave();
  startClock();
  pollFleet();
  pollHealth();
  setInterval(pollFleet, 15000);
  setInterval(pollHealth, 60000);
  setInterval(refreshSessionQuiet, 15 * 60 * 1000);
}

function refreshSessionQuiet() { mintSession().catch(() => setLink(false)); }

function startClock() {
  const clock = $("clock");
  const tick = () => {
    const d = new Date();
    clock.textContent = d.toLocaleTimeString([], { hour12: false });
  };
  tick();
  setInterval(tick, 1000);
}

function startCosmos() {
  const canvas = $("cosmos");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  let stars = [];
  const fit = () => {
    canvas.width = innerWidth;
    canvas.height = innerHeight;
    const count = Math.min(220, Math.round((canvas.width * canvas.height) / 9000));
    stars = Array.from({ length: count }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      r: Math.random() * 1.4 + 0.2,
      p: Math.random() * Math.PI * 2,
      s: Math.random() * 0.55 + 0.2,
    }));
  };
  fit();
  window.addEventListener("resize", fit);
  (function frame() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const t = performance.now() / 1000;
    for (const st of stars) {
      const tw = 0.35 + 0.65 * Math.abs(Math.sin(st.p + t * st.s));
      ctx.beginPath();
      ctx.arc(st.x, st.y, st.r, 0, 6.283);
      ctx.fillStyle = `rgba(148, 226, 255, ${tw * 0.8})`;
      ctx.shadowColor = "rgba(34,211,238,0.8)";
      ctx.shadowBlur = 4;
      ctx.fill();
    }
    requestAnimationFrame(frame);
  })();
}

/* waveform bars while speaking/listening */
let waveRAF = null;
function playWave() {
  const c = $("waveform");
  if (!c) return;
  const ctx = c.getContext("2d");
  const W = (c.width = 170), H = (c.height = 34);
  stopWave();
  (function draw() {
    ctx.clearRect(0, 0, W, H);
    const t = performance.now() / 180;
    for (let i = 0; i < 24; i++) {
      const amp = Math.abs(Math.sin(t + i * 0.55)) * (H / 2 - 3) + 2;
      const x = 6 + i * 6.8;
      const grad = ctx.createLinearGradient(0, H / 2 - amp, 0, H / 2 + amp);
      grad.addColorStop(0, "rgba(34,211,238,0.9)");
      grad.addColorStop(1, "rgba(139,92,246,0.7)");
      ctx.fillStyle = grad;
      ctx.fillRect(x, H / 2 - amp, 3, amp * 2);
    }
    waveRAF = requestAnimationFrame(draw);
  })();
}
function stopWave() {
  if (waveRAF) cancelAnimationFrame(waveRAF);
  waveRAF = null;
  const c = $("waveform");
  if (c) { const ctx = c.getContext("2d"); ctx.clearRect(0, 0, c.width, c.height); }
}

/* ------------------------------------------------------------------ */
/* input bindings                                                      */
/* ------------------------------------------------------------------ */
function bindInput() {
  $("sendBtn").addEventListener("click", () => {
    const input = $("textInput");
    if (input && input.value.trim()) sendMessage(input.value.trim());
  });
  $("textInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      const input = $("textInput");
      if (input.value.trim()) sendMessage(input.value.trim());
    }
  });
  document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const input = $("textInput");
      if (input && chip.dataset.fill) {
        input.value = chip.dataset.fill;
        sendMessage(chip.dataset.fill);
      }
    });
  });
  const toggle = $("speakToggle");
  toggle.addEventListener("click", () => {
    speakEnabled = !speakEnabled;
    toggle.classList.toggle("on", speakEnabled);
    if (!speakEnabled && audioEl) audioEl.pause();
  });
}

/* ------------------------------------------------------------------ */
/* go                                                                  */
/* ------------------------------------------------------------------ */
window.addEventListener("DOMContentLoaded", () => {
  bindGate();
  bindInput();
  bindMic();
  runBoot();
});
