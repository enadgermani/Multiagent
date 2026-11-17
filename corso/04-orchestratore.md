# Modulo 4 · L'orchestratore con LangGraph (50 min)

**File:** `app/graph.py`

## 4.1 Stato, nodi, archi (10 min)

- **Stato**: un `TypedDict` condiviso da tutti i passi.
- **Nodo**: una funzione `stato -> dict` che restituisce solo le chiavi che cambia.
- **Arco**: fisso (`add_edge`) o condizionale (`add_conditional_edges`, una funzione sceglie il nodo successivo).

```python
class State(TypedDict, total=False):
    text: str          # input dell'utente
    raw: str           # risposta grezza del formatter
    error: str | None  # errore di validazione (None = ok)
    attempts: int
    script: dict       # copione validato
    options: dict      # scelte dell'utente
    request: dict      # richiesta per Gemini
```

## 4.2 Il ciclo di correzione (15 min)

```python
def formatter_node(state):
    messages = formatter.build_messages(state["text"], state.get("raw"), state.get("error"))
    return {"raw": model.invoke(messages).content}

def validate_node(state):
    attempts = state.get("attempts", 0) + 1
    try:
        script = formatter.parse_script(state["raw"])
    except ValueError as e:
        return {"error": str(e), "attempts": attempts}
    return {"script": script.model_dump(), "error": None, "attempts": attempts}

def after_validate(state):
    if state["error"] is None:
        return "human_review"
    return "formatter" if state["attempts"] < MAX_ATTEMPTS else END

g.add_edge("formatter", "validate")
g.add_conditional_edges("validate", after_validate, ["formatter", "human_review", END])
```

Tre responsabilità separate: il formatter **genera** (LLM), validate **giudica** (codice), il router
**decide** (codice). Al secondo giro il formatter trova nello stato `raw` ed `error` e li usa per
chiedere la correzione.

## 4.3 La pausa per l'utente: interrupt (20 min)

L'utente deve vedere il copione prima della sintesi. Ma una richiesta HTTP non può restare aperta
mentre lui legge: il grafo deve fermarsi, salvare lo stato e ripartire da un'altra richiesta.

```python
def human_review_node(state):
    answer = interrupt(state["script"])                     # ⏸ si ferma qui
    script = Script.model_validate(answer["script"])        # ▶ riparte da qui
    options = VoiceOptions.model_validate(answer["options"])
    return {"script": script.model_dump(), "options": options.model_dump()}

graph = g.compile(checkpointer=InMemorySaver())
```

Il ciclo di vita:

```python
cfg = {"configurable": {"thread_id": job_id}}            # un thread = un lavoro
graph.invoke({"text": testo}, cfg)                        # gira fino all'interrupt
graph.get_state(cfg).next                                 # ('human_review',)

# più tardi, da un'altra richiesta HTTP:
graph.invoke(Command(resume={"script": ..., "options": ...}), cfg)
```

Da ricordare:

- senza **checkpointer** l'interrupt non funziona: lo stato deve essere salvato da qualche parte;
- il valore passato in `Command(resume=...)` è ciò che `interrupt()` restituisce;
- alla ripresa il nodo riparte dall'inizio: il codice prima di `interrupt()` viene rieseguito;
- il copione torna dal browser, quindi lo validiamo di nuovo.

### Rigenerare l'audio senza richiamare il modello

Dopo "Genera audio" il grafo è arrivato a `END`. Se cambiate voce o pitch e premete di nuovo, l'API
riporta lo stesso lavoro alla revisione:

```python
graph.update_state(cfg, {"error": None, "steps": [step]}, as_node="validate")
graph.invoke(None, cfg)          # segue validate -> human_review e si ferma all'interrupt
graph.invoke(Command(resume={"script": ..., "options": ...}), cfg)
```

`update_state(..., as_node="validate")` scrive un nuovo checkpoint **come se** l'avesse prodotto il nodo
`validate`; il grafo riparte da lì con il copione già pronto. È il *time travel* di LangGraph: il
checkpointer conserva la storia, e si può riprendere da un punto precedente. Nella pagina compare il
passo `rewind`, e il formatter non viene richiamato.

## 4.4 Vedere il grafo mentre lavora (5 min)

Ogni nodo aggiunge una voce allo stato con ciò che ha ricevuto e prodotto:

```python
class State(TypedDict, total=False):
    ...
    steps: Annotated[list[dict], operator.add]   # reducer: ogni nodo AGGIUNGE, non sostituisce

def settings_node(state):
    request = settings_agent.build_tts_request(...)
    return {"request": request, "steps": [{"node": "settings", "output": {"gemini_request": request}}]}
```

`operator.add` è un **reducer**: dice a LangGraph come combinare il valore nuovo con quello vecchio.
Senza, ogni nodo sovrascriverebbe la lista.

La pagina chiede il diagramma a `/api/graph` (che restituisce `graph.get_graph().draw_mermaid()`) e lo
colora: verde i nodi eseguiti, giallo quello dove il grafo è fermo.

> **Cosa guardare.**
> - *Pagina*: dopo "Formatta" il grafo è fermo su `human_review` (giallo). Dopo "Genera audio" tutti i
>   nodi sono verdi e l'elenco dei passi mostra l'intero percorso, compresi eventuali tentativi ripetuti.
> - *LangSmith*: le due chiamate HTTP diventano due trace, "formatta" e "genera_audio". Hanno lo stesso
>   `thread_id` nei metadata, quindi nella vista **Threads** del progetto compaiono insieme: è lo stesso
>   lavoro, interrotto e ripreso.
