"""ORCHESTRATORE: un grafo LangGraph che coordina i subagenti.

    START → formatter → validate ─┬─ errore (max 3 tentativi) → formatter
                                  └─ ok → human_review ⏸ → settings → tts → END

- formatter     subagente LLM (Qwen locale / DeepSeek)
- validate      codice: controlla l'output del formatter con lo schema Pydantic
- human_review  il grafo si FERMA (interrupt) finché l'utente non approva il copione
- settings      subagente deterministico: costruisce la richiesta per Gemini
- tts           strumenti: Gemini TTS, poi ffmpeg per velocità, pitch e MP3

L'ordine dei passi è sempre lo stesso, quindi lo decide il codice (un grafo),
non un LLM.
"""

from pathlib import Path
from typing import TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from . import formatter, settings_agent, tts
from .config import Settings
from .llm import formatter_model
from .schemas import Script, VoiceOptions

MAX_ATTEMPTS = 3


class State(TypedDict, total=False):
    text: str          # input dell'utente
    temperature: float # temperatura del formatter, scelta nell'interfaccia
    raw: str           # risposta grezza del formatter
    error: str | None  # errore di validazione (None = ok)
    attempts: int
    script: dict       # copione validato (Script)
    options: dict      # scelte dell'utente (VoiceOptions)
    request: dict      # richiesta per Gemini


def build_graph(s: Settings, checkpointer=None):
    out_dir = Path(s.output_dir)
    out_dir.mkdir(exist_ok=True)

    def formatter_node(state: State) -> dict:
        messages = formatter.build_messages(state["text"], state.get("raw"), state.get("error"))
        # Il modello si crea a ogni chiamata (è economico) con la temperatura scelta dall'utente.
        model = formatter_model(s, state.get("temperature", 0.2))
        return {"raw": model.invoke(messages).content}

    def validate_node(state: State) -> dict:
        attempts = state.get("attempts", 0) + 1
        try:
            script = formatter.parse_script(state["raw"])
        except ValueError as e:
            return {"error": str(e), "attempts": attempts}
        return {"script": script.model_dump(), "error": None, "attempts": attempts}

    def after_validate(state: State) -> str:
        if state["error"] is None:
            return "human_review"
        return "formatter" if state["attempts"] < MAX_ATTEMPTS else END

    def human_review_node(state: State) -> dict:
        # interrupt() salva lo stato e restituisce il controllo all'API web.
        # Il grafo riparte da qui quando arriva Command(resume=...): il valore
        # passato nel resume è ciò che interrupt() restituisce.
        answer = interrupt(state["script"])
        script = Script.model_validate(answer["script"])
        options = VoiceOptions.model_validate(answer["options"])
        return {"script": script.model_dump(), "options": options.model_dump()}

    def settings_node(state: State) -> dict:
        request = settings_agent.build_tts_request(
            Script.model_validate(state["script"]), VoiceOptions.model_validate(state["options"]), s.tts_model)
        return {"request": request}

    def tts_node(state: State, config: RunnableConfig) -> dict:
        wav = tts.synthesize(s.gemini_api_key.get_secret_value(), state["request"])
        opts = state["options"]
        job_id = config["configurable"]["thread_id"]
        for fmt in ("wav", "mp3"):
            (out_dir / f"{job_id}.{fmt}").write_bytes(tts.ffmpeg(wav, opts["speed"], opts["pitch"], fmt))
        return {}

    g = StateGraph(State)
    g.add_node("formatter", formatter_node)
    g.add_node("validate", validate_node)
    g.add_node("human_review", human_review_node)
    g.add_node("settings", settings_node)
    g.add_node("tts", tts_node)

    g.add_edge(START, "formatter")
    g.add_edge("formatter", "validate")
    g.add_conditional_edges("validate", after_validate, ["formatter", "human_review", END])
    g.add_edge("human_review", "settings")
    g.add_edge("settings", "tts")
    g.add_edge("tts", END)

    # Il checkpointer salva lo stato di ogni lavoro (thread_id): senza, l'interrupt non funziona.
    # L'API web passa InMemorySaver(); LangGraph Studio usa il proprio (vedi app/studio.py).
    return g.compile(checkpointer=checkpointer)
