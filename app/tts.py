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
