# Modulo 3 · Il subagente formatter (30 min)

**Concetto:** un subagente LLM con un compito stretto: prompt di sistema, output strutturato,
controlli nel codice, e messaggi per l'auto-correzione.
**Costruiamo:** `app/formatter.py`.
**Prerequisiti:** moduli 1 e 2 (`app/config.py`, `app/llm.py`, `app/schemas.py`).

## 3.1 Due livelli di regia

Gemini TTS legge `text` parola per parola e separa due livelli
([prompting guide](https://aistudio.google.com/docs/speech-generation?codelanguage=python)):

| Livello | Dove va | Esempi |
|---|---|---|
| sostenuto, vale per tutto il turno: emozione, ritmo, tono, intonazione | `style` → `speech_metadata.style` | `"speaking slowly"`, `"whispers"`, `"sarcastic"`, `"high pitch, excited"` |
| puntuale, in un punto preciso del testo | dentro `text`, tra `<...>`, in inglese | `<sigh>`, `<breath>`, `<laugh>`, `<short pause>`, `<long pause>` |

Più tre strumenti nel testo stesso: punteggiatura e puntini per le esitazioni, MAIUSCOLO per l'enfasi,
`|reazione|` per le brevi reazioni di chi ascolta in un dialogo. Se l'emozione cambia a metà, si divide
in due turni.

## 3.2 Il codice

`app/formatter.py`

```python
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
```

**Il prompt.** Compito in una riga, formato d'uscita esplicito, regole numerate e raggruppate, esempi
concreti dentro le regole. Un modello piccolo come Qwen 9B ignora le indicazioni vaghe ("dove serve"):
le regole 6 e 8 sono scritte come **obblighi verificabili**, e il prompt dice che verranno controllate.

**`check_delivery`.** Ogni istruzione importante del prompt dovrebbe avere un controllo nel codice,
altrimenti non sapete se il modello la rispetta. Il controllo sta qui e non nello schema perché lo schema
vale anche per il copione che **voi** modificherete: se togliete un maiuscolo, va bene così.

**`build_messages` con `error`.** Se la risposta non va, la rimandiamo al modello insieme all'errore:
è l'**auto-correzione**. Funziona bene perché gli errori di Pydantic sono precisi. Il ciclo "riprova al
massimo 3 volte" lo costruiremo nel grafo (modulo 6), dove ogni tentativo resta visibile.

## Verifica

Salvate questo file come `prove/m03_formatter.py`:

```python
from app.config import get_settings
from app.llm import formatter_model
from app.formatter import build_messages, parse_script
text = 'Marco: Ho finito il lavoro, era il 50% del progetto!\nGiulia: Davvero? Che sollievo.'
messages = build_messages(text)
raw = formatter_model(get_settings()).invoke(messages).content
print(raw)
try:
    print(parse_script(raw))
except ValueError as e:
    print('SCARTATO:', e)
    raw2 = formatter_model(get_settings()).invoke(build_messages(text, raw, str(e))).content
    print('SECONDO TENTATIVO:', parse_script(raw2))
```

ed eseguitelo dalla cartella del progetto:

```bash
uv run python -m prove.m03_formatter
```

Esercizio: formattate un'intervista scritta con i trattini (`— Come sta? — Bene.`) e un brano emotivo.
Guardate dove il modello mette tag, maiuscole e cambi di `style`. Togliete la regola 9 dal prompt e
osservate cosa cambia nei dialoghi.

> **Cosa guardare su LangSmith:** la chiamata al modello mostra il prompt di sistema esattamente come
> arriva a Qwen. Se c'è stato un secondo tentativo, i suoi messaggi includono la risposta sbagliata e l'errore.
