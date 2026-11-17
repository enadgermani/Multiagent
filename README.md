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
| `valuta_modelli.py` | confronto tra modelli con dataset ed esperimenti LangSmith |
| `app/studio.py`, `langgraph.json` | grafo per LangGraph Studio (facoltativo) |
| `static/` | interfaccia: l'app e la vista "Dietro le quinte" |

## Avvio

Requisiti: [uv](https://docs.astral.sh/uv/), `ffmpeg`, [Ollama](https://ollama.com) (se usi il modello locale). Python 3.13 lo installa uv da solo (`.python-version`).

Tutti i comandi vanno lanciati dalla cartella principale del repository, quella che contiene `pyproject.toml`:

```bash
git clone https://github.com/enadgermani/Multiagent.git
cd Multiagent
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

## Vedere cosa succede

Due strumenti, entrambi pensati per imparare:

- **La pagina web**: nella colonna "Dietro le quinte" c'è il grafo (generato da LangGraph) con il nodo
  attivo evidenziato, e per ogni passo il JSON scambiato: prompt inviato al modello, risposta grezza,
  esito della validazione, richiesta per Gemini, filtro ffmpeg.
- **LangSmith**: con `LANGSMITH_TRACING=true` e `LANGSMITH_API_KEY` in `.env`, ogni esecuzione diventa una
  trace con prompt completi, token, latenze e la chiamata a Gemini (senza la chiave e senza l'audio).
  Da lì: Playground per riprovare il prompt del formatter, e confronto tra modelli con

  ```bash
  uv run python valuta_modelli.py    # esperimenti Qwen vs DeepSeek sul dataset "formatter-it"
  ```

Facoltativo: LangGraph Studio per eseguire il grafo senza l'app (vedi [corso/07-bonus-studio.md](corso/07-bonus-studio.md)).

## Limiti

- Massimo 2 voci: è il limite di Gemini TTS per una singola richiesta.
- Gemini non ha parametri di velocità e pitch: li applica ffmpeg dopo la sintesi.
- I lavori in revisione stanno in memoria: un riavvio del server li cancella.
