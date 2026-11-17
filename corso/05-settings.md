# Modulo 5 · Il subagente settings (15 min)

**Concetto:** non tutti gli "agenti" devono usare un LLM. Questo ha un ruolo preciso (tradurre copione e
scelte dell'utente in una richiesta API valida), ma ogni sua decisione è una regola.
**Costruiamo:** `app/settings_agent.py`.
**Prerequisiti:** moduli 2 e 4.

## 5.1 Il codice

`app/settings_agent.py`

```python
"""Subagente SETTINGS: copione + scelte dell'utente -> richiesta per Gemini TTS.

Ha un ruolo da agente ma è codice normale: sono regole, non giudizi,
quindi un LLM qui aggiungerebbe solo costo e imprevedibilità.
"""

from .schemas import VOICES, Script, VoiceOptions

DEFAULT_VOICES = ["Charon", "Aoede"]  # usate se l'utente non sceglie


def build_tts_request(script: Script, opts: VoiceOptions, model: str) -> dict:
    voices = {sp: opts.voices.get(sp) if opts.voices.get(sp) in VOICES else DEFAULT_VOICES[i]
              for i, sp in enumerate(script.speakers)}
    multi = len(script.speakers) == 2

    content = []
    for t in script.turns:
        # Lo style del turno va in speech_metadata, separato dal testo (che è letto verbatim).
        meta = {"type": "speech_metadata", "style": f"Speak Italian with a native accent. {t.style}".strip()}
        if multi:
            meta["speaker"] = t.speaker
        content.append({"type": "text", "text": t.text, "annotations": [meta]})

    if multi:
        speech_config = {"speakers": [{"speaker": sp, "voice": v} for sp, v in voices.items()]}
    else:
        speech_config = [{"voice": voices[script.speakers[0]]}]

    return {
        "model": model,
        "input": [{"type": "user_input", "content": content}],
        "response_format": {"type": "audio"},
        "generation_config": {"speech_config": speech_config},
    }
```

Le regole: una voce valida per ogni parlante (quella scelta, o una predefinita), l'italiano sempre
richiesto nello `style`, formato della richiesta diverso per una o due voci. Un LLM qui sarebbe più lento,
più costoso e potrebbe sbagliare il formato.

## 5.2 La pipeline, a mano

Ora abbiamo tutti i pezzi. Colleghiamoli con del semplice Python:

Salvate questo file come `prove/m05_pipeline.py`:

```python
from app.config import get_settings
from app.llm import formatter_model
from app.formatter import build_messages, parse_script
from app.settings_agent import build_tts_request
from app.schemas import VoiceOptions
from app.tts import synthesize, audio_filter, ffmpeg
s = get_settings()
text = 'Marco: Sai che domani parto per Roma?\nGiulia: Ma dai! Non lo sapevo.'
script = parse_script(formatter_model(s).invoke(build_messages(text)).content)
request = build_tts_request(script, VoiceOptions(voices={'Marco': 'Puck'}), s.tts_model)
print(request['generation_config'])
wav = synthesize(s.gemini_api_key.get_secret_value(), request)
open('dialogo.mp3', 'wb').write(ffmpeg(wav, audio_filter(1.0, 0), 'mp3'))
```

ed eseguitelo dalla cartella del progetto:

```bash
uv run python -m prove.m05_pipeline
```

Funziona, quasi sempre. Se il modello sbaglia formato, lo script si ferma con un errore: rilanciatelo.
E proprio qui sta il punto. Provate a pensare a cosa manca: se il formatter sbaglia, chi riprova? Come mostriamo il
copione all'utente prima di spendere crediti TTS, e come riprendiamo dopo? Dove teniamo lo stato tra
un passo e l'altro? Sono i compiti dell'**orchestratore**.
