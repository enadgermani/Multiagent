# Corso: un'architettura multi-agent a casa, in 4 ore

**Pubblico:** sviluppatori che sanno Python ma non hanno mai costruito con l'AI.
**Risultato:** *Voce Agenti* funzionante sul proprio computer: un'app web che trasforma un testo in
audio italiano a una o due voci, con un modello locale (Qwen su Ollama), uno remoto (DeepSeek) e un
modello di sintesi vocale (Gemini TTS), coordinati da un grafo LangGraph.

## Agenda

| Ora | Modulo | File del progetto |
|---|---|---|
| 0:00 – 0:30 | [1. Concetti e scelta del framework](01-concetti.md) | – |
| 0:30 – 1:10 | [2. Modelli locali e remoti](02-modelli.md) | `config.py`, `llm.py` |
| 1:10 – 1:55 | [3. Il subagente formatter](03-formatter.md) | `schemas.py`, `formatter.py` |
| 1:55 – 2:05 | Pausa | |
| 2:05 – 2:55 | [4. L'orchestratore con LangGraph](04-orchestratore.md) | `graph.py` |
| 2:55 – 3:30 | [5. Subagente settings, Gemini TTS e audio](05-tts-audio.md) | `settings_agent.py`, `tts.py` |
| 3:30 – 4:00 | [6. Web e avvio a casa](06-web.md) | `main.py`, `static/`, Docker |

Ogni modulo: un po' di teoria, poi si scrive il file indicato. Il repository contiene la versione
completa da cui copiare se si resta indietro.

## Da preparare prima

- Python 3.11+, [uv](https://docs.astral.sh/uv/), `ffmpeg`, git.
- [Ollama](https://ollama.com) con un modello Qwen da 7-9B: `ollama pull qwen3.5:9b`.
  Senza GPU funziona ma è lento: in quel caso si usa DeepSeek.
- Una chiave Gemini da [Google AI Studio](https://aistudio.google.com/apikey).
- Facoltativa: una chiave [DeepSeek](https://platform.deepseek.com).
