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

## 4.4 Vedere il grafo: LangGraph Studio e LangSmith (5 min)

**LangGraph Studio** mostra il grafo disegnato e permette di eseguirlo nodo per nodo, vedere lo stato
dopo ogni passo e rispondere all'interrupt da un'interfaccia grafica. Serve un account gratuito su
[LangSmith](https://smith.langchain.com) e una sua chiave in `.env` (`LANGSMITH_API_KEY`).

Il file `langgraph.json` dice a Studio dove trovare il grafo:

```json
{"dependencies": ["."], "graphs": {"voce_agenti": "./app/studio.py:graph"}, "env": ".env"}
```

```bash
uv run --with "langgraph-cli[inmem]" langgraph dev
```

Il comando avvia un server locale e stampa l'indirizzo di Studio (`https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024`).
In `app/studio.py` il grafo è compilato senza checkpointer, perché Studio usa il proprio.

Prova: in Studio inserite `{"text": "Marco: Ciao Giulia\nGiulia: Ciao!"}` come input. Il grafo si ferma su
`human_review`; come risposta all'interrupt passate
`{"script": <il copione mostrato>, "options": {"speed": 1, "pitch": 0}}` e guardate i nodi successivi.

**Tracing.** Con `LANGSMITH_TRACING=true` in `.env`, anche le esecuzioni lanciate dall'app web finiscono
su LangSmith: per ogni lavoro vedete i nodi, i messaggi inviati al formatter, la sua risposta, i tempi.
È il modo più rapido per capire perché il formatter ha sbagliato. Ricordate che così i testi vengono
inviati a LangSmith.
