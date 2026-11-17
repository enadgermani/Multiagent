# Modulo 6 · L'orchestratore con LangGraph (30 min)

**Concetto:** un grafo di stato. Stato condiviso, nodi che lo modificano, archi fissi e condizionali.
L'ordine dei passi lo decide il codice, non un LLM.
**Costruiamo:** `app/graph.py` (prima versione).
**Prerequisiti:** moduli 1–5.

## 6.1 Le tre idee

- **Stato**: un `TypedDict` condiviso da tutti i passi.
- **Nodo**: una funzione `stato -> dict` che restituisce **solo le chiavi che cambia**.
- **Arco**: fisso (`add_edge`) o condizionale (`add_conditional_edges`: una funzione sceglie il nodo successivo).

## 6.2 Il codice

`app/graph.py`

```python
"""ORCHESTRATORE: un grafo LangGraph che coordina i subagenti.

    START → formatter → validate ─┬─ errore (max 3 tentativi) → formatter
                                  └─ ok → settings → tts → END
"""

from pathlib import Path
from typing import TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

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
            return "settings"
        return "formatter" if state["attempts"] < MAX_ATTEMPTS else END

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
    g.add_node("settings", settings_node)
    g.add_node("tts", tts_node)

    g.add_edge(START, "formatter")
    g.add_edge("formatter", "validate")
    g.add_conditional_edges("validate", after_validate, ["formatter", "settings", END])
    g.add_edge("settings", "tts")
    g.add_edge("tts", END)
    return g.compile(checkpointer=checkpointer)
```

Tre responsabilità separate nel ciclo di correzione: il **formatter** genera (LLM), **validate** giudica
(codice), **after_validate** decide dove andare (codice). Al secondo giro il formatter trova nello stato
`raw` ed `error` e li passa a `build_messages`: è l'auto-correzione del modulo 3, ora automatica.

`tts_node` riceve anche `config`: da lì legge il `thread_id`, che usiamo come nome dei file audio.

## Verifica

Salvate questo file come `prove/m06_grafo.py`:

```python
from app.config import get_settings
from app.graph import build_graph
graph = build_graph(get_settings())
print(graph.get_graph().draw_mermaid())
result = graph.invoke({'text': 'Marco: Ciao Giulia\nGiulia: Ciao Marco!', 'options': {'speed': 1.1}},
                      {'configurable': {'thread_id': 'prova'}})
print('tentativi:', result['attempts'])
```

ed eseguitelo dalla cartella del progetto:

```bash
uv run python -m prove.m06_grafo
```

`draw_mermaid()` descrive il grafo in sintassi Mermaid: incollatela su [mermaid.live](https://mermaid.live)
per vederlo disegnato (nel modulo 8 lo farà la pagina web). L'audio è in `output/prova.mp3`.

Esercizio: alzate la temperatura a 1.4 (`'temperature': 1.4` nell'input) finché `attempts` non supera 1.

> **Cosa guardare su LangSmith:** una sola trace `LangGraph` con dentro i nodi in ordine. Se c'è stata
> una correzione vedete `formatter → validate → formatter → validate`, e nel secondo `formatter` i
> messaggi con l'errore.
