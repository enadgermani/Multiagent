# Modulo 6 · Web, LangSmith e avvio a casa (30 min)

**File:** `app/main.py`, `static/`, `valuta_modelli.py`, `Dockerfile`, `docker-compose.yml`

## 6.1 L'API in due chiamate (7 min)

```
POST /api/format              → crea un job_id, il grafo gira fino a human_review → copione
POST /api/synthesize/{job_id} → il grafo riprende con copione e impostazioni → link all'audio
GET  /api/audio/{job_id}.mp3  → il file
```

```python
@app.post("/api/format")
def format_text(req: FormatRequest):
    job_id = uuid.uuid4().hex
    graph.invoke({"text": req.text, "temperature": req.temperature}, job_config(job_id, "formatta"))
    state = graph.get_state(job_config(job_id))
    ...
    return {"script": state.values["script"], **view(job_id)}   # view: passi e nodo corrente
```

- Gli endpoint sono `def`, non `async def`: il grafo è bloccante e FastAPI lo esegue in un thread separato.
- `job_id` diventa il `thread_id` del grafo: è così che la seconda chiamata ritrova il lavoro giusto.
- Prima di usare `job_id` come nome di file lo convertiamo in UUID: niente percorsi come `../../`.

- `job_config` aggiunge `run_name` e `metadata`: servono solo a LangSmith, per dare un nome alle trace e raggrupparle.

Il frontend (`static/app.js`) chiama solo questi endpoint: non sa nulla di agenti.

## 6.2 LangSmith al lavoro (15 min)

Con `LANGSMITH_TRACING=true` e `LANGSMITH_API_KEY` in `.env`, LangSmith non serve solo a guardare.
Quattro usi pratici:

1. **Debug.** Una formattazione è venuta male? Aprite la trace, cliccate sulla chiamata al modello e
   leggete messaggi e risposta. Se c'è stata una correzione, si vede quale errore l'ha provocata.
2. **Playground.** Dalla chiamata al modello, il pulsante *Playground* apre lo stesso prompt in un
   editor: cambiate una regola del prompt di sistema o la temperatura e rilanciate, senza toccare il
   codice. Il Playground gira nel cloud di LangSmith: funziona con i modelli remoti (per DeepSeek si
   configura un endpoint compatibile OpenAI, con la chiave nei *Secrets* di LangSmith), non con
   l'Ollama di casa vostra.
3. **Confronto tra modelli.** `valuta_modelli.py` crea un dataset di testi di prova e lancia un
   esperimento per Qwen e uno per DeepSeek, con tre valutatori scritti in Python (schema valido, simboli
   rimossi, testo non riassunto):

   ```python
   def valid_schema(outputs: dict) -> bool:
       try:
           parse_script(outputs["raw"])
           return True
       except ValueError:
           return False

   evaluate(target(model), data="formatter-it", evaluators=[valid_schema, no_symbols, not_summarized],
            experiment_prefix=name)
   ```

   ```bash
   uv run python valuta_modelli.py
   ```

   In *Datasets & Experiments* > `formatter-it` i due esperimenti si confrontano riga per riga.
   È così che si decide, con i numeri, se il modello locale basta.
4. **Costi e latenza.** Ogni trace riporta token e tempi per passo. Per DeepSeek LangSmith può
   calcolare anche il costo, se il prezzo del modello è configurato nelle impostazioni del progetto.

Ricordate: con il tracing attivo i testi che formattate vengono inviati a LangSmith.

## 6.3 Avvio con Docker (5 min)

```bash
docker compose up -d
docker compose exec ollama ollama pull qwen3.5:9b
```

- Due servizi, `app` e `ollama`: l'app raggiunge Ollama all'indirizzo `http://ollama:11434`.
- Le chiavi entrano da `.env` al momento dell'avvio, non sono mai copiate nell'immagine.
- La porta è legata a `127.0.0.1`: l'app non ha login e non va esposta su internet.
- Per la GPU NVIDIA, togliere il commento al blocco `deploy` in `docker-compose.yml`.

## 6.4 Riepilogo e passi successivi (3 min)

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
