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
