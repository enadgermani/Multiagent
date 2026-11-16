// Frontend volutamente "vanilla": nessun build step, si legge tutto in un file.
// Il frontend non sa nulla di agenti: parla con due endpoint e mostra lo stato.
"use strict";

const $ = (id) => document.getElementById(id);
const state = { config: null, jobId: null, script: null };

// ------------------------------------------------------------------ utilità
async function api(path, body) {
  const res = await fetch(path, body ? {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  } : undefined);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = data.detail;
    const msg = typeof d === "string" ? d : d?.message
      ? `${d.message}: ${d.error ?? ""}` : JSON.stringify(d ?? data);
    if (d?.trace) renderTrace(d.trace);
    throw new Error(msg);
  }
  return data;
}

function toast(msg) {
  const t = $("toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.add("hidden"), 7000);
}

async function busy(btn, label, fn) {
  const old = btn.textContent;
  btn.disabled = true; btn.textContent = label;
  try { await fn(); } catch (e) { toast(e.message); } finally { btn.disabled = false; btn.textContent = old; }
}

const show = (...ids) => ids.forEach((id) => $(id).classList.remove("hidden"));
function el(tag, props = {}, ...kids) {
  const n = Object.assign(document.createElement(tag), props);
  n.append(...kids);
  return n;
}

// ------------------------------------------------------------------ avvio
async function init() {
  const c = await api("/api/config");
  state.config = c;
  $("status").textContent = `Formatter: ${c.formatter} · TTS: ${c.tts_model}` +
    (c.tts_backend === "fake" ? " (finto)" : "") + (c.gemini_key ? "" : " · ⚠ GEMINI_API_KEY mancante");
}

$("raw").addEventListener("input", () => { $("count").textContent = `${$("raw").value.length} caratteri`; });
$("speed").addEventListener("input", () => { $("speed-val").textContent = `${(+$("speed").value).toFixed(2)}×`; });
$("pitch").addEventListener("input", () => { $("pitch-val").textContent = `${(+$("pitch").value)} semitoni`; });

// ------------------------------------------------------------------ 1 → 2
$("btn-format").addEventListener("click", () => busy($("btn-format"), "Il formatter sta lavorando…", async () => {
  const text = $("raw").value.trim();
  if (!text) throw new Error("Incolla prima un testo.");
  const speakers = $("speakers").value.split(",").map((s) => s.trim()).filter(Boolean);
  const r = await api("/api/format", { text, mode_hint: $("mode").value, speakers });
  state.jobId = r.job_id;
  state.script = r.script;
  renderScript();
  renderTrace(r.trace);
  show("step-review", "step-settings", "step-trace");
  $("step-review").scrollIntoView({ behavior: "smooth" });
}));

// ------------------------------------------------------------------ revisione
function renderScript() {
  const s = state.script;
  $("notes").textContent = s.notes || "";
  const box = $("turns");
  box.innerHTML = "";
  const speakersInput = el("input", { type: "text", value: s.speakers.join(", "), id: "speaker-list" });
  speakersInput.addEventListener("change", () => {
    collectScript();
    const names = speakersInput.value.split(",").map((x) => x.trim()).filter(Boolean);
    if (names.length) state.script.speakers = [...new Set(names)];
    renderScript();
  });
  box.append(el("label", {}, "Parlanti (modificabili, separati da virgola)", speakersInput));
  s.turns.forEach((t, i) => box.append(turnEl(t, i)));
  renderVoicePickers();
}

function turnEl(t, i) {
  const sel = el("select", { className: "t-speaker", title: "Parlante" });
  for (const sp of state.script.speakers) sel.append(el("option", { value: sp, textContent: sp, selected: sp === t.speaker }));
  const style = el("input", { type: "text", className: "t-style", value: t.style || "", placeholder: "stile (inglese)" });
  const del = el("button", { className: "icon ghost", textContent: "✕", title: "Elimina battuta" });
  del.addEventListener("click", () => { collectScript(); state.script.turns.splice(i, 1); renderScript(); });
  const text = el("textarea", { className: "t-text", value: t.text, rows: 3 });
  return el("div", { className: "turn" }, el("div", { className: "turn-head" }, sel, style, del), text);
}

$("btn-add-turn").addEventListener("click", () => {
  collectScript();
  state.script.turns.push({ speaker: state.script.speakers[0], text: "", style: "" });
  renderScript();
});

function collectScript() {
  const turns = [...document.querySelectorAll(".turn")].map((n) => ({
    speaker: n.querySelector(".t-speaker").value,
    text: n.querySelector(".t-text").value,
    style: n.querySelector(".t-style").value,
  }));
  state.script.turns = turns;
  return state.script;
}

function renderVoicePickers() {
  const box = $("voice-pickers");
  const prev = Object.fromEntries([...box.querySelectorAll("select")].map((s) => [s.dataset.speaker, s.value]));
  box.innerHTML = "";
  for (const sp of state.script.speakers) {
    const sel = el("select", {});
    sel.dataset.speaker = sp;
    sel.append(el("option", { value: "auto", textContent: "Automatica" }));
    for (const [name, info] of Object.entries(state.config.voices)) {
      sel.append(el("option", { value: name, textContent: `${name} · ${info.tone}` }));
    }
    sel.value = prev[sp] || "auto";
    box.append(el("label", {}, `Voce di ${sp}`, sel));
  }
}

// ------------------------------------------------------------------ 3 → 4
$("btn-synth").addEventListener("click", () => busy($("btn-synth"), "Sintesi in corso…", async () => {
  const s = collectScript();
  const turns = s.turns.filter((t) => t.text.trim());
  if (!turns.length) throw new Error("Il copione è vuoto.");
  const used = [...new Set(turns.map((t) => t.speaker))];
  const script = { ...s, turns, speakers: used, mode: used.length > 1 ? "multi" : "single" };
  const voices = Object.fromEntries([...$("voice-pickers").querySelectorAll("select")]
    .map((x) => [x.dataset.speaker, x.value]));
  const options = {
    voices, speed: +$("speed").value, pitch: +$("pitch").value,
    speed_method: $("speed-method").value, global_style: $("global-style").value,
  };
  const r = await api(`/api/jobs/${state.jobId}/synthesize`, { script, options });
  state.jobId = r.job_id;  // può cambiare se è una rigenerazione (fork)
  const bust = `?t=${Date.now()}`;
  $("player").src = r.wav + bust;
  $("dl-mp3").href = r.mp3; $("dl-wav").href = r.wav;
  $("explain").innerHTML = "";
  r.plan.explanation.forEach((e) => $("explain").append(el("li", { textContent: e })));
  $("explain").append(el("li", { textContent: `Durata: ${r.duration_s}s · voci: ` +
    Object.entries(r.plan.voices).map(([k, v]) => `${k}→${v}`).join(", ") }));
  $("payload").textContent = JSON.stringify(r.first_request, null, 2);
  renderTrace(r.trace);
  show("step-result");
  $("step-result").scrollIntoView({ behavior: "smooth" });
  $("player").play().catch(() => {});
}));

// ------------------------------------------------------------------ trace
const LABELS = {
  formatter: "Subagente formatter (LLM)", validate: "Validazione schema (codice)",
  human_review: "Revisione umana", settings: "Subagente settings (codice)",
  synthesize: "Tool Gemini TTS", postprocess: "Tool ffmpeg", fork: "Fork del lavoro (nessuna nuova chiamata LLM)",
};

function renderTrace(trace) {
  const ol = $("trace");
  ol.innerHTML = "";
  for (const { agent, ms, ...rest } of trace) {
    const detail = Object.keys(rest).length ? JSON.stringify(rest) : "";
    ol.append(el("li", {},
      el("span", { className: "tag", textContent: `${ms} ms` }),
      el("strong", { textContent: LABELS[agent] || agent }), " ",
      el("code", { textContent: detail })));
  }
  show("step-trace");
}

init().catch((e) => toast("Server non raggiungibile: " + e.message));
