# Istruzioni per l'agente di sviluppo (Claude Code)

Questo è l'"agente che costruisce l'infrastruttura": lavora in fase di sviluppo, non a runtime.

## Progetto
App web personale: testo → copione (LLM) → revisione umana → Gemini TTS → MP3. Python 3.11+, FastAPI,
LangGraph, frontend vanilla in `static/`. Commenti e testi utente in italiano, identificatori in inglese.

## Comandi
- Test: `uv run pytest -q` (sempre verdi prima di consegnare)
- Server di sviluppo senza chiavi: `FORMATTER_PROVIDER=fake TTS_BACKEND=fake uv run uvicorn app.main:app --reload`

## Regole
- Mai leggere, stampare o committare `.env` o chiavi API. Le chiavi si leggono solo da `app/config.py`.
- Ogni nuovo nodo del grafo: aggiorna il diagramma in `app/graph.py` e aggiungi un test con LLM/TTS finti.
- Gli agenti si scambiano oggetti Pydantic (`app/schemas.py`), mai testo libero.
- Non aggiungere un LLM dove basta codice deterministico.
- L'app non ha autenticazione: non cambiare il bind `127.0.0.1` in `docker-compose.yml`.
