"""Subagente FORMATTER (LLM): testo grezzo -> copione per il TTS.

È l'unico punto del sistema dove serve un LLM: capire chi parla e
riscrivere il testo "per l'orecchio" richiede comprensione del linguaggio.
"""

import json
import re

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
6. OBBLIGATORIO: inserisci DENTRO "text" i tag vocali, tra parentesi angolari, in inglese.
   Scegli quelli adatti al contesto tra questi:
   <breath> <sigh> <laugh> <chuckle> <gasp> <cough> <throat-clearing> <whispering> <yawn>
   <short pause> <long pause>
   Usane ALMENO UNO nel copione, e metti <short pause> o <long pause> tra i passaggi.
   Es. "Ci ho pensato a lungo... <short pause> Va bene, accetto."
7. Pause naturali con virgole, trattini e puntini di sospensione.
8. OBBLIGATORIO: in OGNI frase (tranne quelle di una o due parole) scrivi in MAIUSCOLO la parola
   principale (una, al massimo due).
   Es. "È MOLTO importante!" "Ci vediamo DOMANI alle nove." "Non era mai stato così FELICE."
9. Solo nei dialoghi: brevi reazioni di chi ascolta tra barre verticali dentro il turno di chi parla.
   Es. "Il lancio è GIOVEDÌ |ah sì?| Siamo PRONTI?"

Le regole 6 e 8 vengono controllate: se mancano, la risposta viene scartata."""


def build_messages(text: str, previous: str | None = None, error: str | None = None) -> list:
    messages = [SystemMessage(SYSTEM_PROMPT), HumanMessage(text)]
    if error:
        # Auto-correzione: rimandiamo al modello la sua risposta e l'errore.
        messages += [AIMessage(previous), HumanMessage(f"Risposta non valida: {error}\nCorreggi e rispondi solo con il JSON.")]
    return messages


def check_delivery(script: Script) -> None:
    """Regole di recitazione chieste al formatter (6 e 8 del prompt).

    Stanno qui e non nello schema: valgono per l'output del modello, non per le
    modifiche che fai tu nella revisione.
    """
    if not any(re.search(r"<[^<>]+>", t.text) for t in script.turns):
        raise ValueError("nessun tag vocale nel copione: aggiungine almeno uno (es. <short pause>, <sigh>)")
    for t in script.turns:
        # una "frase" finisce con . ! ? o …; tag e |reazioni| non contano;
        # le frasi brevissime ("Ah...", "Sì!") sono esentate
        for sentence in re.split(r"(?<=[.!?…])\s+", re.sub(r"<[^<>]+>|\|[^|]*\|", "", t.text)):
            if len(sentence.split()) >= 3 and not re.search(r"\b[A-ZÀ-Ý]{2,}\b", sentence):
                raise ValueError(f"frase senza parola in MAIUSCOLO: \"{' '.join(sentence.split())}\"")


def parse_script(raw: str) -> Script:
    """Solleva ValueError (con un messaggio utile per il modello) se l'output non va bene."""
    try:
        script = Script.model_validate(json.loads(raw))
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON non valido: {e}") from e
    check_delivery(script)
    return script
