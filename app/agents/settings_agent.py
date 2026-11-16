"""Subagente SETTINGS: (Script + scelte utente) -> TTSPlan.

Lezione importante: questo "agente" NON usa un LLM. Ha un ruolo preciso
nell'architettura (traduce intenzioni in una richiesta API valida), ma ogni
sua decisione è deterministica e verificabile con un test. Usare un LLM qui
renderebbe il sistema più lento, più costoso e meno prevedibile.

Regola pratica: LLM dove serve *giudizio sul linguaggio*, codice dove servono
*regole*. Un'architettura multi-agent ben fatta è un mix dei due.
"""

from ..schemas import Script, TTSPlan, VoiceOptions
from ..voices import DEFAULT_VOICE, MAX_SPEAKERS_PER_CALL, VOICES

# Ordine di casting automatico: alterna registri per distinguere i parlanti.
CASTING_ORDER = ["Charon", "Aoede", "Puck", "Leda", "Orus", "Sulafat", "Iapetus", "Despina"]
MAX_CHARS_PER_REQUEST = 3_500  # oltre, spezziamo in più richieste e concateniamo

ITALIAN_DIRECTION = "Speak Italian with a natural, native accent from Italy."


def cast_voices(speakers: list[str], chosen: dict[str, str]) -> dict[str, str]:
    """Assegna una voce a ogni speaker: rispetta le scelte valide dell'utente,
    riempie il resto con voci non ancora usate."""
    result: dict[str, str] = {}
    for sp in speakers:
        v = chosen.get(sp)
        if v in VOICES:
            result[sp] = v
    pool = [v for v in CASTING_ORDER if v not in result.values()]
    pool += [v for v in VOICES if v not in result.values() and v not in pool]
    for sp in speakers:
        if sp not in result:
            result[sp] = pool.pop(0) if pool else DEFAULT_VOICE
    return result


def pace_direction(speed: float) -> str:
    """Traduce la velocità numerica in linguaggio naturale per il prompt di stile."""
    if speed <= 0.7:
        return "very slow pace, deliberate"
    if speed <= 0.9:
        return "slightly slow pace"
    if speed >= 1.5:
        return "very fast pace"
    if speed >= 1.15:
        return "slightly fast pace"
    return ""


def _style(turn_style: str, opts: VoiceOptions) -> str:
    parts = [ITALIAN_DIRECTION, turn_style, opts.global_style]
    if opts.speed_method == "prompt":
        parts.append(pace_direction(opts.speed))
    return " ".join(p.strip().rstrip(".") + "." for p in parts if p and p.strip())


def _payload(model: str, turns, voices: dict[str, str], opts: VoiceOptions, multi: bool) -> dict:
    content = []
    for t in turns:
        ann = {"type": "speech_metadata", "style": _style(t.style, opts)}
        if multi:
            ann["speaker"] = t.speaker
        content.append({"type": "text", "text": t.text, "annotations": [ann]})
    if multi:
        used = list(dict.fromkeys(t.speaker for t in turns))
        speech_config = {"speakers": [{"speaker": s, "voice": voices[s]} for s in used]}
    else:
        speech_config = [{"voice": voices[turns[0].speaker]}]
    return {
        "model": model,
        "input": [{"type": "user_input", "content": content}],
        "response_format": {"type": "audio"},
        "generation_config": {"speech_config": speech_config},
    }


def _chunks(turns, limit: int):
    """Raggruppa battute consecutive finché non si supera `limit` caratteri."""
    chunk, size = [], 0
    for t in turns:
        if chunk and size + len(t.text) > limit:
            yield chunk
            chunk, size = [], 0
        chunk.append(t)
        size += len(t.text)
    if chunk:
        yield chunk


def plan_tts(script: Script, opts: VoiceOptions, model: str) -> TTSPlan:
    voices = cast_voices(script.speakers, opts.voices)
    why: list[str] = []
    n = len(script.speakers)

    if n == 1:
        strategy = "single_call"
        reqs = [_payload(model, c, voices, opts, multi=False)
                for c in _chunks(script.turns, MAX_CHARS_PER_REQUEST)]
        why.append(f"Una voce ({voices[script.speakers[0]]}): richiesta single-speaker.")
    elif n <= MAX_SPEAKERS_PER_CALL:
        strategy = "two_speaker_call"
        reqs = [_payload(model, c, voices, opts, multi=True)
                for c in _chunks(script.turns, MAX_CHARS_PER_REQUEST)]
        why.append("Due voci: Gemini le gestisce nativamente in una sola richiesta multi-speaker.")
    else:
        strategy = "per_turn_calls"
        reqs = [_payload(model, [t], voices, opts, multi=False) for t in script.turns]
        why.append(
            f"{n} voci: Gemini ne accetta al massimo {MAX_SPEAKERS_PER_CALL} per richiesta, "
            "quindi sintetizzo ogni battuta separatamente (in parallelo) e concateno l'audio."
        )
    if len(reqs) > 1 and strategy != "per_turn_calls":
        why.append(f"Testo lungo: diviso in {len(reqs)} richieste da max {MAX_CHARS_PER_REQUEST} caratteri.")

    post_speed = opts.speed if opts.speed_method == "dsp" else 1.0
    if opts.speed_method == "prompt" and abs(opts.speed - 1) > 0.1:
        why.append(f"Velocità {opts.speed}x chiesta a parole nello stile ('{pace_direction(opts.speed)}'): "
                   "naturale ma approssimata.")
    elif abs(post_speed - 1) > 0.01:
        why.append(f"Velocità {post_speed}x applicata in post-produzione (time-stretch): precisa.")
    if abs(opts.pitch) > 0.01:
        why.append(f"Pitch {opts.pitch:+} semitoni in post-produzione: Gemini non ha un parametro pitch.")

    return TTSPlan(model=model, strategy=strategy, voices=voices, requests=reqs,
                   post={"speed": post_speed, "pitch": opts.pitch}, explanation=why)
