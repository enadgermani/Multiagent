# Modulo 0 · Concetti e preparazione (20 min)

**Concetto:** cos'è un LLM per un programmatore, la differenza tra agente e workflow, e perché useremo LangGraph.
**Costruiamo:** la cartella del progetto, le dipendenze, il file delle chiavi.

## 0.1 Un LLM, visto da un programmatore

```python
def llm(messaggi: list[Messaggio], temperatura: float) -> Messaggio: ...
```

- Riceve una lista di messaggi: `system` (ruolo e regole), `user` (la richiesta), `assistant` (le sue risposte precedenti).
- Genera testo un *token* alla volta (circa ¾ di parola) scegliendo con un po' di casualità: la
  **temperatura** regola quanta. Bassa (0–0.3) per compiti precisi, alta per compiti creativi.
- Non ricorda nulla tra una chiamata e l'altra: sa solo ciò che c'è nei messaggi (il **contesto**).
- Può sbagliare formato, ignorare una regola, inventare. Buona parte del progetto serve a gestire questo.

## 0.2 Agente, subagente, workflow, strumento

- **Agente**: un LLM in un ciclo. Riceve un obiettivo e degli strumenti, decide quale usare, legge il risultato, decide il passo successivo. *È l'LLM a scegliere il percorso.*
- **Subagente**: un componente con un compito stretto, chiamato da un altro. Prompt corto, contesto pulito, può girare su un modello piccolo.
- **Workflow**: i passi e il loro ordine sono scritti nel codice. *È il programmatore a scegliere il percorso.*
- **Strumento** (tool): una funzione che fa una cosa precisa (chiamare un'API, convertire un file) e non decide nulla.
- **Orchestrazione**: il pezzo che coordina tutto e passa i dati da un componente all'altro.

Regola pratica: un LLM serve dove c'è da **capire il linguaggio**; dove ci sono **regole** basta il codice.

## 0.3 Cosa costruiremo

*Voce Agenti*: incolli un testo, un modello lo riscrive come copione per la sintesi vocale, tu lo
rivedi, Gemini TTS lo legge in italiano a una o due voci, e ascolti o scarichi l'MP3.

```
Browser ─► FastAPI ─► grafo LangGraph

  formatter (LLM) ─► validate ─┬─ errore: riprova (max 3)
                               └─ ok ─► human_review ⏸ ─► settings ─► tts ─► WAV + MP3
```

| Componente | Tipo | Modulo |
|---|---|---|
| modelli Qwen e DeepSeek | LLM dietro un'interfaccia unica | 1 |
| contratti tra componenti | schemi Pydantic | 2 |
| formatter | subagente **LLM** | 3 |
| Gemini TTS, ffmpeg | strumenti | 4 |
| settings | subagente **deterministico** | 5 |
| orchestratore | workflow (grafo LangGraph) | 6 |
| human_review | una persona, con pausa e ripresa del grafo | 7 |
| pagina web | interfaccia + vista "Dietro le quinte" | 8 |
| LangSmith | osservare, confrontare, migliorare | 9 |

Ogni modulo introduce **un** concetto e aggiunge **un pezzo** di codice che si può provare subito.

## 0.4 Quale framework

Prima di scegliere, elenchiamo **cosa ci serve**:

1. chiamare modelli diversi (Ollama, DeepSeek) con lo stesso codice;
2. eseguire passi in un ordine fisso, con un ciclo "riprova se l'output è sbagliato";
3. **fermarsi a metà** per la revisione dell'utente e ripartire più tardi, da un'altra richiesta HTTP;
4. uno stato condiviso tra i passi (testo, copione, impostazioni).

Non ci serve: un LLM che decide i passi, la pianificazione autonoma, la memoria a lungo termine,
più agenti che conversano tra loro.

| Strumento | Cosa fa | Copre i nostri bisogni? |
|---|---|---|
| **LangChain** | un'interfaccia unica per i modelli di molti fornitori, più prompt e parser | sì il punto 1. Lo usiamo solo per questo |
| **LangGraph** | grafi di passi con stato, archi condizionali, pausa e ripresa (checkpoint + interrupt) | sì i punti 2, 3 e 4. **È il nostro orchestratore** |
| **deepagents** | un agente già pronto sopra LangGraph: l'LLM pianifica una lista di cose da fare, usa un filesystem, delega a subagenti | no: è fatto perché l'LLM decida il percorso, noi il percorso lo conosciamo già |
| **Hermes Agent** (Nous Research) | un assistente personale autonomo con memoria, strumenti e abilità che impara nel tempo | no: è un prodotto-agente da usare, non un mattone per costruire una pipeline |
| **CrewAI** | più agenti con un "ruolo" (es. ricercatore, scrittore) che collaborano su un compito | no: ogni nostro passo ha un compito fisso, non serve farli "collaborare" |
| **AutoGen / AG2** | agenti che si scambiano messaggi in una conversazione per risolvere un problema | no: i nostri componenti si passano dati strutturati, non chiacchierano |
| **OpenAI Agents SDK**, **Claude Agent SDK** | il ciclo "LLM + strumenti" già scritto, con passaggio di compiti tra agenti, legato al modello del fornitore | no: il cuore è l'agente autonomo, e noi vogliamo modelli di fornitori diversi |
| **PydanticAI** | chiamate a LLM con output validato da modelli Pydantic, strumenti tipizzati | in parte: coprirebbe i punti 1 e la validazione, ma non la pausa e la ripresa |

In sintesi: quasi tutti questi strumenti servono a costruire **agenti autonomi**. Il nostro problema è
una **pipeline con un LLM dentro e una pausa per l'utente**: LangGraph è lo strumento che fa
esattamente questo senza obbligarci a mettere un LLM al comando.


## 0.5 Preparazione

Requisiti: [uv](https://docs.astral.sh/uv/), `ffmpeg`, [Ollama](https://ollama.com) con un modello Qwen
(`ollama pull qwen3.5:9b`), una chiave [Gemini](https://aistudio.google.com/apikey); facoltative una chiave
[DeepSeek](https://platform.deepseek.com) e un account [LangSmith](https://smith.langchain.com).

Create una cartella `voce-agenti` con dentro le cartelle `app`, `static` e `prove` (gli script di verifica
dei moduli) e un file vuoto `app/__init__.py`. Su macOS e Linux:

```bash
mkdir -p voce-agenti/app voce-agenti/static voce-agenti/prove && cd voce-agenti && touch app/__init__.py
```

Tutti i comandi del corso si lanciano da questa cartella (su Windows, da PowerShell).

`pyproject.toml`

```toml
[project]
name = "voce-agenti"
version = "1.0.0"
description = "Testo -> copione -> voce italiana: un'architettura multi-agent didattica con LangGraph, Qwen locale, DeepSeek e Gemini TTS"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "pydantic-settings>=2.4",
    "python-dotenv>=1.0",
    "langgraph>=1.0",
    "langchain-core>=1.0",
    "langchain-ollama>=1.0",
    "langchain-openai>=1.0",
    "google-genai>=3.0",
]
```

`.python-version`

```text
3.13
```

`.gitignore` (le chiavi non devono mai finire su git):

```text
.env
.venv/
__pycache__/
output/
```

`cp .env.example .env` funziona anche in PowerShell.

`.env.example`

```text
# Copia in .env e inserisci le tue chiavi. .env è in .gitignore: non finisce su git.

# Google AI Studio: https://aistudio.google.com/apikey
GEMINI_API_KEY=
TTS_MODEL=gemini-3.8-flash-tts

# Formatter: local (Qwen su Ollama) | remote (DeepSeek) | auto (locale, poi remoto se fallisce)
FORMATTER_PROVIDER=auto
OLLAMA_BASE_URL=http://localhost:11434
# Nome esatto del modello: controlla con "ollama list"
OLLAMA_MODEL=qwen3.5:9b

DEEPSEEK_API_KEY=
DEEPSEEK_MODEL=deepseek-chat

# Facoltativo: tracing su LangSmith (https://smith.langchain.com) e LangGraph Studio.
# Con queste variabili ogni esecuzione del grafo appare su LangSmith, nodo per nodo.
# Attenzione: i testi che formatti vengono inviati a LangSmith.
LANGSMITH_TRACING=false
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=voce-agenti
# Solo se il tuo account LangSmith è nella regione europea:
# LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com
```

```bash
cp .env.example .env     # e inserite le vostre chiavi
uv sync                  # crea .venv e installa tutto (Python 3.13 compreso)
```

## Verifica

```bash
uv run python -c "import langgraph, langchain_ollama, google.genai; print('ok')"
ollama run qwen3.5:9b "Dimmi ciao in tre lingue"
ffmpeg -version
```
