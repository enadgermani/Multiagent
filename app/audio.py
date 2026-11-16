"""Post-produzione audio con ffmpeg: velocità, pitch, conversione MP3.

Perché qui e non nel modello? Gemini TTS non espone parametri numerici per
velocità e intonazione: si possono solo *chiedere a parole* nello stile.
Per un controllo preciso e ripetibile usiamo il DSP classico:

- velocità: filtro `atempo` (time-stretch: cambia durata, non intonazione)
- pitch: filtro `rubberband` se disponibile (alta qualità), altrimenti il trucco
  `asetrate` + `aresample` + `atempo` (cambia intonazione, compensa la durata).
"""

import functools
import shutil
import subprocess

from .tts import SAMPLE_RATE


@functools.cache
def has_rubberband() -> bool:
    if not shutil.which("ffmpeg"):
        return False
    out = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    return " rubberband " in out


def _atempo_chain(factor: float) -> list[str]:
    # atempo accetta 0.5..2.0 per istanza: per valori estremi si concatenano.
    chain = []
    while factor > 2.0:
        chain.append("atempo=2.0")
        factor /= 2.0
    while factor < 0.5:
        chain.append("atempo=0.5")
        factor /= 0.5
    chain.append(f"atempo={factor:.4f}")
    return chain


def build_filter(speed: float, pitch_semitones: float) -> str:
    filters: list[str] = []
    ratio = 2 ** (pitch_semitones / 12)
    if abs(pitch_semitones) > 0.01:
        if has_rubberband():
            filters.append(f"rubberband=pitch={ratio:.5f}")
        else:
            filters += [f"asetrate={SAMPLE_RATE * ratio:.0f}", f"aresample={SAMPLE_RATE}"]
            filters += _atempo_chain(1 / ratio)
    if abs(speed - 1.0) > 0.01:
        filters += _atempo_chain(speed)
    return ",".join(filters)


def _ffmpeg(wav: bytes, args: list[str]) -> bytes:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg non trovato: installalo (apt install ffmpeg / brew install ffmpeg)")
    p = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "pipe:0", *args, "pipe:1"],
        input=wav, capture_output=True, check=False,
    )
    if p.returncode != 0:
        raise RuntimeError("ffmpeg: " + p.stderr.decode(errors="replace")[:500])
    return p.stdout


def postprocess(wav: bytes, speed: float = 1.0, pitch: float = 0.0) -> bytes:
    flt = build_filter(speed, pitch)
    if not flt:
        return wav
    return _ffmpeg(wav, ["-af", flt, "-f", "wav"])


def to_mp3(wav: bytes, bitrate: str = "128k") -> bytes:
    return _ffmpeg(wav, ["-codec:a", "libmp3lame", "-b:a", bitrate, "-f", "mp3"])
