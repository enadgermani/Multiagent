# Voce Agenti

Un'app web personale che trasforma un testo in audio italiano, a una o due voci, usando
un'architettura multi-agent:

- **formatter**: un LLM (Qwen in locale, DeepSeek in remoto) riscrive il testo per la sintesi vocale;
- **revisione**: tu leggi e correggi il copione prima di generare l'audio;
- **settings**: costruisce la richiesta per Gemini TTS con voci, velocità e pitch;
- **Gemini TTS** genera l'audio, che ascolti nel browser o scarichi in MP3.

Il corso di 4 ore che ricostruisce il progetto passo passo è in [`corso/`](corso/README.md).

## Architettura

```
Browser ─► FastAPI ─► grafo LangGraph (app/graph.py)

  formatter (LLM) ─► validate ─┬─ errore: riprova (max 3)
                               └─ ok ─► human_review ⏸ ─► settings ─► tts ─► WAV + MP3
```

| File | Ruolo |
|---|---|
| `app/graph.py` | orchestratore: il grafo che collega i passi |
| `app/formatter.py` | subagente LLM: testo grezzo → copione (`Script`) |
| `app/settings_agent.py` | subagente deterministico: copione + scelte → richiesta Gemini |
| `app/tts.py` | strumenti: Gemini TTS e ffmpeg (velocità, pitch, MP3) |
| `app/llm.py` | modelli: Qwen su Ollama, DeepSeek, fallback tra i due |
| `app/schemas.py` | contratti tra gli agenti (Pydantic) e catalogo voci |
| `app/main.py` | API web |
| `static/` | interfaccia |

## Avvio

Requisiti: Python 3.11+, [uv](https://docs.astral.sh/uv/), `ffmpeg`, [Ollama](https://ollama.com) (se usi il modello locale).

```bash
cp .env.example .env              # inserisci GEMINI_API_KEY e, se vuoi, DEEPSEEK_API_KEY
ollama pull qwen3.5:9b            # aggiorna OLLAMA_MODEL se usi un altro modello
uv sync
uv run uvicorn app.main:app       # → http://127.0.0.1:8000
```

Con Docker:

```bash
docker compose up -d
docker compose exec ollama ollama pull qwen3.5:9b
```

L'app non ha login: resta in ascolto solo su `127.0.0.1`.

## Limiti

- Massimo 2 voci: è il limite di Gemini TTS per una singola richiesta.
- Gemini non ha parametri di velocità e pitch: li applica ffmpeg dopo la sintesi.
- I lavori in revisione stanno in memoria: un riavvio del server li cancella.
