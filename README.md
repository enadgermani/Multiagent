# Voce Agenti

Incolli un testo grezzo, un piccolo sistema multi-agent lo trasforma in un copione
per la sintesi vocale, tu lo rivedi, e Gemini TTS lo legge in italiano (anche a più voci).
Ascolti nel browser o scarichi l'MP3.

Il progetto è **didattico**: ogni file spiega nei commenti *perché* è fatto così.
Il corso di 4 ore che lo ricostruisce passo passo è in [`corso/`](corso/README.md).

## Architettura in una figura

```
 Browser ──POST /api/format──►  ORCHESTRATORE (grafo LangGraph)
                                   │
                                   ├─► formatter   (subagente LLM: Qwen locale → fallback DeepSeek)
                                   ├─► validate    (codice: schema Pydantic; se fallisce torna al formatter)
                                   ├─► human_review  ⏸ interrupt: il grafo si ferma, tu rivedi il copione
 Browser ──POST /synthesize────►   │   (riprende da qui)
                                   ├─► settings    (subagente deterministico: voci, strategia, payload API)
                                   ├─► synthesize  (tool: Gemini TTS, chiamate in parallelo)
                                   └─► postprocess (tool: ffmpeg → velocità, pitch, MP3)
```

| Ruolo che avevi immaginato | Dove sta | Perché |
|---|---|---|
| "Un agente costruisce l'infrastruttura" | **Claude Code**, in fase di sviluppo (vedi `CLAUDE.md`) | Costruire l'infra è lavoro *di sviluppo*, non qualcosa che deve succedere a ogni richiesta. Un agente che riscrive l'infra a runtime sarebbe lento, costoso e pericoloso. |
| "Un agente orchestra" | `app/graph.py` | È un **workflow** (grafo con passi noti), non un LLM che decide i passi: più prevedibile, più economico, testabile. |
| "Un subagente formatta" | `app/agents/formatter.py` | Qui serve davvero un LLM: capire chi parla, scrivere "per l'orecchio". |
| "Un subagente crea le impostazioni e l'API" | `app/agents/settings_agent.py` | Ruolo da agente, implementazione in puro codice: sono regole, non giudizi. |
| "Google TTS restituisce l'audio" | `app/tts.py` + `app/audio.py` | Strumenti (tool), non agenti. |

## Avvio rapido (senza Docker)

Requisiti: Python 3.11+, `ffmpeg`, opzionalmente [Ollama](https://ollama.com).

```bash
cp .env.example .env            # e inserisci GEMINI_API_KEY (+ DEEPSEEK_API_KEY se vuoi il fallback)
ollama pull qwen3.5:9b          # o il modello Qwen che hai; aggiorna OLLAMA_MODEL in .env

uv sync                         # oppure: python -m venv .venv && pip install -r requirements.txt pytest httpx
uv run uvicorn app.main:app --reload     # → http://127.0.0.1:8000
```

Senza nessuna chiave puoi provare tutto il flusso con i finti:

```bash
FORMATTER_PROVIDER=fake TTS_BACKEND=fake uv run uvicorn app.main:app
```

## Con Docker

```bash
cp .env.example .env    # chiavi
docker compose up -d
docker compose exec ollama ollama pull qwen3.5:9b
```

L'app ascolta solo su `127.0.0.1`: **non ha login**, non esporla su internet così com'è.

## Test

```bash
uv run pytest -q
```

I test usano LLM e TTS finti: niente rete, niente costi. Coprono formatter, schema,
strategia per numero di voci, chunking dei testi lunghi, filtri ffmpeg, interrupt/resume
del grafo, ciclo di auto-correzione dell'LLM e l'API HTTP.

## Velocità e pitch: come funzionano davvero

Gemini TTS **non ha** parametri numerici di velocità o intonazione: si controllano solo
"a parole" nel campo `style` (es. *slow pace*). Quindi l'app offre due metodi:

- **Preciso (DSP)**: ffmpeg `atempo` cambia la durata senza toccare l'intonazione.
- **Naturale (prompt)**: chiede il ritmo a Gemini; suona più naturale ma è approssimato.

Il pitch è sempre in post-produzione (`rubberband` se il tuo ffmpeg lo ha, altrimenti
`asetrate`+`atempo`). Oltre ±3 semitoni la voce inizia a suonare artificiale.

## Limiti noti

- Gemini accetta **max 2 voci** per richiesta: con 3+ parlanti l'app sintetizza battuta per
  battuta in parallelo e concatena (le voci non "si sentono" a vicenda, il ritmo del dialogo
  è un po' meno naturale).
- Lo stato dei lavori è in memoria (`InMemorySaver`): al riavvio i lavori in revisione si perdono.
  Esercizio del corso: passare a `SqliteSaver`.
- Il campo "registro" delle voci in `app/voices.py` è una nostra stima, non un dato ufficiale.
