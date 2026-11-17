# Istruzioni per Claude Code

## Progetto
App web personale: testo → copione (LLM) → revisione umana → Gemini TTS → MP3. Python 3.11+, FastAPI,
LangGraph, frontend vanilla in `static/`. È materiale didattico: il codice resta minimo e leggibile.
Commenti e testi utente in italiano, identificatori in inglese.

## Comandi
- Server: `uv run uvicorn app.main:app --reload`

## Regole
- Mai leggere, stampare o committare `.env` o chiavi API. Le chiavi si leggono solo da `app/config.py`.
- Ogni nuovo nodo del grafo: aggiorna il diagramma in cima a `app/graph.py` e fai aggiungere al nodo una voce a `steps` (input/output in JSON) per la pagina web.
- Gli agenti si scambiano oggetti Pydantic (`app/schemas.py`), mai testo libero.
- Non aggiungere un LLM dove basta codice deterministico.
- L'app non ha autenticazione: non cambiare il bind `127.0.0.1` in `docker-compose.yml`.
