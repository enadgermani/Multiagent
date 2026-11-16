"""API web: il "punto d'ingresso" del sito verso l'orchestratore.

Il flusso è in DUE chiamate perché c'è un umano nel mezzo:
  1. POST /api/format       → il grafo gira fino a human_review e si ferma
  2. POST /api/jobs/{id}/synthesize → il grafo riprende con copione + impostazioni
"""

import re
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from langgraph.types import Command
from pydantic import BaseModel, Field

from . import llm
from .config import get_settings
from .graph import build_graph
from .schemas import Script, VoiceOptions
from .voices import VOICES

settings = get_settings()
app = FastAPI(title="Voce Agenti", version="1.0")
graph = build_graph(settings)
JOB_RE = re.compile(r"^[0-9a-f]{32}$")
STATIC = Path(__file__).resolve().parent.parent / "static"


class FormatRequest(BaseModel):
    text: str = Field(min_length=1)
    mode_hint: str = Field(default="auto", pattern="^(auto|single|multi)$")
    speakers: list[str] = Field(default_factory=list)


class SynthesizeRequest(BaseModel):
    script: Script
    options: VoiceOptions


def _cfg(job_id: str) -> dict:
    if not JOB_RE.match(job_id):
        raise HTTPException(404, "job non valido")
    return {"configurable": {"thread_id": job_id}}


@app.get("/api/config")
def config():
    return {
        "voices": VOICES,
        "formatter": llm.describe(settings),
        "tts_model": settings.tts_model,
        "tts_backend": settings.tts_backend,
        "gemini_key": settings.gemini_api_key is not None or settings.tts_backend == "fake",
        "max_chars": settings.max_input_chars,
    }


@app.post("/api/format")
def format_text(req: FormatRequest):
    if len(req.text) > settings.max_input_chars:
        raise HTTPException(413, f"Testo troppo lungo (max {settings.max_input_chars} caratteri)")
    job_id = uuid.uuid4().hex
    cfg = _cfg(job_id)
    try:
        graph.invoke({"text": req.text, "mode_hint": req.mode_hint,
                      "speaker_hint": [s for s in req.speakers if s.strip()], "attempts": 0}, cfg)
    except Exception as e:  # es. Ollama spento e niente fallback
        raise HTTPException(502, f"Errore del modello di formattazione: {e}") from e
    state = graph.get_state(cfg)
    if "human_review" not in state.next:
        raise HTTPException(422, {"message": "Il formatter non ha prodotto un copione valido",
                                  "error": state.values.get("error"), "trace": state.values.get("trace", [])})
    return {"job_id": job_id, "script": state.values["script"], "trace": state.values["trace"]}


@app.post("/api/jobs/{job_id}/synthesize")
def synthesize(job_id: str, req: SynthesizeRequest):
    cfg = _cfg(job_id)
    state = graph.get_state(cfg)
    if "human_review" not in state.next:
        if not state.values.get("script"):
            raise HTTPException(404, "Lavoro sconosciuto o scaduto (il server è stato riavviato?)")
        # Rigenerazione con altre impostazioni: "forchettiamo" il lavoro.
        job_id, cfg = _fork(state.values)
    try:
        graph.invoke(Command(resume={"script": req.script.model_dump(), "options": req.options.model_dump()}), cfg)
    except Exception as e:
        raise HTTPException(502, f"Errore durante la sintesi: {e}") from e
    v = graph.get_state(cfg).values
    plan = v["plan"]
    return {
        "job_id": job_id,
        "wav": f"/api/jobs/{job_id}/audio.wav",
        "mp3": f"/api/jobs/{job_id}/audio.mp3",
        "duration_s": v.get("duration_s"),
        "plan": {k: plan[k] for k in ("model", "strategy", "voices", "post", "explanation")},
        "first_request": plan["requests"][0],  # didattico: il payload vero inviato a Gemini
        "trace": v["trace"],
    }


def _fork(values: dict) -> tuple[str, dict]:
    """Crea un nuovo thread che parte come se il formatter avesse appena finito.

    `update_state(..., as_node="validate")` scrive lo stato *come se* l'avesse
    prodotto il nodo validate; poi `invoke(None)` fa ripartire il grafo, che
    segue l'arco validate → human_review e si ferma di nuovo all'interrupt.
    Niente nuova chiamata all'LLM: è il "time travel" di LangGraph.
    """
    new_id = uuid.uuid4().hex
    cfg = _cfg(new_id)
    graph.update_state(cfg, {"text": values["text"], "script": values["script"], "error": None,
                             "attempts": values.get("attempts", 1),
                             "trace": [{"agent": "fork", "ms": 0, "from": "lavoro precedente"}]},
                       as_node="validate")
    graph.invoke(None, cfg)
    return new_id, cfg


@app.get("/api/jobs/{job_id}/audio.{ext}")
def audio_file(job_id: str, ext: str):
    _cfg(job_id)
    if ext not in ("wav", "mp3"):
        raise HTTPException(404)
    path = Path(settings.output_dir) / f"{job_id}.{ext}"
    if not path.exists():
        raise HTTPException(404, "audio non ancora generato")
    media = "audio/mpeg" if ext == "mp3" else "audio/wav"
    return FileResponse(path, media_type=media, filename=f"voce-{job_id[:8]}.{ext}")


app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
