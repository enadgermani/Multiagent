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
