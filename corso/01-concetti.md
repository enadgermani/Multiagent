# Modulo 1 · Concetti (30 min)

**Obiettivi:** avere un modello mentale corretto di LLM, agente, subagente, workflow e orchestrazione;
sapere perché useremo LangGraph.

## 1.1 Un LLM è una funzione (strana)

Per un programmatore la definizione più utile è:

```python
def llm(messaggi: list[Messaggio], **parametri) -> Messaggio: ...
```

- **Input**: una lista di messaggi (`system`, `user`, `assistant`). Il messaggio di sistema dà il ruolo e le regole.
- **Output**: testo generato un *token* alla volta (un token ≈ ¾ di parola). Ogni token è campionato da una distribuzione di probabilità.
- **Temperatura**: quanto è "piatta" quella distribuzione. 0–0.3 per compiti precisi (formattare, estrarre), 0.7+ per compiti creativi.
- **Contesto**: quanti token può leggere in una volta. Tutto ciò che il modello "sa" della conversazione sta lì: non ha memoria tra una chiamata e l'altra.
- **Non deterministica e fallibile**: può restituire JSON rotto, inventare, ignorare una regola. *Tutta l'ingegneria che faremo serve a gestire questo fatto.*

Demo (2 min):

```bash
ollama run qwen3.5:9b "Trasforma in testo leggibile ad alta voce: 'Il 3,5% del PIL (dati ISTAT) ecc.'"
```

Fatelo tre volte: le risposte cambiano. Ora chiedete JSON: a volte arriva con i ```` ``` ```` intorno. Ecco il problema.

## 1.2 Workflow o agente?

| | Workflow | Agente |
|---|---|---|
| Chi decide il prossimo passo | il **tuo codice** | l'**LLM** (in un ciclo con strumenti) |
| Prevedibilità | alta | bassa |
| Costo/latenza | bassi | alti, variabili |
| Quando usarlo | i passi sono noti | il percorso dipende da cosa si scopre strada facendo |

Un **agente** nella forma classica è un ciclo: l'LLM riceve un obiettivo e un elenco di strumenti,
sceglie uno strumento, il codice lo esegue, il risultato torna all'LLM, e così via finché l'LLM non dice "fatto".

Un **subagente** è un agente (o un LLM) con un compito stretto, chiamato da un altro componente.
Vantaggi: prompt corti e mirati, contesto pulito, modelli più piccoli e più economici.

**Regola d'oro:** parti dal workflow più semplice che funziona; aggiungi autonomia solo dove porta valore misurabile.

## 1.3 Rileggiamo l'idea iniziale

L'idea di partenza era:

1. un agente costruisce l'infrastruttura;
2. un agente, chiamato dal sito, orchestra;
3. un subagente formatta il testo;
4. un subagente prepara le impostazioni e la chiamata API;
5. Google TTS restituisce l'audio.

È un'ottima scomposizione di **ruoli**. Ma non tutti i ruoli devono essere LLM:

- **(1)** è lavoro di *sviluppo*: lo fa un agente di coding (Claude Code) che scrive questo repository,
  guidato da `CLAUDE.md`. Un agente che costruisce infrastruttura *a ogni richiesta web* sarebbe lento,
  costoso e pericoloso.
- **(2)** i passi sono sempre gli stessi → **workflow** (grafo LangGraph), non un LLM che decide.
- **(3)** serve giudizio linguistico → **LLM** (Qwen locale, DeepSeek di riserva).
- **(4)** sono regole (max 2 voci per richiesta, voci valide, chunking) → **codice deterministico** con il *ruolo* di agente.
- **(5)** è uno **strumento** (tool).

E aggiungiamo un attore che l'idea iniziale implicava ma non nominava: **l'umano**, che rivede il copione.

## 1.4 L'architettura che costruiremo

```
Browser ─► FastAPI ─► Grafo LangGraph
                       formatter (LLM) ⇄ validate (Pydantic)   ← ciclo di auto-correzione
                       human_review  ⏸                         ← interrupt + checkpointer
                       settings (codice) → synthesize (Gemini) → postprocess (ffmpeg)
```

## 1.5 Quale framework? (e perché LangGraph)

| Strumento | Cos'è | Quando sceglierlo |
|---|---|---|
| **Python puro + SDK** | chiamate dirette alle API | sempre per imparare; ottimo per progetti piccoli |
| **LangChain** | astrazioni comuni: chat model, messaggi, prompt, structured output, fallback | quando vuoi cambiare provider senza riscrivere. Noi lo usiamo *solo* per questo |
| **LangGraph** | grafi di stato con nodi, archi condizionali, checkpoint, interrupt, streaming | orchestrazione controllata, human-in-the-loop, ripresa dopo errori. **La nostra scelta** |
| **deepagents** (LangChain) | agente "pronto" sopra LangGraph: pianificazione (todo), filesystem virtuale, subagenti | compiti lunghi e aperti (ricerca, coding). Qui sarebbe eccessivo: il nostro percorso è fisso |
| **Hermes** | il nome indica sia i modelli Hermes di Nous Research (open, addestrati per function calling) sia il loro framework di agente "Hermes Agent" | se vuoi un assistente personale autonomo con memoria e strumenti; utile da confrontare, non adatto a una pipeline fissa |
| Altri: CrewAI, AutoGen/AG2, OpenAI Agents SDK, Claude Agent SDK, PydanticAI | agenti "a ruoli" o loop agentici gestiti | quando il problema è davvero agentico; leggete il codice che generano prima di adottarli |

Perché LangGraph qui: ci dà **gratis** tre cose che altrimenti scriveremmo a mano e male:
stato tipizzato condiviso tra i nodi, *checkpoint* (per fermarsi e riprendere quando l'utente rivede il testo),
e archi condizionali (per il ciclo di auto-correzione). E non ci obbliga a usare un LLM per orchestrare.

## Verifica (5 min)

Rispondete in coppia:

1. Perché il subagente "settings" non usa un LLM?
2. Cosa succederebbe se l'orchestratore fosse un LLM che sceglie il prossimo passo?
3. Qual è l'unico punto dove l'LLM è indispensabile?
