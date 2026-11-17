# Prompt da zero

Questo prompt, dato a un agente di coding (per esempio Claude Code) in una cartella vuota, ricrea l'intero
programma *Voce Agenti*. Non crea il corso. Il risultato atteso è equivalente al codice del repository;
i dettagli (nomi di variabili, formattazione) possono variare.

Prima di lanciarlo: installate `uv`, `ffmpeg` e Ollama con un modello Qwen. Dopo: copiate `.env.example`
in `.env` e inserite le chiavi.

---

```text
Crea da zero, in questa cartella vuota, "Voce Agenti": un'app web personale e didattica che trasforma un
testo in audio italiano a una o due voci con un'architettura multi-agent. Il codice deve restare minimo e
leggibile: è materiale per un corso. Commenti e testi per l'utente in italiano, identificatori in inglese.
Niente test, niente modelli o servizi finti, niente funzioni oltre a quelle descritte.

STACK
- Python 3.13 gestito con uv (pyproject.toml, .python-version = 3.13). Dipendenze: fastapi, uvicorn[standard],
  pydantic-settings, python-dotenv, langgraph, langchain-core, langchain-ollama, langchain-openai, google-genai.
  langsmith arriva con langchain-core.
- Frontend: HTML, CSS e JavaScript senza framework né build, in static/.
- ffmpeg di sistema per l'audio.

FILE E RESPONSABILITÀ
app/config.py
- Settings con pydantic-settings, letto da .env (extra="ignore"). Campi con alias in maiuscolo:
  GEMINI_API_KEY (SecretStr, obbligatoria), TTS_MODEL (default "gemini-3.8-flash-tts"),
  FORMATTER_PROVIDER (Literal "local" | "remote" | "auto", default "auto"), OLLAMA_BASE_URL
  (default http://localhost:11434), OLLAMA_MODEL (default "qwen3.5:9b"), DEEPSEEK_API_KEY (SecretStr opzionale),
  DEEPSEEK_MODEL (default "deepseek-chat"), OUTPUT_DIR (default "output"). get_settings() con lru_cache.
- Chiama load_dotenv() all'import: LangSmith legge LANGSMITH_* da os.environ e pydantic-settings non le esporta.

app/llm.py
- local_model(s, temperature): ChatOllama con format="json", reasoning=False, num_ctx=16384.
- remote_model(s, temperature): ChatOpenAI verso https://api.deepseek.com con
  model_kwargs={"response_format": {"type": "json_object"}}.
- formatter_model(s, temperature=0.2): local, remote, oppure auto = locale con .with_fallbacks([remoto]),
  solo locale se manca la chiave DeepSeek.
- describe(s): stringa leggibile dei modelli in uso, per la pagina.

app/schemas.py
- VOICES: le 30 voci predefinite di Gemini TTS con il loro carattere (Zephyr Bright, Puck Upbeat, Charon
  Informative, Kore Firm, Fenrir Excitable, Leda Youthful, Orus Firm, Aoede Breezy, Callirrhoe Easy-going,
  Autonoe Bright, Enceladus Breathy, Iapetus Clear, Umbriel Easy-going, Algieba Smooth, Despina Smooth,
  Erinome Clear, Algenib Gravelly, Rasalgethi Informative, Laomedeia Upbeat, Achernar Soft, Alnilam Firm,
  Schedar Even, Gacrux Mature, Pulcherrima Forward, Achird Friendly, Zubenelgenubi Casual, Vindemiatrix
  Gentle, Sadachbia Lively, Sadaltager Knowledgeable, Sulafat Warm).
- VOCAL_TAGS: i tag vocali ammessi da Gemini TTS: argh, breath, heavy breath, exhales, cackle, cheer,
  chuckle, chuckles, cough, cry, gasp, giggle, groan, growl, grunt, grr, hiss, laugh, laughter, moan, pant,
  pff, phew, scream, shout, shriek, sigh, sighs, sneeze, snicker, snort, sob, throat-clearing, tsk, whimper,
  whispers, whispering, yawn, short pause, long pause.
- Turn(speaker, text, style=""): text è la trascrizione letta parola per parola; un field_validator rifiuta
  i tag <...> non presenti in VOCAL_TAGS, con un messaggio che elenca quelli validi.
- Script(speakers: 1-2 elementi, turns: almeno 1): un model_validator rifiuta battute con speaker non dichiarati.
- VoiceOptions(voices: dict speaker->voce, speed 0.5-2 default 1, pitch -6..6 semitoni default 0).

app/formatter.py (subagente LLM)
- SYSTEM_PROMPT in italiano. Chiede SOLO un JSON {"speakers": [...], "turns": [{"speaker","text","style"}]}.
  Regole: testo italiano fedele, non riassunto; scritto per l'orecchio (niente markdown, URL, emoji; simboli
  e abbreviazioni sciolti); niente regia nel testo; un nome per parlante nei dialoghi (max 2), altrimenti
  "Narratore"; "style" in inglese per tutto il turno (emozione, ritmo, tono, intonazione; dividere il turno
  se l'emozione cambia); OBBLIGATORIO almeno un tag vocale tra <breath> <sigh> <laugh> <chuckle> <gasp>
  <cough> <throat-clearing> <whispering> <yawn> <short pause> <long pause>, con pause tra i passaggi;
  pause naturali con punteggiatura; OBBLIGATORIO in ogni frase (tranne quelle di una o due parole) la
  parola principale in MAIUSCOLO; nei dialoghi brevi reazioni |così| dentro il turno di chi parla.
  Il prompt avvisa che le regole obbligatorie vengono controllate. Esempi concreti per ogni regola.
- build_messages(text, previous=None, error=None): system + user; se c'è un errore aggiunge la risposta
  precedente (AIMessage) e un messaggio che chiede di correggerla (auto-correzione).
- check_delivery(script): ValueError se non c'è nessun tag <...> nel copione, o se una frase con almeno
  tre parole (tag e |reazioni| esclusi) non ha una parola tutta maiuscola di almeno due lettere.
  Non sta nello schema perché vale solo per l'output del modello, non per le modifiche dell'utente.
- parse_script(raw): json.loads + Script.model_validate + check_delivery; ogni errore come ValueError leggibile.

app/tts.py (strumenti)
- synthesize(api_key, request) -> bytes WAV: google.genai Client(api_key, http_options={"api_version":
  "v1beta"}), client.interactions.create(**request), base64 di interaction.output_audio.data.
  Decorata con langsmith @traceable(run_type="tool", name="gemini_tts") che registra solo la richiesta
  (mai la chiave) e in uscita solo {"wav_bytes": len}.
- audio_filter(speed, pitch): ratio = 2**(pitch/12);
  "asetrate={24000*ratio},aresample=24000,atempo={1/ratio},atempo={speed}".
- ffmpeg(wav, filters, fmt): ffmpeg via stdin/stdout, "mp3" con libmp3lame 128k; errore chiaro se ffmpeg
  manca (su Windows: winget install ffmpeg).

app/settings_agent.py (subagente deterministico, niente LLM)
- build_tts_request(script, opts, model): voce scelta se valida, altrimenti Charon e Aoede; per ogni turno
  un blocco {"type":"text","text":...,"annotations":[{"type":"speech_metadata","style":"Speak Italian with
  a native accent. "+style}]}, con "speaker" nell'annotazione se le voci sono due. speech_config:
  [{"voice": v}] con una voce, {"speakers": [{"speaker": s, "voice": v}, ...]} con due. Richiesta completa:
  {"model", "input": [{"type":"user_input","content": [...]}], "response_format": {"type":"audio"},
  "generation_config": {"speech_config": ...}}.

app/graph.py (orchestratore LangGraph)
- Diagramma in cima al file:
  START → formatter → validate ─┬─ errore (max 3 tentativi) → formatter
                                └─ ok → human_review ⏸ → settings → tts → END
- State (TypedDict): text, temperature, raw, error, attempts, script, options, request, e
  steps: Annotated[list[dict], operator.add], in cui ogni nodo aggiunge {"node", "input"?, "output"} in JSON.
- formatter: crea il modello con la temperatura dello stato, invoca build_messages(text, raw, error);
  nel passo registra modelli (describe), temperatura, messaggi {role, content}, modello che ha risposto
  (response_metadata model_name o model) e risposta grezza.
- validate: parse_script, conta i tentativi, salva script o error.
- arco condizionale: ok → human_review; errore → formatter se attempts < 3, altrimenti END.
- human_review: interrupt(script); la risposta può essere vuota o non dict (= approva così com'è) oppure
  {"script"?, "options"?}: le chiavi mancanti prendono lo stato / i default. Rivalida con Script e VoiceOptions.
- settings: build_tts_request; tts: synthesize, audio_filter, scrive OUTPUT_DIR/{thread_id}.wav e .mp3.
- build_graph(settings, checkpointer=None) restituisce il grafo compilato.

app/main.py (FastAPI)
- Grafo con InMemorySaver. job_config(job_id, run_name) = configurable.thread_id, run_name, metadata.thread_id.
- GET /api/voices; GET /api/graph → {"mermaid": graph.get_graph().draw_mermaid()}.
- POST /api/format {text, temperature 0-1.5 default 0.2}: nuovo job_id (uuid hex), invoke fino
  all'interrupt; 422 con i passi se dopo 3 tentativi non c'è un copione valido; 502 leggibile se il
  modello non risponde. Risposta: script, job_id, next, steps.
- POST /api/synthesize/{job_id} {script, options}: se il lavoro non è fermo su human_review ma ha già un
  copione, lo riporta alla revisione con update_state(..., {"error": None, "steps": [passo "rewind"]},
  as_node="validate") seguito da invoke(None) (time travel, nessuna nuova chiamata al modello); poi
  Command(resume=...). Risposta: url wav e mp3, job_id, next, steps. 502 leggibile in caso di errore.
- GET /api/audio/{job_id}.{wav|mp3}: job_id validato con uuid.UUID (niente path traversal).
- Endpoint sincroni (def). Monta static/ su "/".

static/ (index.html, style.css, app.js come modulo ES)
- Responsiva, chiaro/scuro con prefers-color-scheme. Due colonne su schermi larghi (sopra i 1000px), una su mobile.
- Colonna app: 1. testo + slider temperatura (0-1.5, mostra il valore) + "Formatta"; 2. revisione: per
  ogni battuta parlante, style e textarea modificabile; 3. una select di voce per parlante (Charon e Aoede
  preselezionate) + slider velocità e pitch con valore mostrato + "Genera audio"; 4. player e "Scarica MP3".
  "Genera audio" si può premere più volte con impostazioni diverse.
- Colonna "Dietro le quinte": il grafo da /api/graph disegnato con Mermaid 11.4.1 importato dinamicamente
  da cdn.jsdelivr.net (se non si carica l'app funziona lo stesso, con un messaggio); nodi eseguiti in
  verde, nodo in attesa in giallo. Sotto, un <details> per passo con etichetta per nodo; il passo
  formatter mostra modelli, temperatura, chi ha risposto, ogni messaggio come testo leggibile e la
  risposta grezza; gli altri il loro JSON. Mostra i passi anche quando la risposta è un errore.
- Errori del server mostrati in modo leggibile anche se la risposta non è JSON. Testi inseriti nell'HTML
  sempre con escape. Cache del browser evitata sul player (query string) e sui file statici (?v=).

valuta_modelli.py
- Crea su LangSmith (se non esiste) il dataset "formatter-it" con 5 testi italiani di prova (simboli e
  URL, markdown, dialogo con "Nome:", intervista con trattini, brano letterario) e lancia evaluate() per
  Qwen e, se c'è la chiave, DeepSeek, con valutatori valid_schema (parse_script), no_symbols
  (niente % € http ** #), not_summarized (testo in uscita almeno l'80% dell'entrata).

Altri file
- .env.example con tutte le variabili sopra, commentate, più LANGSMITH_TRACING, LANGSMITH_API_KEY,
  LANGSMITH_PROJECT=voce-agenti e LANGSMITH_ENDPOINT commentato per la regione europea.
- .gitignore: .env, .venv/, __pycache__/, output/.
- requirements.txt, Dockerfile (python:3.12-slim + ffmpeg, uvicorn su 0.0.0.0:8000) e docker-compose.yml
  con servizi app e ollama, env_file .env, OLLAMA_BASE_URL=http://ollama:11434, porta 127.0.0.1:8000,
  volume per output e per i modelli Ollama, blocco GPU NVIDIA commentato.
- app/studio.py + langgraph.json per LangGraph Studio (grafo compilato senza checkpointer).
- CLAUDE.md con comandi e regole: mai leggere o committare .env; ogni nuovo nodo aggiorna il diagramma
  e scrive in steps; gli agenti si passano oggetti Pydantic; niente LLM dove basta il codice; bind 127.0.0.1.
- README.md: cosa fa, architettura, tabella file → ruolo, avvio (uv sync; uv run uvicorn app.main:app),
  Docker, LangSmith, limiti (max 2 voci; velocità e pitch via ffmpeg; lavori in memoria).

VERIFICA PRIMA DI CONSEGNARE
- uv sync e import di app.main senza errori.
- Con il server avviato, in un browser: Formatta → grafo fermo su human_review → Genera audio → audio
  riproducibile → cambio pitch e nuova generazione senza nuova chiamata al modello (passo "rewind").
```
