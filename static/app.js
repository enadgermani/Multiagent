// Il frontend non sa nulla di agenti: chiama due endpoint e mostra i risultati.
const $ = (id) => document.getElementById(id);
let jobId, script, voices;
const esc = (s) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

async function post(url, body) {
  const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const text = await res.text();
  // Gli errori FastAPI sono JSON {"detail": ...}; un crash del server può restituire testo semplice.
  let data;
  try { data = JSON.parse(text); } catch { data = { detail: text }; }
  if (!res.ok) throw new Error(`Errore ${res.status}: ${typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)}`);
  return data;
}

async function run(button, fn) {
  button.disabled = true;
  try { await fn(); } catch (e) { alert(e.message); } finally { button.disabled = false; }
}

$("speed").oninput = () => ($("speed-out").textContent = $("speed").value);
$("temperature").oninput = () => ($("temp-out").textContent = $("temperature").value);
$("pitch").oninput = () => ($("pitch-out").textContent = $("pitch").value);

// 1 → 2: il formatter prepara il copione, il grafo si ferma per la revisione
$("format").onclick = () => run($("format"), async () => {
  voices ??= await (await fetch("/api/voices")).json();
  ({ job_id: jobId, script } = await post("/api/format", { text: $("text").value, temperature: +$("temperature").value }));

  $("turns").innerHTML = script.turns.map((t, i) => `
    <div class="turn"><b>${esc(t.speaker)}</b> <small>${esc(t.style)}</small>
    <textarea data-i="${i}" rows="3">${esc(t.text)}</textarea></div>`).join("");

  const options = Object.entries(voices).map(([name, tone]) => `<option value="${name}">${name} · ${tone}</option>`).join("");
  $("voices").innerHTML = script.speakers.map((sp, i) => `
    <label>Voce di ${esc(sp)} <select data-speaker="${esc(sp)}">${options}</select></label>`).join("");
  document.querySelectorAll("#voices select").forEach((s, i) => (s.value = ["Charon", "Aoede"][i]));

  $("review").hidden = $("settings").hidden = false;
});

// 3 → 4: il grafo riprende con il copione rivisto e le impostazioni
$("synthesize").onclick = () => run($("synthesize"), async () => {
  document.querySelectorAll("#turns textarea").forEach((ta) => (script.turns[ta.dataset.i].text = ta.value));
  const chosen = Object.fromEntries([...document.querySelectorAll("#voices select")].map((s) => [s.dataset.speaker, s.value]));
  const options = { voices: chosen, speed: +$("speed").value, pitch: +$("pitch").value };

  const audio = await post(`/api/synthesize/${jobId}`, { script, options });
  $("player").src = audio.wav;
  $("download").href = audio.mp3;
  $("result").hidden = false;
});
