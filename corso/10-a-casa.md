# Modulo 10 · A casa: Docker e l'agente di sviluppo (10 min)

**Concetto:** far girare tutto con un comando, senza mettere le chiavi nell'immagine e senza esporre l'app.
**Costruiamo:** `Dockerfile`, `docker-compose.yml`, `requirements.txt`, `CLAUDE.md`.
**Prerequisiti:** modulo 8.

`requirements.txt`

```text
fastapi>=0.115
uvicorn[standard]>=0.30
pydantic-settings>=2.4
python-dotenv>=1.0
langgraph>=1.0
langchain-core>=1.0
langchain-ollama>=1.0
langchain-openai>=1.0
google-genai>=3.0
```

`Dockerfile`

```text
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY static ./static
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`docker-compose.yml`

```yaml
# Uso: docker compose up -d   →   http://localhost:8000
# Le chiavi arrivano dal file .env (mai nell'immagine).
services:
  app:
    build: .
    env_file: .env
    environment:
      OLLAMA_BASE_URL: http://ollama:11434
    ports:
      - "127.0.0.1:8000:8000"   # solo dal tuo computer: l'app non ha login!
    volumes:
      - ./output:/app/output
    depends_on: [ollama]

  ollama:
    image: ollama/ollama:latest
    volumes:
      - ollama:/root/.ollama
    # Per la GPU NVIDIA (richiede nvidia-container-toolkit) togli il commento:
    # deploy:
    #   resources:
    #     reservations:
    #       devices: [{ driver: nvidia, count: all, capabilities: [gpu] }]

volumes:
  ollama:
```

- Due servizi: l'app raggiunge Ollama all'indirizzo `http://ollama:11434`.
- Le chiavi entrano da `.env` all'avvio; non sono mai copiate nell'immagine.
- Porta legata a `127.0.0.1`: l'app non ha login e non va esposta su internet (per usarla fuori casa, una VPN come Tailscale).

## L'agente di sviluppo

Il codice di questo corso si può far scrivere, modificare e mantenere a un agente di coding (Claude Code).
`CLAUDE.md` gli dà i comandi e le regole del progetto; [prompt-da-zero.md](prompt-da-zero.md) è il prompt
con cui ricostruisce l'intero programma da una cartella vuota.

`CLAUDE.md`

```markdown
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
```

## Verifica

```bash
docker compose up -d
docker compose exec ollama ollama pull qwen3.5:9b
```

→ http://127.0.0.1:8000

## Riepilogo: le decisioni del progetto

1. LLM solo dove serve capire il linguaggio (formatter); codice per le regole (validate, settings).
2. Modello locale per il compito stretto, remoto come riserva; il confronto lo fa LangSmith.
3. Orchestrazione come workflow esplicito, perché i passi sono noti.
4. Una persona nel punto in cui un errore costa: prima della sintesi.
5. Oggetti tipizzati tra i componenti e controlli nel codice per ogni regola importante del prompt.

Per continuare: `SqliteSaver` per i lavori persistenti, più di due voci (una richiesta per battuta e audio
concatenato), `graph.stream(...)` per vedere i passi mentre avvengono. LangGraph Studio, per eseguire il
grafo senza l'app, è nel [bonus](bonus-studio.md).
