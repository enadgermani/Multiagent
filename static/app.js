// Il frontend non sa nulla di agenti: chiama gli endpoint e mostra i risultati.
// La colonna "Dietro le quinte" mostra il grafo e il JSON passato tra i nodi.
// Mermaid (la libreria che disegna il grafo) arriva da una CDN: se manca internet
// l'app funziona lo stesso, solo senza disegno.
const MERMAID_URL = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.esm.min.mjs";

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
let jobId, script, voices, graphText, mermaid;
let graphState = { visited: [], current: null };

async function post(url, body) {
  const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const text = await res.text();
  // Gli errori FastAPI sono JSON {"detail": ...}; un crash del server può restituire testo semplice.
  let data;
  try { data = JSON.parse(text); } catch { data = { detail: text }; }
  if (!res.ok) {
    if (data.steps) showInternals(data);  // anche in caso di errore: si vede cosa è andato storto
    throw new Error(`Errore ${res.status}: ${typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)}`);
  }
  return data;
}

async function run(button, fn) {
  button.disabled = true;
  try { await fn(); } catch (e) { alert(e.message); } finally { button.disabled = false; }
}

$("temperature").oninput = () => ($("temp-out").textContent = $("temperature").value);
$("speed").oninput = () => ($("speed-out").textContent = $("speed").value);
$("pitch").oninput = () => ($("pitch-out").textContent = $("pitch").value);

// ------------------------------------------------------------------ dietro le quinte
const LABELS = {
  formatter: "Subagente LLM: prompt inviato e risposta grezza",
  validate: "Codice: controllo dello schema",
  human_review: "Tu: copione approvato e impostazioni",
  settings: "Subagente deterministico: richiesta JSON per Gemini",
  tts: "Strumenti: Gemini TTS e ffmpeg",
};

async function drawGraph() {
  if (!mermaid) return;
  const { visited, current } = graphState;
  graphText ??= (await (await fetch("/api/graph")).json()).mermaid;
  let text = graphText +
    "\n\tclassDef visited fill:#c8efd0,stroke:#2e7d32,color:#000;" +
    "\n\tclassDef current fill:#ffe08a,stroke:#b8860b,stroke-width:3px,color:#000;";
  const done = [...new Set(visited)].filter((n) => n !== current);
  if (done.length) text += `\n\tclass ${done.join(",")} visited;`;
  if (current) text += `\n\tclass ${current} current;`;
  const { svg } = await mermaid.render(`g${Date.now()}`, text);
  $("graph").innerHTML = svg;
}

// Il passo del formatter è il più istruttivo: mostriamo i messaggi come testo leggibile.
function formatterStep({ input, output }) {
  const messages = input.messages.map((m) => `<p class="role">${esc(m.role)}</p><pre>${esc(m.content)}</pre>`).join("");
  return `<p class="role">modelli: ${esc(input.models)} · temperatura ${input.temperature}` +
    (output.answered_by ? ` · ha risposto: ${esc(output.answered_by)}` : "") + `</p>` +
    messages + `<p class="role">risposta grezza del modello</p><pre>${esc(output.raw)}</pre>`;
}

function showInternals({ steps, next }) {
  graphState = { visited: steps.map((s) => s.node), current: next[0] || null };
  drawGraph();
  $("steps-empty").hidden = true;
  $("steps").innerHTML = steps.map((s, i) => `
    <details ${i === steps.length - 1 ? "open" : ""}>
      <summary>${i + 1}. <b>${esc(s.node)}</b> · ${esc(LABELS[s.node] || "")}</summary>
      ${s.node === "formatter" ? formatterStep(s) : `<pre>${esc(JSON.stringify(s.output, null, 2))}</pre>`}
    </details>`).join("");
}

import(MERMAID_URL)
  .then((m) => {
    mermaid = m.default;
    mermaid.initialize({ startOnLoad: false, theme: matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "default" });
    drawGraph();
  })
  .catch(() => ($("graph").textContent = "Disegno del grafo non disponibile: Mermaid si carica da internet."));

// ------------------------------------------------------------------ 1 → 2
// Il formatter prepara il copione, poi il grafo si ferma per la revisione.
$("format").onclick = () => run($("format"), async () => {
  voices ??= await (await fetch("/api/voices")).json();
  const data = await post("/api/format", { text: $("text").value, temperature: +$("temperature").value });
  ({ job_id: jobId, script } = data);
  showInternals(data);

  $("turns").innerHTML = script.turns.map((t, i) => `
    <div class="turn"><b>${esc(t.speaker)}</b> <small>${esc(t.style)}</small>
    <textarea data-i="${i}" rows="3">${esc(t.text)}</textarea></div>`).join("");

  const options = Object.entries(voices).map(([name, tone]) => `<option value="${name}">${name} · ${tone}</option>`).join("");
  $("voices").innerHTML = script.speakers.map((sp) => `
    <label>Voce di ${esc(sp)} <select data-speaker="${esc(sp)}">${options}</select></label>`).join("");
  document.querySelectorAll("#voices select").forEach((s, i) => (s.value = ["Charon", "Aoede"][i]));

  $("review").hidden = $("settings").hidden = false;
  $("result").hidden = true;
});

// ------------------------------------------------------------------ 3 → 4
// Il grafo riprende con il copione rivisto e le impostazioni.
$("synthesize").onclick = () => run($("synthesize"), async () => {
  document.querySelectorAll("#turns textarea").forEach((ta) => (script.turns[ta.dataset.i].text = ta.value));
  const chosen = Object.fromEntries([...document.querySelectorAll("#voices select")].map((s) => [s.dataset.speaker, s.value]));
  const options = { voices: chosen, speed: +$("speed").value, pitch: +$("pitch").value };

  const data = await post(`/api/synthesize/${jobId}`, { script, options });
  showInternals(data);
  $("player").src = data.wav;
  $("download").href = data.mp3;
  $("result").hidden = false;
});
