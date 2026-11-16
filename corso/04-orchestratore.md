# Modulo 4 · L'orchestratore con LangGraph (50 min)

**Obiettivi:** capire stato, nodi, archi e reducer; costruire un ciclo di auto-correzione con un arco
condizionale; fermare il grafo per la revisione umana e riprenderlo; vedere il "time travel".

**File:** `app/graph.py`, `tests/test_pipeline.py`

## 4.1 Le tre idee di LangGraph (10 min)

1. **Stato**: un `TypedDict` condiviso. Ogni nodo riceve lo stato e restituisce **solo le chiavi che cambia**.
2. **Nodi**: funzioni Python normali (`state -> dict`). Possono chiamare LLM, API, o niente.
3. **Archi**: fissi (`add_edge`) o condizionali (`add_conditional_edges` con una funzione che sceglie il prossimo nodo).

```python
class State(TypedDict, total=False):
    text: str
    raw_output: str
    error: str | None
    attempts: int
    script: dict
    options: dict
    plan: dict
    trace: Annotated[list[dict], operator.add]   # ← reducer
```

Il **reducer** `operator.add` dice: quando un nodo restituisce `trace`, *aggiungi* alla lista invece
di sostituirla. Ogni nodo appende la propria riga di log; alla fine abbiamo la storia completa.
(Lo stesso meccanismo, con `add_messages`, è quello che usano i chatbot per accumulare i messaggi.)

## 4.2 Il ciclo di auto-correzione (15 min, lab)

```python
def validate_node(state):
    attempts = state.get("attempts", 0) + 1
    try:
        script = formatter.parse_script(state["raw_output"])
    except ValueError as e:
        return {"error": str(e), "attempts": attempts, "trace": [...]}
    return {"script": script.model_dump(), "error": None, "attempts": attempts, "trace": [...]}

def route_after_validate(state) -> str:
    if state.get("error") is None:
        return "human_review"
    return "formatter" if state["attempts"] < MAX_FORMAT_ATTEMPTS else END

g.add_edge("formatter", "validate")
g.add_conditional_edges("validate", route_after_validate, ["formatter", "human_review", END])
```

Notate la separazione: il **formatter** genera (LLM), il **validate** giudica (codice), il **router**
decide (codice). Il formatter, al secondo giro, trova nello stato `raw_output` ed `error` e li usa per
costruire i messaggi di correzione.

Testarlo senza GPU, con un LLM finto che sbaglia la prima volta:

```python
model = FakeListChatModel(responses=["non è json", GOOD])
g = build_graph(s, model=model, tts=FakeTTS())
g.invoke({"text": "Ciao a tutti.", "attempts": 0}, cfg)
assert g.get_state(cfg).values["attempts"] == 2
```

Questa è la ragione per cui `build_graph` accetta `model` e `tts` come parametri: **dependency injection**.
Tutto ciò che costa o non è deterministico deve poter essere sostituito nei test.

## 4.3 Human-in-the-loop: interrupt e checkpointer (15 min)

Vogliamo che l'utente veda il copione **prima** di spendere crediti TTS. Ma una richiesta HTTP non
può restare aperta mentre l'utente legge. Serve che il grafo si fermi, salvi lo stato, e riparta
più tardi da un'altra richiesta.

```python
def human_review_node(state):
    decision = interrupt({"script": state["script"]})   # ⏸ si ferma QUI
    script = Script.model_validate(decision["script"])  # ▶ riparte da qui con la risposta
    options = VoiceOptions.model_validate(decision.get("options", {}))
    return {"script": script.model_dump(), "options": options.model_dump(), ...}

graph = g.compile(checkpointer=InMemorySaver())
```

Il ciclo di vita:

```python
cfg = {"configurable": {"thread_id": job_id}}           # un "thread" = un lavoro
graph.invoke({"text": testo, "attempts": 0}, cfg)        # gira fino all'interrupt
graph.get_state(cfg).next                                # → ("human_review",)

# ... minuti dopo, un'altra richiesta HTTP ...
graph.invoke(Command(resume={"script": modificato, "options": {...}}), cfg)
```

Cose da sapere (domande d'esame!):

- Senza **checkpointer** l'interrupt non funziona: lo stato deve essere salvato da qualche parte.
- Alla ripresa, il nodo che ha chiamato `interrupt` **riparte dall'inizio**: tutto il codice prima di `interrupt()` viene rieseguito. Tenetelo leggero e senza effetti collaterali.
- Il valore di `Command(resume=...)` è ciò che `interrupt()` restituisce.
- Validiamo di nuovo il copione: arriva dal browser, quindi è input non fidato.

## 4.4 Time travel: rigenerare senza richiamare l'LLM (5 min)

L'utente ascolta, non gli piace la voce, vuole riprovare. Il grafo di quel lavoro è finito.
Rifare tutto chiamerebbe di nuovo l'LLM. Invece in `app/main.py`:

```python
graph.update_state(new_cfg, {...stato del lavoro precedente...}, as_node="validate")
graph.invoke(None, new_cfg)   # segue l'arco validate → human_review e si ferma
```

`update_state(as_node=...)` scrive lo stato **come se** l'avesse prodotto quel nodo. È lo stesso
meccanismo che permette di "riavvolgere" un grafo a un checkpoint precedente e prendere un'altra strada.

## 4.5 Visualizzare il grafo (5 min)

```python
from app.graph import build_graph
from app.config import Settings
print(build_graph(Settings(FORMATTER_PROVIDER="fake", TTS_BACKEND="fake")).get_graph().draw_mermaid())
```

Incollate l'output in [mermaid.live](https://mermaid.live). Confrontatelo con il diagramma ASCII in
cima a `graph.py`: se divergono, uno dei due mente.

## Verifica

`uv run pytest tests/test_pipeline.py -k "graph or correction or gives_up"` è verde. Domanda: perché
`test_gives_up_after_max_attempts` controlla che `state.next == ()`?
