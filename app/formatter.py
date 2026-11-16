"""Subagente FORMATTER (LLM): testo grezzo -> copione per il TTS.

È l'unico punto del sistema dove serve un LLM: capire chi parla e
riscrivere il testo "per l'orecchio" richiede comprensione del linguaggio.
"""

import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from .schemas import Script

SYSTEM_PROMPT = """Prepari testi italiani per la sintesi vocale.
Restituisci SOLO un oggetto JSON con questo schema:

{"speakers": ["Nome1"], "turns": [{"speaker": "Nome1", "text": "...", "style": "..."}]}

Regole:
1. "text" resta in italiano e fedele al testo originale: non riassumere, non inventare.
2. Scrivi per l'orecchio: togli markdown, URL ed emoji; sciogli simboli e abbreviazioni
   ("%" -> "per cento", "ecc." -> "eccetera").
3. Se il testo è un dialogo, usa un nome per ogni parlante (massimo 2).
   Altrimenti un solo speaker: "Narratore".
4. "style" è una breve indicazione di recitazione in inglese, es. "calm, warm narration".
   Non mettere indicazioni di regia dentro "text": verrebbero lette ad alta voce."""


def build_messages(text: str, previous: str | None = None, error: str | None = None) -> list:
    messages = [SystemMessage(SYSTEM_PROMPT), HumanMessage(text)]
    if error:
        # Auto-correzione: rimandiamo al modello la sua risposta e l'errore.
        messages += [AIMessage(previous), HumanMessage(f"Risposta non valida: {error}\nCorreggi e rispondi solo con il JSON.")]
    return messages


def parse_script(raw: str) -> Script:
    """Solleva ValueError (con un messaggio utile per il modello) se l'output non va bene."""
    try:
        return Script.model_validate(json.loads(raw))
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON non valido: {e}") from e
