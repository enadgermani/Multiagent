"""API web. Due chiamate, perché in mezzo c'è la revisione dell'utente:

  POST /api/format              → il grafo gira fino a human_review e si ferma
  POST /api/synthesize/{job_id} → il grafo riprende e genera l'audio
"""

import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from pydantic import BaseModel

from .config import get_settings
from .graph import build_graph
from .schemas import VOICES, Script, VoiceOptions

settings = get_settings()
graph = build_graph(settings, checkpointer=InMemorySaver())
app = FastAPI(title="Voce Agenti")


class FormatRequest(BaseModel):
    text: str


class SynthesizeRequest(BaseModel):
    script: Script
    options: VoiceOptions


def job_config(job_id: str) -> dict:
    return {"configurable": {"thread_id": job_id}}


@app.get("/api/voices")
def voices():
    return VOICES


@app.post("/api/format")
def format_text(req: FormatRequest):
    job_id = uuid.uuid4().hex
    try:
        graph.invoke({"text": req.text}, job_config(job_id))
    except Exception as e:  # es. Ollama spento e nessun fallback
        raise HTTPException(502, f"Errore del formatter: {type(e).__name__}: {e}")
    state = graph.get_state(job_config(job_id))
    if state.next != ("human_review",):
        raise HTTPException(422, f"Il formatter non ha prodotto un copione valido: {state.values['error']}")
    return {"job_id": job_id, "script": state.values["script"]}


@app.post("/api/synthesize/{job_id}")
def synthesize(job_id: str, req: SynthesizeRequest):
    if graph.get_state(job_config(job_id)).next != ("human_review",):
        raise HTTPException(409, "Lavoro non in attesa di revisione: formatta di nuovo il testo.")
    try:
        graph.invoke(Command(resume=req.model_dump()), job_config(job_id))
    except Exception as e:  # es. chiave Gemini errata, ffmpeg mancante
        raise HTTPException(502, f"Errore durante la sintesi: {type(e).__name__}: {e}")
    return {"wav": f"/api/audio/{job_id}.wav", "mp3": f"/api/audio/{job_id}.mp3"}


@app.get("/api/audio/{job_id}.{fmt}")
def audio(job_id: str, fmt: str):
    try:
        job_id = uuid.UUID(job_id).hex  # accetta solo UUID: niente path traversal
    except ValueError:
        raise HTTPException(404)
    path = Path(settings.output_dir) / f"{job_id}.{fmt}"
    if fmt not in ("wav", "mp3") or not path.exists():
        raise HTTPException(404)
    return FileResponse(path, filename=f"voce.{fmt}")


app.mount("/", StaticFiles(directory=Path(__file__).parent.parent / "static", html=True))
