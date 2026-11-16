# Modulo 5 · Subagente settings, Gemini TTS e audio (35 min)

**File:** `app/settings_agent.py`, `app/tts.py`

## 5.1 Gemini TTS (10 min)

Dalla [documentazione](https://aistudio.google.com/docs/speech-generation?codelanguage=python):

- modelli `gemini-3.8-flash-tts` e `gemini-3.8-flash-lite-tts`;
- 30 voci predefinite (Kore, Charon, Aoede, Puck...): sono timbri, la lingua la riconosce dal testo;
- al massimo 2 voci per richiesta;
- l'espressività si controlla con il campo `style` e con tag nel testo come `<short pause>` o `<laugh>`;
- **non ci sono** parametri numerici di velocità o pitch;
- restituisce un WAV a 24 kHz, mono, 16 bit.

```python
client = genai.Client(api_key=key, http_options={"api_version": "v1beta"})
interaction = client.interactions.create(**request)
wav = base64.b64decode(interaction.output_audio.data)
```

## 5.2 Il subagente settings (15 min)

Riceve il copione e le scelte dell'utente, restituisce la richiesta per Gemini. Ha un ruolo preciso
nell'architettura ma è codice normale: le sue decisioni sono regole.

```python
def build_tts_request(script, opts, model):
    voices = {sp: opts.voices.get(sp) if opts.voices.get(sp) in VOICES else DEFAULT_VOICES[i]
              for i, sp in enumerate(script.speakers)}
    multi = len(script.speakers) == 2

    content = []
    for t in script.turns:
        meta = {"type": "speech_metadata", "style": f"Speak Italian with a native accent. {t.style}"}
        if multi:
            meta["speaker"] = t.speaker
        content.append({"type": "text", "text": t.text, "annotations": [meta]})

    if multi:
        speech_config = {"speakers": [{"speaker": sp, "voice": v} for sp, v in voices.items()]}
    else:
        speech_config = [{"voice": voices[script.speakers[0]]}]
    ...
```

Le regole: una voce valida per ogni parlante, l'italiano sempre richiesto nello stile, il formato
diverso per una o due voci. Un LLM qui sarebbe più lento, più costoso e potrebbe sbagliare il formato.

## 5.3 Velocità e pitch con ffmpeg (10 min)

Gemini non li ha, quindi li applichiamo all'audio dopo la sintesi:

```python
ratio = 2 ** (pitch / 12)   # un semitono = rapporto di frequenza 2^(1/12)
filters = f"asetrate={24000 * ratio:.0f},aresample=24000,atempo={1 / ratio:.4f},atempo={speed}"
```

- `asetrate` fa suonare l'audio come se fosse campionato a un'altra frequenza: il tono sale o scende, ma cambia anche la durata;
- `aresample` riporta a 24 kHz;
- il primo `atempo` ricompensa la durata, il secondo applica la velocità scelta (senza toccare il tono).

Provate da terminale:

```bash
ffmpeg -i in.wav -af "atempo=1.25" veloce.wav
ffmpeg -i in.wav -codec:a libmp3lame -b:a 128k out.mp3
```

Un'alternativa per la velocità è chiederla a Gemini nello `style` ("slow pace"): suona più naturale ma è meno precisa.
