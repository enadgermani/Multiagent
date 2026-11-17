# Modulo 2 · Contratti tra componenti (15 min)

**Concetto:** i componenti si passano **oggetti tipizzati**, non testo libero. Lo schema è il contratto,
e gli errori emergono nel punto in cui nascono.
**Costruiamo:** `app/schemas.py`.
**Prerequisiti:** modulo 0 (questo file non dipende da altri).

## 2.1 Lo schema

`app/schemas.py`

```python
"""I contratti tra gli agenti: oggetti tipizzati, non testo libero."""

import re

from pydantic import BaseModel, Field, field_validator, model_validator

# Le 30 voci predefinite di Gemini TTS (nome: carattere). Sono timbri, non lingue.
VOICES = {
    "Zephyr": "Bright", "Puck": "Upbeat", "Charon": "Informative", "Kore": "Firm",
    "Fenrir": "Excitable", "Leda": "Youthful", "Orus": "Firm", "Aoede": "Breezy",
    "Callirrhoe": "Easy-going", "Autonoe": "Bright", "Enceladus": "Breathy", "Iapetus": "Clear",
    "Umbriel": "Easy-going", "Algieba": "Smooth", "Despina": "Smooth", "Erinome": "Clear",
    "Algenib": "Gravelly", "Rasalgethi": "Informative", "Laomedeia": "Upbeat", "Achernar": "Soft",
    "Alnilam": "Firm", "Schedar": "Even", "Gacrux": "Mature", "Pulcherrima": "Forward",
    "Achird": "Friendly", "Zubenelgenubi": "Casual", "Vindemiatrix": "Gentle", "Sadachbia": "Lively",
    "Sadaltager": "Knowledgeable", "Sulafat": "Warm",
}


# Tag vocali in linea ammessi da Gemini TTS (prompting guide, sempre in inglese anche per testi italiani).
VOCAL_TAGS = {
    "argh", "breath", "heavy breath", "exhales", "cackle", "cheer", "chuckle", "chuckles", "cough",
    "cry", "gasp", "giggle", "groan", "growl", "grunt", "grr", "hiss", "laugh", "laughter", "moan",
    "pant", "pff", "phew", "scream", "shout", "shriek", "sigh", "sighs", "sneeze", "snicker", "snort",
    "sob", "throat-clearing", "tsk", "whimper", "whispers", "whispering", "yawn", "short pause", "long pause",
}


class Turn(BaseModel):
    speaker: str
    text: str            # trascrizione LETTA parola per parola; può contenere tag <...> e |reazioni|
    style: str = ""      # recitazione sostenuta per tutto il turno (in inglese): finisce in speech_metadata.style

    @field_validator("text")
    @classmethod
    def known_tags(cls, text: str) -> str:
        unknown = {t for t in re.findall(r"<([^<>]+)>", text) if t.strip().lower() not in VOCAL_TAGS}
        if unknown:
            raise ValueError(f"tag non ammessi: {sorted(unknown)}. Usa solo: {sorted(VOCAL_TAGS)}")
        return text


class Script(BaseModel):
    """Output del formatter, input della revisione umana."""

    speakers: list[str] = Field(min_length=1, max_length=2)  # Gemini: max 2 voci per richiesta
    turns: list[Turn] = Field(min_length=1)

    @model_validator(mode="after")
    def speakers_declared(self):
        unknown = {t.speaker for t in self.turns} - set(self.speakers)
        if unknown:
            raise ValueError(f"battute con speaker non dichiarati: {sorted(unknown)}")
        return self


class VoiceOptions(BaseModel):
    """Scelte dell'utente nell'interfaccia."""

    voices: dict[str, str] = {}                     # speaker -> voce Gemini
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    pitch: float = Field(default=0.0, ge=-6, le=6)  # semitoni
```

Ogni riga incorpora una decisione:

- `text` e `style` sono separati perché Gemini TTS legge `text` **parola per parola**: le indicazioni di
  recitazione stanno in `style`, che finirà in un campo diverso della richiesta (modulo 5).
- `known_tags` accetta solo i tag vocali previsti da Gemini (`<sigh>`, `<short pause>`...). Il messaggio
  d'errore elenca quelli validi: tornerà utile quando a sbagliare sarà un modello (modulo 3).
- `max_length=2` porta nello schema un limite di Gemini (al massimo 2 voci per richiesta).
- `speakers_declared` controlla la coerenza tra campi: un modello piccolo può dichiarare `Marco` e poi
  scrivere una battuta di `Marco Rossi`.
- `VoiceOptions` ha limiti (`ge`, `le`): un valore fuori scala viene rifiutato, da qualunque parte arrivi.

## Verifica

Salvate questo file come `prove/m02_contratti.py`:

```python
from app.schemas import Script
ok = Script.model_validate({'speakers': ['Marco'], 'turns': [{'speaker': 'Marco', 'text': 'Ciao <sigh> a tutti'}]})
print('valido:', ok.turns[0].text)
try:
    Script.model_validate({'speakers': ['Marco'], 'turns': [{'speaker': 'Giulia', 'text': 'Ciao <door slam>'}]})
except ValueError as e:
    print(e)
```

ed eseguitelo dalla cartella del progetto:

```bash
uv run python -m prove.m02_contratti
```

Il secondo esempio produce **due** errori, entrambi leggibili: tag non ammesso e speaker non dichiarato.
