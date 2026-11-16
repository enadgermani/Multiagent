"""Strumenti (non agenti): Gemini TTS e ffmpeg."""

import base64
import subprocess

from google import genai


def synthesize(api_key: str, request: dict) -> bytes:
    """Chiama Gemini TTS e restituisce un WAV (24 kHz, mono, 16 bit)."""
    client = genai.Client(api_key=api_key, http_options={"api_version": "v1beta"})
    interaction = client.interactions.create(**request)
    return base64.b64decode(interaction.output_audio.data)


def ffmpeg(wav: bytes, speed: float, pitch: float, fmt: str) -> bytes:
    """Gemini non ha parametri di velocità e pitch: li applichiamo noi.

    - pitch: asetrate alza/abbassa il tono (ma cambia anche la durata),
      poi aresample torna a 24 kHz e atempo ricompensa la durata
    - velocità: atempo cambia la durata senza toccare il tono
    """
    ratio = 2 ** (pitch / 12)
    filters = f"asetrate={24000 * ratio:.0f},aresample=24000,atempo={1 / ratio:.4f},atempo={speed}"
    codec = ["-codec:a", "libmp3lame", "-b:a", "128k"] if fmt == "mp3" else []
    result = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-af", filters, *codec, "-f", fmt, "pipe:1"],
        input=wav, capture_output=True, check=True,
    )
    return result.stdout
