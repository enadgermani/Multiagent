# Corso: un'architettura multi-agent in produzione a casa

**Durata:** 4 ore · **Pubblico:** sviluppatori che scrivono Python ma non hanno mai costruito con l'AI
**Risultato:** alla fine ognuno ha sul proprio computer *Voce Agenti*, un'app web che trasforma un
testo grezzo in audio italiano a una o più voci, con un modello locale (Qwen via Ollama), uno remoto
(DeepSeek) e un modello di sintesi vocale cloud (Gemini TTS), coordinati da un grafo LangGraph.

## Il filo conduttore

Il corso non insegna "a usare un framework". Insegna a **decidere**:

1. dove serve un LLM e dove basta il codice;
2. quale modello usare per quale compito (locale, remoto, specializzato);
3. come far collaborare più componenti senza perdere il controllo (orchestrazione);
4. dove mettere l'essere umano (human-in-the-loop);
5. come rendere tutto testabile, osservabile ed economico.

## Agenda

| Ora | Modulo | Tipo |
|---|---|---|
| 0:00 – 0:30 | [1. Concetti: LLM, agenti, workflow, framework](01-concetti.md) | teoria + demo |
| 0:30 – 1:10 | [2. Modelli locali e remoti dietro un'unica interfaccia](02-modelli.md) | lab |
| 1:10 – 1:55 | [3. Il primo subagente: il formatter](03-formatter.md) | lab |
| 1:55 – 2:05 | Pausa | |
| 2:05 – 2:55 | [4. L'orchestratore con LangGraph](04-orchestratore.md) | lab |
| 2:55 – 3:30 | [5. Subagente settings, Gemini TTS e audio](05-tts-audio.md) | lab |
| 3:30 – 4:00 | [6. Web, produzione a casa, e cosa fare dopo](06-produzione.md) | lab + chiusura |

## Prima del corso (30 minuti, a casa)

- Python 3.11+, [uv](https://docs.astral.sh/uv/) (o pip), `ffmpeg`, git.
- [Ollama](https://ollama.com) e un modello Qwen da 7-9B: `ollama pull qwen3.5:9b`
  (con 8 GB di VRAM va bene un 7-9B quantizzato a 4 bit; senza GPU funziona ma è lento:
  in quel caso userete DeepSeek).
- Una chiave Gemini da [Google AI Studio](https://aistudio.google.com/apikey).
- Facoltativa: una chiave [DeepSeek](https://platform.deepseek.com).

Verifica: `ollama run qwen3.5:9b "Dimmi ciao in tre lingue"` risponde, `ffmpeg -version` funziona.

## Come usare il codice

Il repository contiene la soluzione completa. Ogni modulo indica i file da scrivere; chi resta
indietro può copiare il file di riferimento e proseguire. I test (`uv run pytest`) servono da
"semaforo" alla fine di ogni lab.

Suggerimento per chi conduce: create un branch `inizio` con solo `pyproject.toml`, `.env.example`,
`app/config.py`, `app/schemas.py` vuoto e `static/`; i partecipanti partono da lì.
