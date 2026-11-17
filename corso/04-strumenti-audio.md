# Modulo 4 · Strumenti: Gemini TTS e ffmpeg (20 min)

**Concetto:** uno **strumento** fa una cosa precisa e non decide nulla. Si isola dietro una funzione,
così se l'API cambia si tocca un solo file.
**Costruiamo:** `app/tts.py`.
**Prerequisiti:** modulo 0 (questo file non dipende da altri).

## 4.1 Gemini TTS

Dalla [documentazione](https://aistudio.google.com/docs/speech-generation?codelanguage=python):

- modelli `gemini-3.8-flash-tts` e `gemini-3.8-flash-lite-tts`;
- 30 voci predefinite (Kore, Charon, Aoede, Puck...): sono timbri, la lingua la riconosce dal testo;
- al massimo 2 voci per richiesta;
- restituisce un WAV a 24 kHz, mono, 16 bit;
- **non** ha parametri numerici di velocità o pitch.

## 4.2 Il codice

`app/tts.py`

```python
"""Strumenti (non agenti): Gemini TTS e ffmpeg."""

import base64
import shutil
import subprocess

from google import genai
from langsmith import traceable


# @traceable registra la chiamata su LangSmith (se il tracing è attivo).
# Mostriamo la richiesta JSON completa; dell'audio solo la dimensione, non i byte.
@traceable(
    run_type="tool",
    name="gemini_tts",
    process_inputs=lambda inputs: {"request": inputs["request"]},  # la chiave API non finisce nella trace
    process_outputs=lambda wav: {"wav_bytes": len(wav)},
)
def synthesize(api_key: str, request: dict) -> bytes:
    """Chiama Gemini TTS e restituisce un WAV (24 kHz, mono, 16 bit)."""
    client = genai.Client(api_key=api_key, http_options={"api_version": "v1beta"})
    interaction = client.interactions.create(**request)
    return base64.b64decode(interaction.output_audio.data)


def audio_filter(speed: float, pitch: float) -> str:
    """Gemini non ha parametri di velocità e pitch: li applichiamo noi con ffmpeg.

    - pitch: asetrate alza/abbassa il tono (ma cambia anche la durata),
      poi aresample torna a 24 kHz e atempo ricompensa la durata
    - velocità: atempo cambia la durata senza toccare il tono
    """
    ratio = 2 ** (pitch / 12)
    return f"asetrate={24000 * ratio:.0f},aresample=24000,atempo={1 / ratio:.4f},atempo={speed}"


def ffmpeg(wav: bytes, filters: str, fmt: str) -> bytes:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg non trovato: installalo (Windows: winget install ffmpeg) e riapri il terminale")
    codec = ["-codec:a", "libmp3lame", "-b:a", "128k"] if fmt == "mp3" else []
    result = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-af", filters, *codec, "-f", fmt, "pipe:1"],
        input=wav, capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError("ffmpeg: " + result.stderr.decode(errors="replace"))
    return result.stdout
```

**`@traceable`.** Le chiamate ai modelli LangChain finiscono su LangSmith da sole; questa usa l'SDK di
Google, quindi la decoriamo. `process_inputs` e `process_outputs` decidono cosa registrare: la richiesta
JSON sì, la chiave API e i byte dell'audio no.

**Velocità e pitch.** Gemini non li ha, quindi li applichiamo dopo con ffmpeg:

- `asetrate` fa suonare l'audio come se fosse campionato a un'altra frequenza: il tono sale o scende, ma cambia anche la durata;
- `aresample` riporta a 24 kHz; il primo `atempo` ricompensa la durata, il secondo applica la velocità.

(Un'alternativa per la velocità è chiederla nello `style`, "speaking slowly": più naturale, meno precisa.)

## Verifica

Una richiesta scritta a mano, una voce:

Salvate questo file come `prove/m04_audio.py`:

```python
from app.config import get_settings
from app.tts import synthesize, audio_filter, ffmpeg
request = {
    'model': 'gemini-3.8-flash-tts',
    'input': [{'type': 'user_input', 'content': [{'type': 'text', 'text': 'Buongiorno a TUTTI! <short pause> Iniziamo.',
               'annotations': [{'type': 'speech_metadata', 'style': 'Speak Italian with a native accent. Warm, cheerful.'}]}]}],
    'response_format': {'type': 'audio'},
    'generation_config': {'speech_config': [{'voice': 'Kore'}]},
}
wav = synthesize(get_settings().gemini_api_key.get_secret_value(), request)
open('prova.mp3', 'wb').write(ffmpeg(wav, audio_filter(speed=1.0, pitch=-2), 'mp3'))
print('scritto prova.mp3')
```

ed eseguitelo dalla cartella del progetto:

```bash
uv run python -m prove.m04_audio
```

Ascoltate `prova.mp3`, poi cambiate `pitch` e `speed`.

> **Cosa guardare su LangSmith:** il run `gemini_tts` con la richiesta completa e `wav_bytes` in uscita.
> Guardate la latenza: è quasi sempre il passo più lento del sistema.
