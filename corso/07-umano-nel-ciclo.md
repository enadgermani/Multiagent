# Modulo 7 · Una persona nel ciclo: interrupt, checkpoint, time travel (25 min)

**Concetto:** il grafo si **ferma** a metà, salva lo stato, e **riparte** più tardi, anche da un altro
processo o un'altra richiesta HTTP. Poi: tornare indietro a un punto salvato.
**Costruiamo:** `app/graph.py` (seconda versione: nodo `human_review`).
**Prerequisiti:** modulo 6.

## 7.1 Perché

Prima di spendere crediti TTS, una persona deve vedere il copione. Ma una richiesta HTTP non può restare
aperta mentre l'utente legge: il grafo deve fermarsi, salvare lo stato, e riprendere quando arriva la risposta.

## 7.2 Le modifiche a `app/graph.py`

1. `from langgraph.types import interrupt`
2. un nuovo nodo:

```python
    def human_review_node(state: State) -> dict:
        # interrupt() salva lo stato e restituisce il controllo a chi ha chiamato il grafo.
        # Il grafo riparte da qui quando arriva Command(resume=...): il valore
        # passato nel resume è ciò che interrupt() restituisce.
        answer = interrupt(state["script"])
        if not isinstance(answer, dict):  # risposta vuota = approvo così com'è
            answer = {}
        script = Script.model_validate(answer.get("script", state["script"]))
        options = VoiceOptions.model_validate(answer.get("options", {}))
        return {"script": script.model_dump(), "options": options.model_dump()}
```

3. `after_validate` restituisce `"human_review"` invece di `"settings"`;
4. il nodo entra nel grafo:

```python
    g.add_node("human_review", human_review_node)
    ...
    g.add_conditional_edges("validate", after_validate, ["formatter", "human_review", END])
    g.add_edge("human_review", "settings")
```

<details><summary>Il file completo dopo le modifiche</summary>

`app/graph.py`

```python
"""ORCHESTRATORE: un grafo LangGraph che coordina i subagenti.

    START → formatter → validate ─┬─ errore (max 3 tentativi) → formatter
                                  └─ ok → human_review ⏸ → settings → tts → END
"""

from pathlib import Path
from typing import TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from . import formatter, settings_agent, tts
from .config import Settings
from .llm import formatter_model
from .schemas import Script, VoiceOptions

MAX_ATTEMPTS = 3


class State(TypedDict, total=False):
    text: str          # input dell'utente
    temperature: float # temperatura del formatter
    raw: str           # risposta grezza del formatter
    error: str | None  # errore di validazione (None = ok)
    attempts: int
    script: dict       # copione validato (Script)
    options: dict      # voci, velocità, pitch (VoiceOptions)
    request: dict      # richiesta per Gemini


def build_graph(s: Settings, checkpointer=None):
    out_dir = Path(s.output_dir)
    out_dir.mkdir(exist_ok=True)

    def formatter_node(state: State) -> dict:
        messages = formatter.build_messages(state["text"], state.get("raw"), state.get("error"))
        response = formatter_model(s, state.get("temperature", 0.2)).invoke(messages)
        return {"raw": response.content}

    def validate_node(state: State) -> dict:
        attempts = state.get("attempts", 0) + 1
        try:
            script = formatter.parse_script(state["raw"])
        except ValueError as e:
            return {"error": str(e), "attempts": attempts}
        return {"script": script.model_dump(), "error": None, "attempts": attempts}

    def after_validate(state: State) -> str:
        if state["error"] is None:
            return "human_review"
        return "formatter" if state["attempts"] < MAX_ATTEMPTS else END

    def human_review_node(state: State) -> dict:
        # interrupt() salva lo stato e restituisce il controllo a chi ha chiamato il grafo.
        # Il grafo riparte da qui quando arriva Command(resume=...): il valore
        # passato nel resume è ciò che interrupt() restituisce.
        answer = interrupt(state["script"])
        if not isinstance(answer, dict):  # risposta vuota = approvo così com'è
            answer = {}
        script = Script.model_validate(answer.get("script", state["script"]))
        options = VoiceOptions.model_validate(answer.get("options", {}))
        return {"script": script.model_dump(), "options": options.model_dump()}

    def settings_node(state: State) -> dict:
        request = settings_agent.build_tts_request(
            Script.model_validate(state["script"]), VoiceOptions.model_validate(state.get("options", {})), s.tts_model)
        return {"request": request}

    def tts_node(state: State, config: RunnableConfig) -> dict:
        wav = tts.synthesize(s.gemini_api_key.get_secret_value(), state["request"])
        opts = VoiceOptions.model_validate(state.get("options", {}))
        filters = tts.audio_filter(opts.speed, opts.pitch)
        job_id = config["configurable"]["thread_id"]
        for fmt in ("wav", "mp3"):
            (out_dir / f"{job_id}.{fmt}").write_bytes(tts.ffmpeg(wav, filters, fmt))
        return {}

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
    return g.compile(checkpointer=checkpointer)
```

