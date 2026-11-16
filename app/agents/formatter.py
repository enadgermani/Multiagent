"""Subagente FORMATTER: testo grezzo -> copione (Script) pronto per il TTS.

È un vero "agente LLM": il lavoro richiede comprensione del linguaggio
(chi parla? dove servono pause? come si pronuncia "3,5%"?). Ma è un agente
*stretto*: un solo compito, un solo formato d'uscita, nessuno strumento.
I subagenti stretti sono più affidabili e si possono far girare su modelli
piccoli (Qwen 9B in locale) invece che su modelli enormi.
"""

import json
import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from ..schemas import Script

SYSTEM_PROMPT = """Sei un adattatore di testi per la sintesi vocale (TTS) in ITALIANO.
Ricevi un testo grezzo e restituisci SOLO un oggetto JSON con questo schema:

{
  "mode": "single" | "multi",
  "speakers": ["Nome1", ...],
  "turns": [{"speaker": "Nome1", "text": "...", "style": "..."}],
  "notes": "breve nota in italiano su cosa hai cambiato"
}

REGOLE SUL TESTO ("text"):
1. Il testo resta in italiano e fedele al senso: NON riassumere, NON inventare.
2. Rimuovi ciò che non si legge ad alta voce: markdown (#, *, _), URL, emoji,
   numeri di nota, tabelle (trasformale in frasi).
3. Scrivi per l'orecchio: sciogli abbreviazioni ("ecc." -> "eccetera",
   "dott." -> "dottore", "p.es." -> "per esempio"), simboli ("%" -> "per cento",
   "€" -> "euro", "&" -> "e"), sigle poco note alla prima occorrenza.
4. Puoi inserire con parsimonia questi tag in inglese tra parentesi angolari:
   <short pause>, <long pause>, <laugh>, <sigh>. Mai altre indicazioni nel testo:
   ciò che scrivi in "text" viene LETTO.
5. Spezza in battute di lunghezza ragionevole (massimo ~600 caratteri), a fine frase.

REGOLE SUI PARLANTI:
6. Se il testo è un dialogo (righe "Nome: ...", trattini di dialogo, intervista),
   usa mode="multi" e un nome per ogni parlante. Altrimenti mode="single" con
   un solo speaker "Narratore".
7. Ogni "speaker" nelle battute deve comparire in "speakers".

REGOLE SULLO STILE ("style"):
8. Breve indicazione di recitazione IN INGLESE (es. "calm, warm narration",
   "excited, fast", "whispering"). Coerente con il contenuto.

Rispondi con il solo JSON, senza testo prima o dopo, senza ```."""


def build_messages(
    text: str,
    mode_hint: str = "auto",
    speaker_hint: list[str] | None = None,
    previous_output: str | None = None,
    error: str | None = None,
) -> list:
    hints = []
    if mode_hint == "single":
        hints.append("L'utente vuole UNA sola voce (mode=single).")
    elif mode_hint == "multi":
        hints.append("L'utente vuole PIÙ voci (mode=multi).")
    if speaker_hint:
        hints.append("Parlanti indicati dall'utente: " + ", ".join(speaker_hint))
    user = (("\n".join(hints) + "\n\n") if hints else "") + "TESTO:\n" + text

    messages = [SystemMessage(SYSTEM_PROMPT), HumanMessage(user)]
    if previous_output is not None and error:
        # Self-correction: mostriamo al modello la sua risposta e l'errore.
        messages += [
            AIMessage(previous_output),
            HumanMessage(
                "La tua risposta non è valida:\n" + error +
                "\nCorreggila e restituisci SOLO il JSON corretto."
            ),
        ]
    return messages


def run_llm(model: Runnable, messages: list) -> str:
    out = model.invoke(messages)
    return out.content if hasattr(out, "content") else str(out)


_JSON_BLOCK = re.compile(r"\{.*\}", re.S)


def parse_script(raw: str) -> Script:
    """Estrae e valida il JSON. Solleva ValueError con un messaggio utile
    da rimandare al modello in caso di errore."""
    m = _JSON_BLOCK.search(raw)
    if not m:
        raise ValueError("nessun oggetto JSON trovato nella risposta")
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON non valido: {e}") from e
    return Script.model_validate(data)  # ValidationError è sottoclasse di ValueError


# --------------------------------------------------------------------------
# Formatter finto: niente LLM, regole fisse. Serve per test e sviluppo offline,
# ed è un ottimo termine di paragone: cosa fa in più l'LLM?
# --------------------------------------------------------------------------
_DIALOG_LINE = re.compile(r"^\s*([A-ZÀ-Ý][\wÀ-ÿ' ]{0,30}):\s*(.+)$")
_REPLACEMENTS = [
    (r"https?://\S+", ""),
    (r"[*_#`>]+", ""),
    (r"\becc\.", "eccetera"),
    (r"(\d)\s?%", r"\1 per cento"),
    (r"€\s?(\d[\d.,]*)", r"\1 euro"),
    (r"\s+&\s+", " e "),
]


def _clean(t: str) -> str:
    for pat, rep in _REPLACEMENTS:
        t = re.sub(pat, rep, t)
    return re.sub(r"[ \t]+", " ", t).strip()


def fake_format(text: str, mode_hint: str = "auto") -> str:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    dialog = [_DIALOG_LINE.match(ln) for ln in lines]
    is_dialog = lines and sum(1 for d in dialog if d) >= max(2, len(lines) // 2)
    if (is_dialog and mode_hint != "single") or (mode_hint == "multi" and is_dialog):
        turns, speakers = [], []
        for d, ln in zip(dialog, lines):
            if d:
                name, said = d.group(1).strip(), _clean(d.group(2))
                if name not in speakers:
                    speakers.append(name)
                turns.append({"speaker": name, "text": said, "style": "natural, conversational"})
            elif turns:
                turns[-1]["text"] += " " + _clean(ln)
        return json.dumps({"mode": "multi", "speakers": speakers, "turns": turns,
                           "notes": "Formatter finto: dialogo riconosciuto dalle righe 'Nome:'."})
    paragraphs = [_clean(p) for p in re.split(r"\n\s*\n", text) if _clean(p)]
    return json.dumps({
        "mode": "single", "speakers": ["Narratore"],
        "turns": [{"speaker": "Narratore", "text": p, "style": "calm, clear narration"}
                  for p in paragraphs],
        "notes": "Formatter finto: pulizia con regole fisse, una voce.",
    })
