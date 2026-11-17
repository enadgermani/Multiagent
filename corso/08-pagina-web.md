# Modulo 8 · La pagina web e la vista "Dietro le quinte" (25 min)

**Concetto:** un'API in due chiamate attorno a un grafo che si ferma, e una pagina che mostra non solo il
risultato ma **cosa è passato tra gli agenti**.
**Costruiamo:** `app/graph.py` (versione finale, con `steps`), `app/main.py`, `static/`.
**Prerequisiti:** modulo 7.

## 8.1 Ogni nodo lascia una traccia: `steps` e i reducer

Aggiungiamo allo stato una lista in cui ogni nodo scrive ciò che ha ricevuto e prodotto:

```python
    steps: Annotated[list[dict], operator.add]
```

`operator.add` è un **reducer**: dice a LangGraph come combinare il valore nuovo con il vecchio. Senza,
ogni nodo sovrascriverebbe la lista; con, ogni nodo **aggiunge** la sua voce. Il formatter registra anche
il prompt completo e quale modello ha risposto davvero (`response_metadata`, utile con il fallback).

`app/graph.py`

```python
"""ORCHESTRATORE: un grafo LangGraph che coordina i subagenti.

    START → formatter → validate ─┬─ errore (max 3 tentativi) → formatter
                                  └─ ok → human_review ⏸ → settings → tts → END

- formatter     subagente LLM (Qwen locale / DeepSeek)
- validate      codice: controlla l'output del formatter con lo schema Pydantic
- human_review  il grafo si FERMA (interrupt) finché l'utente non approva il copione
- settings      subagente deterministico: costruisce la richiesta per Gemini
- tts           strumenti: Gemini TTS, poi ffmpeg per velocità, pitch e MP3

L'ordine dei passi è sempre lo stesso, quindi lo decide il codice (un grafo),
non un LLM.

Ogni nodo aggiunge una voce a `steps` con ciò che ha ricevuto e prodotto:
la pagina web la mostra, così si vede cosa passa da un agente all'altro.
"""

import operator
from pathlib import Path
from typing import Annotated, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from . import formatter, settings_agent, tts
from .config import Settings
from .llm import describe, formatter_model
from .schemas import Script, VoiceOptions

MAX_ATTEMPTS = 3


class State(TypedDict, total=False):
    text: str          # input dell'utente
    temperature: float # temperatura del formatter, scelta nell'interfaccia
    raw: str           # risposta grezza del formatter
    error: str | None  # errore di validazione (None = ok)
    attempts: int
    script: dict       # copione validato (Script)
    options: dict      # scelte dell'utente (VoiceOptions)
    request: dict      # richiesta per Gemini
    # operator.add è un "reducer": ogni nodo AGGIUNGE la sua voce invece di sostituire la lista
    steps: Annotated[list[dict], operator.add]


def build_graph(s: Settings, checkpointer=None):
    out_dir = Path(s.output_dir)
    out_dir.mkdir(exist_ok=True)

    def formatter_node(state: State) -> dict:
        messages = formatter.build_messages(state["text"], state.get("raw"), state.get("error"))
        # Il modello si crea a ogni chiamata (è economico) con la temperatura scelta dall'utente.
        temperature = state.get("temperature", 0.2)
        response = formatter_model(s, temperature).invoke(messages)
        meta = response.response_metadata  # chi ha risposto davvero (utile col fallback)
        step = {"node": "formatter",
                "input": {"models": describe(s), "temperature": temperature,
                          "messages": [{"role": m.type, "content": m.content} for m in messages]},
                "output": {"answered_by": meta.get("model_name") or meta.get("model"), "raw": response.content}}
        return {"raw": response.content, "steps": [step]}

    def validate_node(state: State) -> dict:
        attempts = state.get("attempts", 0) + 1
        try:
            script = formatter.parse_script(state["raw"])
        except ValueError as e:
            step = {"node": "validate", "output": {"ok": False, "attempt": attempts, "error": str(e)}}
            return {"error": str(e), "attempts": attempts, "steps": [step]}
        step = {"node": "validate", "output": {"ok": True, "attempt": attempts, "script": script.model_dump()}}
        return {"script": script.model_dump(), "error": None, "attempts": attempts, "steps": [step]}

    def after_validate(state: State) -> str:
        if state["error"] is None:
            return "human_review"
        return "formatter" if state["attempts"] < MAX_ATTEMPTS else END

    def human_review_node(state: State) -> dict:
        # interrupt() salva lo stato e restituisce il controllo all'API web.
        # Il grafo riparte da qui quando arriva Command(resume=...): il valore
        # passato nel resume è ciò che interrupt() restituisce.
        answer = interrupt(state["script"])
        # Risposta vuota (es. Resume in Studio) = approvo il copione così com'è, opzioni di default.
        # Ogni chiave mancante prende il valore attuale: {"options": {...}} cambia solo la voce.
        if not isinstance(answer, dict):
            answer = {}
        script = Script.model_validate(answer.get("script", state["script"]))
        options = VoiceOptions.model_validate(answer.get("options", {}))
        step = {"node": "human_review", "output": {"script": script.model_dump(), "options": options.model_dump()}}
        return {"script": script.model_dump(), "options": options.model_dump(), "steps": [step]}

    def settings_node(state: State) -> dict:
        request = settings_agent.build_tts_request(
            Script.model_validate(state["script"]), VoiceOptions.model_validate(state["options"]), s.tts_model)
        return {"request": request, "steps": [{"node": "settings", "output": {"gemini_request": request}}]}

    def tts_node(state: State, config: RunnableConfig) -> dict:
        wav = tts.synthesize(s.gemini_api_key.get_secret_value(), state["request"])
        opts = state["options"]
        filters = tts.audio_filter(opts["speed"], opts["pitch"])
        job_id = config["configurable"]["thread_id"]
        files = []
        for fmt in ("wav", "mp3"):
            path = out_dir / f"{job_id}.{fmt}"
            path.write_bytes(tts.ffmpeg(wav, filters, fmt))
            files.append(path.name)
        step = {"node": "tts", "output": {"gemini_wav_bytes": len(wav), "ffmpeg_filter": filters, "files": files}}
        return {"steps": [step]}

    g = StateGraph(State)
    g.add_node("formatter", formatter_node)
    g.add_node("validate", validate_node)
    g.add_node("human_review", human_review_node)
    g.add_node("settings", settings_node)
    g.add_node("tts", tts_node)

    g.add_edge(START, "formatter")
    g.add_edge("formatter", "validate")
    g.add_conditional_edges("validate", after_validate, ["formatter", "human_review", END])
    g.add_edge("human_review", "settings")
    g.add_edge("settings", "tts")
    g.add_edge("tts", END)

    # Il checkpointer salva lo stato di ogni lavoro (thread_id): senza, l'interrupt non funziona.
    # L'API web passa InMemorySaver(); LangGraph Studio usa il proprio (vedi app/studio.py).
    return g.compile(checkpointer=checkpointer)
```

