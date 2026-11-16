"""ORCHESTRATORE: il grafo LangGraph che coordina i subagenti.

    START
      │
      ▼
  ┌────────────┐   errore e tentativi < 3   ┌──────────┐
  │ formatter  │ ◄───────────────────────── │ validate │
  │ (LLM)      │ ─────────────────────────► │ (codice) │
  └────────────┘                            └────┬─────┘
                                     ok          │      troppi errori
                          ┌──────────────────────┘──────────────► END (errore)
                          ▼
                  ┌───────────────┐
                  │ human_review  │  ← interrupt(): il grafo si FERMA e aspetta
                  │ (tu, nel web) │    che l'utente approvi/modifichi il copione
                  └───────┬───────┘
                          ▼
                  ┌───────────────┐
                  │ settings      │  subagente deterministico → TTSPlan
                  └───────┬───────┘
                          ▼
                  ┌───────────────┐
                  │ synthesize    │  tool: Gemini TTS (fan-out parallelo)
                  └───────┬───────┘
                          ▼
                  ┌───────────────┐
                  │ postprocess   │  tool: ffmpeg (speed, pitch, MP3)
                  └───────┬───────┘
                          ▼
                         END

Perché un grafo e non un "agente orchestratore LLM" che decide da solo?
Perché qui i passi sono noti in anticipo. Un LLM che sceglie l'ordine dei passi
aggiungerebbe costo, latenza e imprevedibilità senza alcun beneficio.
L'LLM lo mettiamo solo dove serve davvero (formatter). È la distinzione
"workflow vs agent": parti sempre dal workflow, aggiungi autonomia solo se serve.
"""

import operator
import time
import uuid
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from . import audio, llm
from .agents import formatter, settings_agent
from .config import Settings
from .schemas import Script, VoiceOptions
from .tts import TTSClient, concat_wavs, make_tts, synthesize_all

MAX_FORMAT_ATTEMPTS = 3


class State(TypedDict, total=False):
    # input
    text: str
    mode_hint: str
    speaker_hint: list[str]
    # formatter / validate
    raw_output: str
    error: str | None
    attempts: int
    script: dict
    # human review
    options: dict
    # settings / tts / post
    plan: dict
    wav_path: str
    mp3_path: str
    duration_s: float
    # trace: il reducer operator.add fa sì che ogni nodo AGGIUNGA voci, non le sostituisca
    trace: Annotated[list[dict], operator.add]


def _t(agent: str, start: float, **detail: Any) -> list[dict]:
    return [{"agent": agent, "ms": round((time.perf_counter() - start) * 1000), **detail}]


