"""API web. Due chiamate, perché in mezzo c'è la revisione dell'utente:

  POST /api/format              → il grafo gira fino a human_review e si ferma
  POST /api/synthesize/{job_id} → il grafo riprende e genera l'audio
"""

import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from pydantic import BaseModel, Field

from .config import get_settings
from .graph import build_graph
from .schemas import VOICES, Script, VoiceOptions

settings = get_settings()
graph = build_graph(settings, checkpointer=InMemorySaver())
app = FastAPI(title="Voce Agenti")


class FormatRequest(BaseModel):
    text: str
    temperature: float = Field(default=0.2, ge=0, le=1.5)


class SynthesizeRequest(BaseModel):
    script: Script
    options: VoiceOptions


def job_config(job_id: str, run_name: str | None = None) -> dict:
    # run_name e metadata servono a LangSmith: nome leggibile della trace e
    # raggruppamento per thread_id (formatta + genera audio dello stesso lavoro).
    return {"configurable": {"thread_id": job_id}, "run_name": run_name, "metadata": {"thread_id": job_id}}


def view(job_id: str) -> dict:
    """Ciò che la pagina mostra: dove si trova il grafo e cosa ha fatto ogni nodo."""
    state = graph.get_state(job_config(job_id))
    return {"job_id": job_id, "next": list(state.next), "steps": state.values.get("steps", [])}


@app.get("/api/graph")
def graph_diagram():
    # Il diagramma Mermaid è generato da LangGraph a partire dal grafo vero.
    return {"mermaid": graph.get_graph().draw_mermaid()}


@app.get("/api/voices")
def voices():
    return VOICES


@app.post("/api/format")
def format_text(req: FormatRequest):
    job_id = uuid.uuid4().hex
    try:
        graph.invoke({"text": req.text, "temperature": req.temperature}, job_config(job_id, "formatta"))
    except Exception as e:  # es. Ollama spento e nessun fallback
        raise HTTPException(502, f"Errore del formatter: {type(e).__name__}: {e}")
    state = graph.get_state(job_config(job_id))
    if state.next != ("human_review",):
        # Restituiamo comunque i passi: si vede quali risposte del formatter sono state scartate.
        return JSONResponse(status_code=422, content={
            "detail": f"Il formatter non ha prodotto un copione valido: {state.values['error']}", **view(job_id)})
    return {"script": state.values["script"], **view(job_id)}


@app.post("/api/synthesize/{job_id}")
def synthesize(job_id: str, req: SynthesizeRequest):
    state = graph.get_state(job_config(job_id))
    if state.next != ("human_review",):
        if "script" not in state.values:
            raise HTTPException(404, "Lavoro sconosciuto (il server è stato riavviato?): formatta di nuovo il testo.")
        rewind_to_review(job_id)
    try:
        graph.invoke(Command(resume=req.model_dump()), job_config(job_id, "genera_audio"))
    except Exception as e:  # es. chiave Gemini errata, ffmpeg mancante
        raise HTTPException(502, f"Errore durante la sintesi: {type(e).__name__}: {e}")
    return {"wav": f"/api/audio/{job_id}.wav", "mp3": f"/api/audio/{job_id}.mp3", **view(job_id)}


def rewind_to_review(job_id: str) -> None:
    """Riporta il lavoro alla revisione, per rigenerare l'audio senza richiamare il modello.

    update_state(..., as_node="validate") scrive un nuovo checkpoint COME SE l'avesse
    prodotto il nodo validate: il grafo segue l'arco validate -> human_review, e
    invoke(None) lo fa ripartire fino all'interrupt. Il copione resta quello già validato.
    """
    step = {"node": "rewind", "output": {"note": "ripartito da validate con il copione già pronto: nessuna nuova chiamata al modello"}}
    graph.update_state(job_config(job_id), {"error": None, "steps": [step]}, as_node="validate")
    graph.invoke(None, job_config(job_id))


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
