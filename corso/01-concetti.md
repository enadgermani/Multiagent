# Modulo 1 · Concetti e scelta del framework (30 min)

## 1.1 Un LLM, visto da un programmatore

```python
def llm(messaggi: list[Messaggio], temperatura: float) -> Messaggio: ...
```

- Riceve una lista di messaggi: `system` (ruolo e regole), `user`, `assistant`.
- Genera testo un *token* alla volta (circa ¾ di parola), scegliendo con una certa casualità:
  la **temperatura** regola quanta. Bassa (0–0.3) per compiti precisi, alta per compiti creativi.
- Non ricorda nulla tra una chiamata e l'altra: sa solo quello che c'è nei messaggi (il **contesto**).
- Può sbagliare formato, ignorare una regola, inventare. Buona parte del progetto serve a gestire questo.

Prova:

```bash
ollama run qwen3.5:9b "Riscrivi per la lettura ad alta voce: 'Il 3,5% del PIL (dati ISTAT) ecc.'"
```

Lanciatelo tre volte: le risposte cambiano.

## 1.2 Agente, subagente, workflow

- **Agente**: un LLM in un ciclo. Riceve un obiettivo e degli strumenti, decide quale usare, legge il
  risultato, decide il passo successivo, finché non ha finito. *È l'LLM a scegliere il percorso.*
- **Subagente**: un componente con un compito stretto, chiamato da un altro. Prompt corto, contesto
  pulito, può girare su un modello piccolo.
- **Workflow**: i passi e il loro ordine sono scritti nel codice. *È il programmatore a scegliere il percorso.*
- **Orchestrazione**: il pezzo che coordina tutto e passa i dati da un componente all'altro.

Regola pratica: un LLM serve dove c'è da **capire il linguaggio**; dove ci sono **regole** basta il codice.
E l'orchestrazione è un workflow ogni volta che i passi sono sempre gli stessi.

## 1.3 Il progetto

```
Browser ─► FastAPI ─► grafo LangGraph

  formatter (LLM) ─► validate ─┬─ errore: riprova (max 3)
                               └─ ok ─► human_review ⏸ ─► settings ─► tts ─► WAV + MP3
```

| Componente | Tipo | Perché |
|---|---|---|
| orchestratore (`graph.py`) | workflow | i passi sono sempre gli stessi, nello stesso ordine |
| formatter | subagente **LLM** | capire chi parla e riscrivere "per l'orecchio" richiede comprensione del linguaggio |
| validate | codice | controllare uno schema è una regola |
| human_review | persona | prima di spendere crediti TTS, l'utente controlla il copione |
| settings | subagente **deterministico** | voci, formato della richiesta, limiti dell'API: tutte regole |
| Gemini TTS, ffmpeg | strumenti | ricevono input, restituiscono audio; non decidono nulla |

## 1.4 Quale framework

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
