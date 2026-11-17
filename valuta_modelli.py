"""Confronta Qwen (locale) e DeepSeek (remoto) come formatter, usando LangSmith.

    uv run python valuta_modelli.py

La prima volta crea su LangSmith il dataset "formatter-it" con alcuni testi di prova,
poi lancia un esperimento per ciascun modello. Su smith.langchain.com > Datasets &
Experiments > formatter-it trovi i due esperimenti affiancati: punteggi, latenza, token.
Serve LANGSMITH_API_KEY in .env (e DEEPSEEK_API_KEY per il secondo esperimento).
"""

from langsmith import Client, evaluate

from app.config import get_settings
from app.formatter import build_messages, parse_script
from app.llm import local_model, remote_model

DATASET = "formatter-it"
TEXTS = [
    "Il fatturato è cresciuto del 3,5% (dati ISTAT), cioè di 120 € a famiglia. Dettagli su https://example.com ecc.",
    "# Ricetta\n**Ingredienti**: farina, uova & zucchero.\nMescolare per 5 min.",
    "Marco: Ciao Giulia, hai visto la partita?\nGiulia: Sì! Che finale, 2 a 1 all'ultimo minuto.",
    "— Come sta, dottore?\n— Bene, grazie. E lei, signora Rossi?",
    "Nel mezzo del cammin di nostra vita mi ritrovai per una selva oscura, ché la diritta via era smarrita.",
]


# --- Valutatori: funzioni normali che danno un voto a ogni risposta -----------------
def valid_schema(outputs: dict) -> bool:
    """La risposta rispetta lo schema Script?"""
    try:
        parse_script(outputs["raw"])
        return True
    except ValueError:
        return False


def no_symbols(outputs: dict) -> bool:
    """Sono spariti simboli e markup che il TTS leggerebbe male?"""
    return not any(sym in outputs["raw"] for sym in ("%", "€", "http", "**", "#"))


def not_summarized(inputs: dict, outputs: dict) -> bool:
    """Il testo in uscita è lungo almeno l'80% di quello in entrata (il modello non ha riassunto)?"""
    try:
        script = parse_script(outputs["raw"])
    except ValueError:
        return False
    return sum(len(t.text) for t in script.turns) >= 0.8 * len(inputs["text"])


def target(model):
    def run(inputs: dict) -> dict:
        return {"raw": model.invoke(build_messages(inputs["text"])).content}
    return run


if __name__ == "__main__":
    s = get_settings()
    client = Client()
    if not client.has_dataset(dataset_name=DATASET):
        dataset = client.create_dataset(DATASET)
        client.create_examples(dataset_id=dataset.id, examples=[{"inputs": {"text": t}} for t in TEXTS])

    models = [("qwen", local_model(s, 0.2))]
    if s.deepseek_api_key:
        models.append(("deepseek", remote_model(s, 0.2)))
    for name, model in models:
        evaluate(target(model), data=DATASET, evaluators=[valid_schema, no_symbols, not_summarized],
                 experiment_prefix=name)
