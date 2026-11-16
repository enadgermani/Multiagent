"""Contratti dati tra gli agenti.

Lezione chiave del multi-agent: gli agenti NON si passano "testo libero", si
passano oggetti tipizzati. Lo schema è il contratto; se un LLM produce qualcosa
che non rispetta lo schema, lo scopriamo subito (validazione Pydantic) e
possiamo chiedergli di correggersi.
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class Turn(BaseModel):
    """Una battuta: chi parla, cosa dice (verbatim), con che stile."""

    speaker: str = Field(description="Nome del parlante. 'Narratore' se c'è una sola voce.")
    text: str = Field(description="Testo da leggere, esattamente come va pronunciato.")
    style: str = Field(default="", description="Indicazione di recitazione, in inglese, breve.")

    @field_validator("text")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("il testo della battuta è vuoto")
        return v.strip()


class Script(BaseModel):
    """Output del subagente formatter: un copione pronto per il TTS."""

    mode: Literal["single", "multi"]
    speakers: list[str] = Field(min_length=1)
    turns: list[Turn] = Field(min_length=1)
    notes: str = Field(default="", description="Note del formatter per l'utente (in italiano).")

    @field_validator("speakers")
    @classmethod
    def unique(cls, v: list[str]) -> list[str]:
        if len(set(v)) != len(v):
            raise ValueError("speakers contiene duplicati")
        return v

    @model_validator(mode="after")
    def consistent(self) -> "Script":  # coerenza interna tra campi
        unknown = {t.speaker for t in self.turns} - set(self.speakers)
        if unknown:
            raise ValueError(f"battute con speaker non dichiarati: {sorted(unknown)}")
        if self.mode == "single" and len(self.speakers) != 1:
            raise ValueError("mode=single richiede esattamente 1 speaker")
        return self


class VoiceOptions(BaseModel):
    """Scelte dell'utente nell'interfaccia."""

    # speaker -> nome voce Gemini; "auto" = lascia scegliere al subagente settings
    voices: dict[str, str] = Field(default_factory=dict)
    speed: float = Field(default=1.0, ge=0.5, le=2.0)  # 1.0 = naturale
    pitch: float = Field(default=0.0, ge=-6.0, le=6.0)  # semitoni
    # dsp = time-stretch preciso in post-produzione; prompt = chiesto a parole a Gemini
    speed_method: Literal["dsp", "prompt"] = "dsp"
    global_style: str = Field(default="", max_length=300)


class TTSPlan(BaseModel):
    """Output del subagente settings: tutto ciò che serve per chiamare il TTS
    e per il post-processing. È serializzabile, quindi lo mostriamo anche in UI."""

    model: str
    strategy: Literal["single_call", "two_speaker_call", "per_turn_calls"]
    voices: dict[str, str]
    requests: list[dict]  # payload pronti per client.interactions.create(**req)
    post: dict  # {"speed": float, "pitch": float}
    explanation: list[str] = Field(default_factory=list)
