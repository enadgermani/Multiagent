"""I contratti tra gli agenti: oggetti tipizzati, non testo libero."""

from pydantic import BaseModel, Field, model_validator

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


class Turn(BaseModel):
    speaker: str
    text: str            # viene LETTO così com'è
    style: str = ""      # come leggerlo (in inglese), non viene letto


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
