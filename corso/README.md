# Corso: un'architettura multi-agent a casa, in 4 ore

**Pubblico:** sviluppatori che sanno Python ma non hanno mai costruito con l'AI.
**Risultato:** *Voce Agenti* funzionante sul proprio computer: un'app web che trasforma un testo in
audio italiano a una o due voci, con un modello locale (Qwen su Ollama), uno remoto (DeepSeek) e un
modello di sintesi vocale (Gemini TTS), coordinati da un grafo LangGraph.

## Due strumenti per vedere cosa succede

| Strumento | Cosa mostra | Quando si usa |
|---|---|---|
| **La pagina web** (`http://127.0.0.1:8000`) | il prodotto (testo → copione → audio) e, nella colonna "Dietro le quinte", il grafo con il nodo attivo e il JSON passato tra i nodi: prompt inviato, risposta grezza, esito della validazione, richiesta per Gemini | sempre: è il punto di partenza |
| **LangSmith** (smith.langchain.com) | le trace complete di ogni esecuzione (prompt, token, latenza, chiamata a Gemini), più strumenti di lavoro: Playground per riprovare un prompt, dataset ed esperimenti per confrontare i modelli | per il debug e per migliorare il formatter (moduli 4 e 6) |

In ogni modulo, il riquadro **Cosa guardare** dice dove osservare il concetto appena visto.
LangGraph Studio è un terzo strumento, facoltativo: è nel [bonus](07-bonus-studio.md).

## Agenda

| Ora | Modulo | File del progetto |
|---|---|---|
| 0:00 – 0:30 | [1. Concetti e scelta del framework](01-concetti.md) | – |
| 0:30 – 1:10 | [2. Modelli locali e remoti](02-modelli.md) | `config.py`, `llm.py` |
| 1:10 – 1:55 | [3. Il subagente formatter](03-formatter.md) | `schemas.py`, `formatter.py` |
| 1:55 – 2:05 | Pausa | |
| 2:05 – 2:55 | [4. L'orchestratore con LangGraph](04-orchestratore.md) | `graph.py` |
| 2:55 – 3:30 | [5. Subagente settings, Gemini TTS e audio](05-tts-audio.md) | `settings_agent.py`, `tts.py` |
| 3:30 – 4:00 | [6. Web, LangSmith e avvio a casa](06-web.md) | `main.py`, `static/`, `valuta_modelli.py`, Docker |
| bonus | [LangGraph Studio](07-bonus-studio.md) | `langgraph.json`, `app/studio.py` |

Ogni modulo: un po' di teoria, poi si scrive il file indicato. Il repository contiene la versione
completa da cui copiare se si resta indietro.

## Da preparare prima

Clonare il repository ed entrare nella cartella: tutti i comandi `uv` del corso si lanciano da lì,
dove c'è `pyproject.toml`.

```bash
git clone https://github.com/enadgermani/Multiagent.git
cd Multiagent
```

- Python 3.11+, [uv](https://docs.astral.sh/uv/), `ffmpeg`, git.
- [Ollama](https://ollama.com) con un modello Qwen da 7-9B: `ollama pull qwen3.5:9b`.
  Senza GPU funziona ma è lento: in quel caso si usa DeepSeek.
- Una chiave Gemini da [Google AI Studio](https://aistudio.google.com/apikey).
- Facoltativa: una chiave [DeepSeek](https://platform.deepseek.com).
- Un account gratuito [LangSmith](https://smith.langchain.com) e la sua chiave (`LANGSMITH_API_KEY`).

Avvio dell'app, l'unico comando che serve durante il corso:

```bash
uv sync
uv run uvicorn app.main:app      # → http://127.0.0.1:8000
```
