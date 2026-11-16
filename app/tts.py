"""Client Gemini TTS (e un sostituto finto per i test).

Gemini TTS NON è un agente: è uno *strumento* (tool) deterministico dal punto di
vista dell'architettura. Riceve un payload, restituisce audio. Lo isoliamo
dietro un'interfaccia minima (`synthesize(payload) -> wav bytes`) così possiamo
sostituirlo nei test e, un domani, con un altro motore TTS.

Formato restituito da Gemini (richieste non in streaming): WAV, 24 kHz, mono, 16 bit.
"""

import base64
import io
import math
import struct
import wave
from concurrent.futures import ThreadPoolExecutor
from typing import Protocol

from .config import Settings

SAMPLE_RATE = 24_000


class TTSClient(Protocol):
    def synthesize(self, payload: dict) -> bytes: ...


class GeminiTTS:
    def __init__(self, api_key: str):
        from google import genai

        # L'API "interactions" è in v1beta al momento della scrittura.
        self.client = genai.Client(api_key=api_key, http_options={"api_version": "v1beta"})

    def synthesize(self, payload: dict) -> bytes:
        interaction = self.client.interactions.create(**payload)
        data = interaction.output_audio.data
        raw = base64.b64decode(data) if isinstance(data, str) else data
        # Per sicurezza: se arrivasse PCM senza header RIFF, lo incapsuliamo noi.
        return raw if raw[:4] == b"RIFF" else pcm_to_wav(raw)


class FakeTTS:
    """Genera un 'bip' la cui durata è proporzionale al testo. Zero costi."""

    def __init__(self):
        self.calls: list[dict] = []

    def synthesize(self, payload: dict) -> bytes:
        self.calls.append(payload)
        chars = sum(len(c["text"]) for c in payload["input"][0]["content"])
        seconds = min(0.2 + chars / 40, 10)
        n = int(SAMPLE_RATE * seconds)
        pcm = b"".join(
            struct.pack("<h", int(6000 * math.sin(2 * math.pi * 330 * i / SAMPLE_RATE)))
            for i in range(n)
        )
        return pcm_to_wav(pcm)


def make_tts(s: Settings) -> TTSClient:
    if s.tts_backend == "fake":
        return FakeTTS()
    if s.gemini_api_key is None:
        raise RuntimeError("GEMINI_API_KEY non impostata (vedi .env.example)")
    return GeminiTTS(s.gemini_api_key.get_secret_value())


def synthesize_all(client: TTSClient, payloads: list[dict], max_workers: int = 4) -> list[bytes]:
    """Esegue più richieste in parallelo mantenendo l'ordine (fan-out / fan-in)."""
    if len(payloads) == 1:
        return [client.synthesize(payloads[0])]
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return list(pool.map(client.synthesize, payloads))


# ---------------------------------------------------------------- utilità WAV
def pcm_to_wav(pcm: bytes, rate: int = SAMPLE_RATE) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def concat_wavs(wavs: list[bytes], gap_ms: int = 250) -> bytes:
    """Concatena WAV mono 16 bit inserendo una breve pausa tra i pezzi."""
    frames, rate = [], SAMPLE_RATE
    for i, w in enumerate(wavs):
        with wave.open(io.BytesIO(w)) as r:
            rate = r.getframerate()
            if i:
                frames.append(b"\x00\x00" * int(rate * gap_ms / 1000))
            frames.append(r.readframes(r.getnframes()))
    return pcm_to_wav(b"".join(frames), rate)