</details>

## 7.3 Il ciclo di vita

```python
cfg = {"configurable": {"thread_id": job_id}}            # un thread = un lavoro
graph.invoke({"text": testo}, cfg)                        # gira fino all'interrupt
graph.get_state(cfg).next                                 # ('human_review',)
# ...più tardi, anche da un'altra richiesta:
graph.invoke(Command(resume={"script": ..., "options": ...}), cfg)
```

Da ricordare:

- serve un **checkpointer** (`InMemorySaver`, o `SqliteSaver` per sopravvivere ai riavvii): senza, l'interrupt non ha dove salvare lo stato;
- il valore di `Command(resume=...)` è ciò che `interrupt()` restituisce;
- alla ripresa il nodo riparte dall'inizio: il codice prima di `interrupt()` viene rieseguito, quindi va tenuto leggero;
- il copione torna dall'utente: lo validiamo di nuovo.

## 7.4 Time travel: rigenerare senza richiamare il modello

Il grafo è arrivato alla fine, ma l'utente vuole un'altra voce. Il checkpointer conserva la storia, quindi
possiamo **riprendere da un punto precedente**:

```python
graph.update_state(cfg, {"error": None}, as_node="validate")   # nuovo checkpoint, "come se" l'avesse scritto validate
graph.invoke(None, cfg)                                         # segue validate -> human_review, si ferma
graph.invoke(Command(resume={"options": {"voices": {"Marco": "Puck"}}}), cfg)
```

Il copione già validato resta nello stato: il formatter non viene richiamato.

## Verifica

Salvate questo file come `prove/m07_revisione.py`:

```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from app.config import get_settings
from app.graph import build_graph
graph = build_graph(get_settings(), checkpointer=InMemorySaver())
cfg = {'configurable': {'thread_id': 'prova'}}
graph.invoke({'text': 'Marco: Ciao Giulia\nGiulia: Bene!'}, cfg)
state = graph.get_state(cfg)
print(state.next, state.values['script'])
script = state.values['script']
script['turns'][0]['text'] = 'Ciao GIULIA, tutto bene?'
graph.invoke(Command(resume={'script': script, 'options': {'pitch': -2}}), cfg)
print('finito:', graph.get_state(cfg).next == ())
graph.update_state(cfg, {'error': None}, as_node='validate')
graph.invoke(None, cfg)
graph.invoke(Command(resume={'options': {'voices': {'Marco': 'Puck'}}}), cfg)
print(graph.get_state(cfg).values['request']['generation_config'])
```

ed eseguitelo dalla cartella del progetto:

```bash
uv run python -m prove.m07_revisione
```

> **Cosa guardare su LangSmith:** tre trace separate per lo stesso `thread_id` (fino all'interrupt, la
> ripresa, la rigenerazione). Nella terza non c'è nessuna chiamata al modello.
