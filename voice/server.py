"""Neta Gym Voice - HTTP service.

Endpoints:
    GET  /                    web UI (type a question)
    GET  /talk                live voice UI (needs ASSEMBLYAI_API_KEY + AGENT_ID)
    POST /api/ask             {"question": ...} -> answer text
    GET|POST /tools/ask       AssemblyAI agent HTTP tool (voice brain)
    GET  /api/voice-agent     public agent view for the talk page
    GET  /api/voice-token     60-second AssemblyAI session token (key stays here)
    GET  /api/health          index stats + integration status

Run:  uvicorn voice.server:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel

from .answers import answer
from .assemblyai_client import aai_config, get_agent, mint_session_token
from .data_index import MPDataIndex
from .intents import parse

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="Neta Gym Voice", version="0.1.0")


@lru_cache(maxsize=1)
def get_index() -> MPDataIndex:
    return MPDataIndex()


class Question(BaseModel):
    question: str


def _ask(question: str) -> dict:
    parsed = parse(question)
    result = answer(parsed, get_index())
    return {
        "question": question,
        "intent": parsed.intent,
        "language": parsed.language,
        "answer": result["text"],
        "mps": result["mps"],
    }


@app.get("/", response_class=HTMLResponse)
def home() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/talk", response_class=HTMLResponse)
def talk() -> FileResponse:
    return FileResponse(STATIC / "talk.html")


@app.get("/static/{name}")
def static_file(name: str) -> FileResponse:
    path = STATIC / name
    if not path.exists() or path.parent != STATIC:
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(path)


@app.post("/api/ask")
def ask(q: Question) -> dict:
    return _ask(q.question)


@app.post("/tools/ask")
def tool_ask_post(q: Question) -> JSONResponse:
    """AssemblyAI HTTP-tool shape: question in, spoken answer out."""
    result = _ask(q.question)
    return JSONResponse({"answer": result["answer"], "mps": result["mps"]})


@app.get("/tools/ask")
def tool_ask_get(question: str = Query(...)) -> JSONResponse:
    result = _ask(question)
    return JSONResponse({"answer": result["answer"], "mps": result["mps"]})


@app.get("/api/voice-agent")
async def voice_agent() -> JSONResponse:
    """Public agent view for the talk page: id + name only."""
    if aai_config() is None:
        return JSONResponse({"error": "voice not configured"}, status_code=503)
    agent_id = os.environ.get("AGENT_ID", "").strip()
    if not agent_id:
        return JSONResponse({"error": "AGENT_ID is not set"}, status_code=503)
    agent = await get_agent(agent_id)
    return JSONResponse({"id": agent_id,
                         "name": agent.get("name") or "Neta Gym Voice"})


@app.get("/api/voice-token")
async def voice_token() -> JSONResponse:
    if aai_config() is None:
        return JSONResponse({"error": "voice not configured"}, status_code=503)
    token = await mint_session_token(expires_in_seconds=60)
    return JSONResponse(token)


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "data": get_index().stats(),
        "assemblyai_configured": aai_config() is not None,
    }