## 8.2 L'API

```
POST /api/format              → nuovo job_id, il grafo gira fino a human_review → copione + passi
POST /api/synthesize/{job_id} → il grafo riprende (o torna indietro e riprende) → audio + passi
GET  /api/audio/{job_id}.mp3  → il file
GET  /api/graph               → il grafo in Mermaid, generato da LangGraph
```

`app/main.py`

```python
"""API web. Due chiamate, perché in mezzo c'è la revisione dell'utente:

  POST /api/format              → il grafo gira fino a human_review e si ferma
  POST /api/synthesize/{job_id} → il grafo riprende e genera l'audio
"""

import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from pydantic import BaseModel, Field

from .config import get_settings
from .graph import build_graph
from .schemas import VOICES, Script, VoiceOptions

settings = get_settings()
graph = build_graph(settings, checkpointer=InMemorySaver())
app = FastAPI(title="Voce Agenti")


class FormatRequest(BaseModel):
    text: str
    temperature: float = Field(default=0.2, ge=0, le=1.5)


class SynthesizeRequest(BaseModel):
    script: Script
    options: VoiceOptions


def job_config(job_id: str, run_name: str | None = None) -> dict:
    # run_name e metadata servono a LangSmith: nome leggibile della trace e
    # raggruppamento per thread_id (formatta + genera audio dello stesso lavoro).
    return {"configurable": {"thread_id": job_id}, "run_name": run_name, "metadata": {"thread_id": job_id}}


def view(job_id: str) -> dict:
    """Ciò che la pagina mostra: dove si trova il grafo e cosa ha fatto ogni nodo."""
    state = graph.get_state(job_config(job_id))
    return {"job_id": job_id, "next": list(state.next), "steps": state.values.get("steps", [])}


@app.get("/api/graph")
def graph_diagram():
    # Il diagramma Mermaid è generato da LangGraph a partire dal grafo vero.
    return {"mermaid": graph.get_graph().draw_mermaid()}


@app.get("/api/voices")
def voices():
    return VOICES


@app.post("/api/format")
def format_text(req: FormatRequest):
    job_id = uuid.uuid4().hex
    try:
        graph.invoke({"text": req.text, "temperature": req.temperature}, job_config(job_id, "formatta"))
    except Exception as e:  # es. Ollama spento e nessun fallback
        raise HTTPException(502, f"Errore del formatter: {type(e).__name__}: {e}")
    state = graph.get_state(job_config(job_id))
    if state.next != ("human_review",):
        # Restituiamo comunque i passi: si vede quali risposte del formatter sono state scartate.
        return JSONResponse(status_code=422, content={
            "detail": f"Il formatter non ha prodotto un copione valido: {state.values['error']}", **view(job_id)})
    return {"script": state.values["script"], **view(job_id)}


@app.post("/api/synthesize/{job_id}")
def synthesize(job_id: str, req: SynthesizeRequest):
    state = graph.get_state(job_config(job_id))
    if state.next != ("human_review",):
        if "script" not in state.values:
            raise HTTPException(404, "Lavoro sconosciuto (il server è stato riavviato?): formatta di nuovo il testo.")
        rewind_to_review(job_id)
    try:
        graph.invoke(Command(resume=req.model_dump()), job_config(job_id, "genera_audio"))
    except Exception as e:  # es. chiave Gemini errata, ffmpeg mancante
        raise HTTPException(502, f"Errore durante la sintesi: {type(e).__name__}: {e}")
    return {"wav": f"/api/audio/{job_id}.wav", "mp3": f"/api/audio/{job_id}.mp3", **view(job_id)}


def rewind_to_review(job_id: str) -> None:
    """Riporta il lavoro alla revisione, per rigenerare l'audio senza richiamare il modello.

    update_state(..., as_node="validate") scrive un nuovo checkpoint COME SE l'avesse
    prodotto il nodo validate: il grafo segue l'arco validate -> human_review, e
    invoke(None) lo fa ripartire fino all'interrupt. Il copione resta quello già validato.
    """
    step = {"node": "rewind", "output": {"note": "ripartito da validate con il copione già pronto: nessuna nuova chiamata al modello"}}
    graph.update_state(job_config(job_id), {"error": None, "steps": [step]}, as_node="validate")
    graph.invoke(None, job_config(job_id))


@app.get("/api/audio/{job_id}.{fmt}")
def audio(job_id: str, fmt: str):
    try:
        job_id = uuid.UUID(job_id).hex  # accetta solo UUID: niente path traversal
    except ValueError:
        raise HTTPException(404)
    path = Path(settings.output_dir) / f"{job_id}.{fmt}"
    if fmt not in ("wav", "mp3") or not path.exists():
        raise HTTPException(404)
    return FileResponse(path, filename=f"voce.{fmt}")


app.mount("/", StaticFiles(directory=Path(__file__).parent.parent / "static", html=True))
```

