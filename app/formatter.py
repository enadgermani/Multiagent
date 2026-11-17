"""Subagente FORMATTER (LLM): testo grezzo -> copione per il TTS.

È l'unico punto del sistema dove serve un LLM: capire chi parla e
riscrivere il testo "per l'orecchio" richiede comprensione del linguaggio.
"""

import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from .schemas import Script

SYSTEM_PROMPT = """Prepari testi italiani per Gemini TTS, che legge "text" parola per parola.
Restituisci SOLO un oggetto JSON con questo schema:

{"speakers": ["Nome1"], "turns": [{"speaker": "Nome1", "text": "...", "style": "..."}]}

TESTO ("text")
1. Resta in italiano e fedele all'originale: non riassumere, non inventare.
2. Scrivi per l'orecchio: togli markdown, URL ed emoji; sciogli simboli e abbreviazioni
   ("%" -> "per cento", "ecc." -> "eccetera").
3. Niente indicazioni di regia nel testo: verrebbero lette ad alta voce.

PARLANTI
4. Se il testo è un dialogo, un nome per ogni parlante (massimo 2). Altrimenti un solo speaker: "Narratore".

COME RECITARE: due livelli
5. "style" = come suona TUTTO il turno, in inglese: emozione, ritmo, tono, intonazione.
   Es. "calm, warm narration", "speaking slowly", "whispers", "sarcastic", "high pitch, excited".
   Se l'emozione cambia a metà, dividi in due turni con style diversi.
6. Eventi puntuali DENTRO "text", tra parentesi angolari, sempre in inglese, solo questi:
   <breath> <sigh> <laugh> <chuckle> <gasp> <cough> <throat-clearing> <whispering> <yawn>
   <short pause> <long pause> (e pochi altri suoni umani: niente effetti sonori).
   Es. "Ci ho pensato a lungo... <short pause> Va bene, accetto."
7. Pause naturali con virgole, trattini e puntini di sospensione.
8. Enfasi: MAIUSCOLO sulla parola chiave, con parsimonia. Es. "È MOLTO importante!"
9. Solo nei dialoghi: brevi reazioni di chi ascolta tra barre verticali dentro il turno di chi parla.
   Es. "Il lancio è giovedì |ah sì?| Siamo pronti?"

Usa tag, maiuscole e reazioni solo dove il testo li giustifica: meglio pochi che troppi."""


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
