# Modulo 6 · Web, produzione a casa, e cosa fare dopo (30 min)

**Obiettivi:** esporre il grafo via HTTP con un flusso in due fasi; far girare tutto con Docker;
osservare, testare e proteggere il sistema; sapere dove andare dopo.

**File:** `app/main.py`, `static/`, `Dockerfile`, `docker-compose.yml`, `CLAUDE.md`

## 6.1 Un'API in due fasi (8 min)

```
POST /api/format                → crea job_id, il grafo gira fino all'interrupt → copione
POST /api/jobs/{id}/synthesize  → riprende il grafo con copione modificato + impostazioni → URL audio
GET  /api/jobs/{id}/audio.mp3   → file
```

Dettagli che fanno la differenza in produzione:

- Gli endpoint sono `def` (non `async def`): il grafo è sincrono e bloccante, così FastAPI lo esegue in un thread pool senza bloccare il server.
- `job_id` è un UUID esadecimale validato con una regex **prima** di usarlo come nome di file: niente path traversal.
- Lo stato del grafo decide cosa è permesso: `synthesize` su un lavoro non in revisione → fork (modulo 4).
- Il trace degli agenti torna al browser e viene mostrato: è il miglior strumento didattico e di debug che avete.

Il frontend (`static/app.js`) è JavaScript senza framework né build: due `fetch`, un form. Non sa nulla di agenti.

## 6.2 Docker Compose a casa (7 min)

```bash
docker compose up -d
docker compose exec ollama ollama pull qwen3.5:9b
```

- Due servizi: `app` e `ollama`. L'app trova Ollama per nome di servizio (`http://ollama:11434`).
- Le chiavi entrano da `env_file: .env`, **mai** nell'immagine (`COPY` non copia `.env`).
- `127.0.0.1:8000:8000`: l'app è raggiungibile solo dal vostro computer. Non ha login. Per usarla dal
  telefono fuori casa, mettetela dietro una VPN (Tailscale, WireGuard), non esponetela con un port forwarding.
- GPU NVIDIA: togliete il commento al blocco `deploy` (serve `nvidia-container-toolkit`).

## 6.3 Osservabilità, costi, sicurezza (8 min)

**Osservabilità.** Il trace nell'UI basta per un'app personale. Per vedere prompt e risposte complete di
ogni nodo, LangGraph si integra con LangSmith impostando tre variabili (`LANGSMITH_TRACING=true`,
`LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`). Alternativa open source da far girare in casa: Langfuse.
Attenzione: il tracing remoto invia i vostri testi a un servizio esterno.

**Costi.** Il formatter locale è gratis; DeepSeek costa frazioni di centesimo per testo; il costo vero è
il TTS (si paga a token audio generati). Per questo la revisione umana sta *prima* della sintesi, e la
rigenerazione con altre voci non richiama l'LLM.

**Sicurezza.**
- *Prompt injection*: il testo incollato finisce nel prompt del formatter. Se contiene "ignora le istruzioni
  e…", un modello può obbedire. Qui il danno è limitato perché il formatter **non ha strumenti** e il suo
  output è validato da uno schema e rivisto da un umano. Regola generale: più strumenti ha un agente,
  più l'input non fidato è pericoloso.
- Limite di lunghezza dell'input (`MAX_INPUT_CHARS`) contro errori e costi accidentali.
- Le chiavi non si loggano (`SecretStr`), non si committano (`.gitignore`), non entrano nell'immagine.

**Test.** 15 test girano in un secondo senza rete, grazie a `FakeListChatModel` e `FakeTTS`. Un sistema
con LLM senza test con modelli finti è un sistema che non si osa toccare.

## 6.4 L'agente che costruisce l'infrastruttura (4 min)

Ricordate il ruolo 1 dell'idea iniziale? Esiste, ma vive nello **sviluppo**: un agente di coding come
Claude Code, che legge `CLAUDE.md` (comandi, regole, cosa non toccare) e modifica il repository su
richiesta. Esempio di richiesta: *"Aggiungi la persistenza dei lavori con SqliteSaver, con un test che
riavvia il grafo e riprende un lavoro in revisione."* Rivedete sempre il diff e fate girare i test.

## 6.5 Compiti per casa (3 min)

In ordine di difficoltà:

1. **Persistenza**: sostituite `InMemorySaver` con `SqliteSaver` (`langgraph-checkpoint-sqlite`) e verificate che un lavoro in revisione sopravviva al riavvio.
2. **Map-reduce nativo**: riscrivete `per_turn_calls` con l'API `Send` di LangGraph, una istanza del nodo `synthesize_turn` per battuta.
3. **Un vero agente con strumenti**: un nodo "casting" in cui l'LLM riceve lo strumento `list_voices()` e il copione, e sceglie le voci motivando la scelta. Confrontate qualità e costo con il casting deterministico. Ne vale la pena?
4. **Streaming**: usate `graph.stream(..., stream_mode="updates")` e i Server-Sent Events per mostrare nel browser ogni agente mentre lavora.
5. **Valutazione**: trasformate il mini-eval del modulo 3 in un confronto Qwen vs DeepSeek su 20 testi, con tempi e percentuale di successo al primo tentativo.

## Ripasso finale (le 5 decisioni)

1. LLM solo dove serve giudizio linguistico (formatter); codice per le regole (settings, validate).
2. Modello piccolo locale per il compito stretto, remoto come fallback.
3. Orchestrazione come workflow esplicito; autonomia solo se misurabilmente utile.
4. Umano nel punto in cui un errore costa (prima della sintesi).
5. Contratti tipizzati, dipendenze iniettabili, test con modelli finti, trace sempre visibile.