- Endpoint `def`, non `async def`: il grafo è bloccante e FastAPI lo esegue in un thread separato.
- `job_id` diventa il `thread_id` del grafo: così la seconda chiamata ritrova il lavoro.
- `run_name` e `metadata` servono a LangSmith: trace con un nome leggibile, raggruppate per lavoro.
- `rewind_to_review` è il time travel del modulo 7, usato quando si rigenera l'audio.
- `uuid.UUID(job_id)` prima di usarlo come nome di file: niente percorsi come `../../`.

## 8.3 La pagina

Due colonne: a sinistra l'app (testo, revisione, voci, audio), a destra "Dietro le quinte" (il grafo con i
nodi eseguiti in verde e quello in attesa in giallo, poi i passi con il loro JSON). Il frontend non sa
nulla di agenti: chiama le API e mostra ciò che riceve.

`static/index.html`

```html
<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Voce Agenti</title>
  <link rel="stylesheet" href="style.css?v=4">
</head>
<body>
<h1>Voce Agenti</h1>
<div class="layout">

  <!-- Colonna sinistra: l'app -->
  <main>
    <section>
      <h2>1. Testo</h2>
      <textarea id="text" rows="8" placeholder="Incolla il testo. Per un dialogo: &quot;Marco: ciao&quot;"></textarea>
      <label>Temperatura del formatter <output id="temp-out">0.2</output>
        <input id="temperature" type="range" min="0" max="1.5" step="0.1" value="0.2"></label>
      <button id="format">Formatta</button>
    </section>

    <section id="review" hidden>
      <h2>2. Rivedi il copione</h2>
      <div id="turns"></div>
    </section>

    <section id="settings" hidden>
      <h2>3. Voce</h2>
      <div id="voices"></div>
      <label>Velocità <output id="speed-out">1</output>×
        <input id="speed" type="range" min="0.5" max="2" step="0.05" value="1"></label>
      <label>Pitch <output id="pitch-out">0</output> semitoni
        <input id="pitch" type="range" min="-6" max="6" step="0.5" value="0"></label>
      <button id="synthesize">Genera audio</button>
    </section>

    <section id="result" hidden>
      <h2>4. Ascolta</h2>
      <audio id="player" controls></audio>
      <a id="download" download>Scarica MP3</a>
    </section>
  </main>

  <!-- Colonna destra: dietro le quinte -->
  <aside>
    <h2>Dietro le quinte</h2>
    <p class="hint">Il grafo è disegnato da LangGraph. In verde i nodi già eseguiti, in giallo quello in cui il grafo è fermo.</p>
    <div id="graph"></div>
    <h3>Cosa è passato tra gli agenti</h3>
    <p class="hint" id="steps-empty">Premi "Formatta" per vedere il prompt inviato al modello, la sua risposta e i passi successivi.</p>
    <div id="steps"></div>
  </aside>
</div>
<script type="module" src="app.js?v=4"></script>
</body>
</html>
```

