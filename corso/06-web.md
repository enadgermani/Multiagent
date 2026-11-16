# Modulo 6 · Web e avvio a casa (30 min)

**File:** `app/main.py`, `static/`, `Dockerfile`, `docker-compose.yml`

## 6.1 L'API in due chiamate (10 min)

```
POST /api/format              → crea un job_id, il grafo gira fino a human_review → copione
POST /api/synthesize/{job_id} → il grafo riprende con copione e impostazioni → link all'audio
GET  /api/audio/{job_id}.mp3  → il file
```

```python
@app.post("/api/format")
def format_text(req: FormatRequest):
    job_id = uuid.uuid4().hex
    graph.invoke({"text": req.text}, job_config(job_id))
    state = graph.get_state(job_config(job_id))
    if state.next != ("human_review",):
        raise HTTPException(422, f"Il formatter non ha prodotto un copione valido: {state.values['error']}")
    return {"job_id": job_id, "script": state.values["script"]}
```

- Gli endpoint sono `def`, non `async def`: il grafo è bloccante e FastAPI lo esegue in un thread separato.
- `job_id` diventa il `thread_id` del grafo: è così che la seconda chiamata ritrova il lavoro giusto.
- Prima di usare `job_id` come nome di file lo convertiamo in UUID: niente percorsi come `../../`.

Il frontend (`static/app.js`) chiama solo questi endpoint: non sa nulla di agenti.

## 6.2 Avvio con Docker (10 min)

```bash
docker compose up -d
docker compose exec ollama ollama pull qwen3.5:9b
```

- Due servizi, `app` e `ollama`: l'app raggiunge Ollama all'indirizzo `http://ollama:11434`.
- Le chiavi entrano da `.env` al momento dell'avvio, non sono mai copiate nell'immagine.
- La porta è legata a `127.0.0.1`: l'app non ha login e non va esposta su internet.
- Per la GPU NVIDIA, togliere il commento al blocco `deploy` in `docker-compose.yml`.

## 6.3 Riepilogo e passi successivi (10 min)

Le decisioni del progetto:

1. LLM solo dove serve capire il linguaggio (formatter); codice per le regole (validate, settings).
2. Modello locale per il compito stretto, remoto come riserva.
3. Orchestrazione come workflow esplicito, perché i passi sono noti.
4. Una persona nel punto in cui un errore costa: prima della sintesi.
5. Oggetti tipizzati tra i componenti, così gli errori emergono subito.

Per continuare a casa:

- salvare i lavori su disco con `SqliteSaver` (pacchetto `langgraph-checkpoint-sqlite`), così sopravvivono ai riavvii;
- gestire più di due voci: una richiesta per battuta e audio concatenato;
- mostrare nel browser ogni passo mentre avviene, con `graph.stream(...)`.
