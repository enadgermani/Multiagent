"""Catalogo delle 30 voci predefinite di Gemini TTS.

Le voci non sono "italiane" o "inglesi": sono timbri. La lingua la decide il
testo (Gemini rileva l'italiano in automatico). Qui aggiungiamo un'indicazione
indicativa di registro (grave/acuto: stima nostra, NON ufficiale, ascoltale e correggi!) utile al subagente settings per il casting.
Verificata sulla documentazione ufficiale di novembre 2026.
"""

VOICES: dict[str, dict[str, str]] = {
    "Zephyr": {"tone": "Bright", "register": "high"},
    "Puck": {"tone": "Upbeat", "register": "mid"},
    "Charon": {"tone": "Informative", "register": "low"},
    "Kore": {"tone": "Firm", "register": "mid"},
    "Fenrir": {"tone": "Excitable", "register": "mid"},
    "Leda": {"tone": "Youthful", "register": "high"},
    "Orus": {"tone": "Firm", "register": "low"},
    "Aoede": {"tone": "Breezy", "register": "mid"},
    "Callirrhoe": {"tone": "Easy-going", "register": "mid"},
    "Autonoe": {"tone": "Bright", "register": "high"},
    "Enceladus": {"tone": "Breathy", "register": "low"},
    "Iapetus": {"tone": "Clear", "register": "low"},
    "Umbriel": {"tone": "Easy-going", "register": "low"},
    "Algieba": {"tone": "Smooth", "register": "low"},
    "Despina": {"tone": "Smooth", "register": "high"},
    "Erinome": {"tone": "Clear", "register": "high"},
    "Algenib": {"tone": "Gravelly", "register": "low"},
    "Rasalgethi": {"tone": "Informative", "register": "low"},
    "Laomedeia": {"tone": "Upbeat", "register": "high"},
    "Achernar": {"tone": "Soft", "register": "high"},
    "Alnilam": {"tone": "Firm", "register": "low"},
    "Schedar": {"tone": "Even", "register": "low"},
    "Gacrux": {"tone": "Mature", "register": "mid"},
    "Pulcherrima": {"tone": "Forward", "register": "high"},
    "Achird": {"tone": "Friendly", "register": "low"},
    "Zubenelgenubi": {"tone": "Casual", "register": "low"},
    "Vindemiatrix": {"tone": "Gentle", "register": "high"},
    "Sadachbia": {"tone": "Lively", "register": "low"},
    "Sadaltager": {"tone": "Knowledgeable", "register": "low"},
    "Sulafat": {"tone": "Warm", "register": "high"},
}

DEFAULT_VOICE = "Kore"
# Gemini accetta al massimo 2 speaker in una singola richiesta multi-speaker.
MAX_SPEAKERS_PER_CALL = 2