def build_graph(s: Settings, model: Runnable | None = None, tts: TTSClient | None = None,
                checkpointer=None):
    """Costruisce e compila il grafo. `model` e `tts` sono iniettabili (test!)."""
    if model is None and s.formatter_provider != "fake":
        model = llm.formatter_model(s)
    model_name = llm.describe(s)
    tts_client = tts  # creato pigramente: si può formattare anche senza chiave Gemini
    out_dir = Path(s.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------- nodi
    def formatter_node(state: State) -> dict:
        t0 = time.perf_counter()
        if s.formatter_provider == "fake" and model is None:
            raw = formatter.fake_format(state["text"], state.get("mode_hint", "auto"))
        else:
            msgs = formatter.build_messages(
                state["text"], state.get("mode_hint", "auto"), state.get("speaker_hint"),
                previous_output=state.get("raw_output"), error=state.get("error"),
            )
            raw = formatter.run_llm(model, msgs)
        return {"raw_output": raw,
                "trace": _t("formatter", t0, model=model_name, attempt=state.get("attempts", 0) + 1)}

    def validate_node(state: State) -> dict:
        t0 = time.perf_counter()
        attempts = state.get("attempts", 0) + 1
        try:
            script = formatter.parse_script(state["raw_output"])
        except ValueError as e:
            err = str(e)[:800]
            return {"error": err, "attempts": attempts,
                    "trace": _t("validate", t0, ok=False, error=err)}
        return {"script": script.model_dump(), "error": None, "attempts": attempts,
                "trace": _t("validate", t0, ok=True, speakers=script.speakers, turns=len(script.turns))}

    def route_after_validate(state: State) -> str:
        if state.get("error") is None:
            return "human_review"
        return "formatter" if state["attempts"] < MAX_FORMAT_ATTEMPTS else END

    def human_review_node(state: State) -> dict:
        # interrupt() salva lo stato nel checkpointer e restituisce il controllo
        # al chiamante (l'API web). Quando l'utente risponde, il grafo riprende
        # da QUI e `decision` contiene il valore passato con Command(resume=...).
        decision = interrupt({"script": state["script"]})
        script = Script.model_validate(decision.get("script", state["script"]))
        options = VoiceOptions.model_validate(decision.get("options", {}))
        return {"script": script.model_dump(), "options": options.model_dump(),
                "trace": [{"agent": "human_review", "ms": 0, "edited": script.model_dump() != state["script"]}]}

    def settings_node(state: State) -> dict:
        t0 = time.perf_counter()
        plan = settings_agent.plan_tts(
            Script.model_validate(state["script"]), VoiceOptions.model_validate(state["options"]), s.tts_model,
        )
        return {"plan": plan.model_dump(),
                "trace": _t("settings", t0, strategy=plan.strategy, voices=plan.voices, requests=len(plan.requests))}

    def synthesize_node(state: State, config: RunnableConfig) -> dict:
        nonlocal tts_client
        t0 = time.perf_counter()
        if tts_client is None:
            tts_client = make_tts(s)
        wavs = synthesize_all(tts_client, state["plan"]["requests"])
        wav = concat_wavs(wavs) if len(wavs) > 1 else wavs[0]
        job = config["configurable"].get("thread_id") or uuid.uuid4().hex
        path = out_dir / f"{job}.raw.wav"
        path.write_bytes(wav)
        return {"wav_path": str(path),
                "trace": _t("synthesize", t0, model=s.tts_model if s.tts_backend == "gemini" else "fake",
                            calls=len(wavs))}

    def postprocess_node(state: State) -> dict:
        t0 = time.perf_counter()
        raw = Path(state["wav_path"])
        post = state["plan"]["post"]
        wav = audio.postprocess(raw.read_bytes(), post["speed"], post["pitch"])
        final = raw.with_name(raw.name.replace(".raw.wav", ".wav"))
        final.write_bytes(wav)
        mp3 = final.with_suffix(".mp3")
        mp3.write_bytes(audio.to_mp3(wav))
        raw.unlink(missing_ok=True)
        duration = (len(wav) - 44) / (2 * 24_000)
        return {"wav_path": str(final), "mp3_path": str(mp3), "duration_s": round(duration, 2),
                "trace": _t("postprocess", t0, filter=audio.build_filter(post["speed"], post["pitch"]) or "nessuno")}

    # ------------------------------------------------------------- grafo
    g = StateGraph(State)
    g.add_node("formatter", formatter_node)
    g.add_node("validate", validate_node)
    g.add_node("human_review", human_review_node)
    g.add_node("settings", settings_node)
    g.add_node("synthesize", synthesize_node)
    g.add_node("postprocess", postprocess_node)

    g.add_edge(START, "formatter")
    g.add_edge("formatter", "validate")
    g.add_conditional_edges("validate", route_after_validate, ["formatter", "human_review", END])
    g.add_edge("human_review", "settings")
    g.add_edge("settings", "synthesize")
    g.add_edge("synthesize", "postprocess")
    g.add_edge("postprocess", END)

    # Il checkpointer è ciò che rende possibile l'interrupt: lo stato di ogni
    # "thread" (qui: ogni lavoro) viene salvato e può essere ripreso.
    # InMemorySaver va bene per uso personale; per persistere ai riavvii usa
    # SqliteSaver (pacchetto langgraph-checkpoint-sqlite).
    return g.compile(checkpointer=checkpointer or InMemorySaver())


__all__ = ["build_graph", "Command", "State"]
