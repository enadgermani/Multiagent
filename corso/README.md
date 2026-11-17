# Corso: un'architettura multi-agent a casa, in 4 ore

**Pubblico:** sviluppatori che sanno Python ma non hanno mai costruito con l'AI.
**Risultato:** *Voce Agenti* funzionante sul proprio computer: un'app web che trasforma un testo in audio
italiano a una o due voci, con un modello locale (Qwen su Ollama), uno remoto (DeepSeek) e un modello di
sintesi vocale (Gemini TTS), coordinati da un grafo LangGraph e osservati con LangSmith.

## Come è fatto

Ogni modulo spiega **un concetto** e aggiunge **un pezzo** di codice che si prova subito. I moduli sono in
ordine: seguiti tutti, si ottiene il programma completo, identico a quello del repository. Ognuno si può
anche leggere da solo: in cima trovate i prerequisiti, cioè i file dei moduli precedenti da copiare dal
repository se partite da lì.

| Ora | Modulo | Concetto | File |
|---|---|---|---|
| 0:00 | [0. Concetti e preparazione](00-concetti-e-setup.md) | LLM, agente vs workflow, scelta del framework | `pyproject.toml`, `.env` |
| 0:20 | [1. Chiamare un modello](01-modelli.md) | interfaccia unica, temperatura, fallback, tracing | `config.py`, `llm.py` |
| 0:40 | [2. Contratti tra componenti](02-contratti.md) | schemi tipizzati e validazione | `schemas.py` |
| 0:55 | [3. Il subagente formatter](03-formatter.md) | prompt, controlli nel codice, auto-correzione | `formatter.py` |
| 1:25 | [4. Strumenti: Gemini TTS e ffmpeg](04-strumenti-audio.md) | strumenti isolati, tracing manuale | `tts.py` |
| 1:45 | [5. Il subagente settings](05-settings.md) | un agente senza LLM; la pipeline a mano | `settings_agent.py` |
| 2:00 | Pausa | | |
| 2:10 | [6. L'orchestratore](06-grafo.md) | stato, nodi, archi condizionali | `graph.py` v1 |
| 2:40 | [7. Una persona nel ciclo](07-umano-nel-ciclo.md) | interrupt, checkpoint, time travel | `graph.py` v2 |
| 3:05 | [8. La pagina web](08-pagina-web.md) | API in due fasi, reducer, vista "Dietro le quinte" | `graph.py`, `main.py`, `static/` |
| 3:30 | [9. LangSmith al lavoro](09-langsmith.md) | debug, Playground, dataset ed esperimenti | `valuta_modelli.py` |
| 3:50 | [10. A casa](10-a-casa.md) | Docker, agente di sviluppo | `Dockerfile`, `CLAUDE.md` |
| bonus | [LangGraph Studio](bonus-studio.md) | eseguire il grafo senza l'app | `langgraph.json` |

## Due strumenti per vedere cosa succede

- **La pagina web** (dal modulo 8): il grafo con il nodo attivo e il JSON passato tra i nodi.
- **LangSmith** (dal modulo 1): le trace di ogni esecuzione e gli strumenti per migliorare il sistema.

Prima, nei moduli 1–7, si lavora da terminale: ogni modulo finisce con un breve script in `prove/` da lanciare con `uv run python -m prove.<nome>`.

## Il prompt per ricostruire tutto

[prompt-da-zero.md](prompt-da-zero.md) contiene un unico prompt da dare a un agente di coding (Claude Code)
per ricreare l'intero programma partendo da una cartella vuota. Utile per confrontare il proprio codice,
o per vedere come si specifica un progetto a un agente.