`static/style.css`

```css
:root { --bg: #fafaf8; --fg: #1d1d1f; --line: #ddd; --accent: #2f5bd3; --code: #f0efea; color-scheme: light dark; }
@media (prefers-color-scheme: dark) { :root { --bg: #161618; --fg: #eee; --line: #333; --accent: #7c9dff; --code: #222226; } }
* { box-sizing: border-box; }
body { margin: 0 auto; max-width: 1400px; padding: 16px; background: var(--bg); color: var(--fg); font: 16px/1.5 system-ui, sans-serif; }
.layout { display: grid; gap: 24px; }
@media (min-width: 1000px) { .layout { grid-template-columns: 1fr 1fr; } aside { position: sticky; top: 16px; max-height: calc(100vh - 32px); overflow: auto; } }
main, aside { min-width: 0; }
section { border-top: 1px solid var(--line); padding: 12px 0; }
aside { border-top: 1px solid var(--line); padding-top: 12px; }
textarea, select { width: 100%; font: inherit; padding: 8px; border: 1px solid var(--line); border-radius: 6px; background: transparent; color: inherit; }
label { display: block; margin: 12px 0; }
input[type=range] { width: 100%; }
button, a#download { display: inline-block; margin-top: 10px; padding: 10px 20px; border: 0; border-radius: 6px;
  background: var(--accent); color: #fff; font: inherit; cursor: pointer; text-decoration: none; }
button:disabled { opacity: .5; }
.turn { margin-bottom: 10px; }
.turn small, .hint { opacity: .7; }
.hint { font-size: .9rem; }
audio { width: 100%; }
#graph { text-align: center; }
#graph svg { max-width: 100%; height: auto; }
details { border: 1px solid var(--line); border-radius: 6px; margin-bottom: 8px; }
summary { cursor: pointer; padding: 8px 10px; }
summary b { text-transform: uppercase; font-size: .8rem; letter-spacing: .04em; }
pre { margin: 0; padding: 10px; background: var(--code); overflow: auto; font-size: .8rem; white-space: pre-wrap; word-break: break-word; }
.role { margin: 8px 10px 2px; font-size: .8rem; text-transform: uppercase; letter-spacing: .04em; opacity: .7; }
```

`static/app.js`

```javascript
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
  rewind: "Rigenerazione: il grafo torna alla revisione (time travel)",
};

async function drawGraph() {
  if (!mermaid) return;
  const { visited, current } = graphState;
  graphText ??= (await (await fetch("/api/graph")).json()).mermaid;
  let text = graphText +
    "\n\tclassDef visited fill:#c8efd0,stroke:#2e7d32,color:#000;" +
    "\n\tclassDef current fill:#ffe08a,stroke:#b8860b,stroke-width:3px,color:#000;";
  const done = [...new Set(visited)].filter((n) => n !== current && n !== "rewind");
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
  const bust = `?t=${Date.now()}`;  // stesso file, audio nuovo: evitiamo la cache del browser
  $("player").src = data.wav + bust;
  $("download").href = data.mp3;
  $("result").hidden = false;
});
```

Mermaid si carica da una CDN: senza internet la pagina funziona lo stesso, solo senza il disegno.

## Verifica

```bash
uv run uvicorn app.main:app      # → http://127.0.0.1:8000
```

1. Incollate un dialogo e premete **Formatta**: il grafo è fermo su `human_review` (giallo); aprite il passo `formatter` e leggete prompt e risposta grezza.
2. Correggete una battuta, scegliete le voci, premete **Genera audio**: tutti i nodi diventano verdi.
3. Cambiate pitch e premete di nuovo: compare il passo `rewind`, il formatter non viene richiamato.
