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


# -- NetaGym Watch: Telegram alerts, digest, reliability evals --------------

import secrets as _secrets
import time as _time

from fastapi import Request
from fastapi.responses import PlainTextResponse

from .answers import SITE
from .digest import compose_digest
from .eval_harness import load_gold, markdown_report, run_evals
from .telegram_bot import TelegramClient, handle_update, verify_secret
from .watch import WatchStore, detect_changes, load_snapshots, save_snapshots


@lru_cache(maxsize=1)
def get_store() -> WatchStore:
    return WatchStore()


def _watch_secret() -> str:
    return os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip()


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request) -> JSONResponse:
    if not verify_secret(dict(request.headers), _watch_secret()):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    update = await request.json()
    outgoing = handle_update(update, get_index(), get_store())
    client = TelegramClient()
    for msg in outgoing:
        await client.send_message(msg.chat_id, msg.text)
    return JSONResponse({"ok": True, "replies": len(outgoing)})


@app.post("/api/watch/check")
async def watch_check(request: Request) -> JSONResponse:
    """Diff watched MPs against the last snapshot; alert watchers on change.

    Called after each data refresh (cron or manual). Guarded by the same
    secret as the webhook so only our pipeline can fan out alerts.
    """
    key = request.headers.get("x-watch-key", "")
    if not _watch_secret() or not _secrets.compare_digest(key, _watch_secret()):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    store = get_store()
    changes, new_snaps = detect_changes(get_index(), store.all_slugs(), load_snapshots())
    save_snapshots(new_snaps)
    client = TelegramClient()
    sent = 0
    alerts = []
    for change in changes:
        body = (f"Record update: {change.name}\n" + "\n".join(change.lines()) +
                f"\nSource: {SITE}/mp/{change.slug}/")
        for chat_id in store.watchers_of(change.slug):
            if await client.send_message(chat_id, body):
                sent += 1
            alerts.append({"watcher": chat_id, "mp": change.name,
                           "slug": change.slug, "body": body})
    return JSONResponse({"ok": True, "changes": len(changes),
                         "alerts_sent": sent, "alerts": alerts})


@app.get("/api/digest", response_class=PlainTextResponse)
def digest(chat_id: str = Query(...)) -> str:
    return compose_digest(chat_id, get_index(), get_store())


_EVAL_CACHE: dict = {"at": 0.0, "report": None}


@app.get("/api/evals/report")
def evals_report() -> JSONResponse:
    """Live reliability report, run against this deployed instance."""
    if _EVAL_CACHE["report"] is None or _time.time() - _EVAL_CACHE["at"] > 900:
        report = run_evals(_ask, load_gold())
        report["markdown"] = markdown_report(report)
        _EVAL_CACHE.update(at=_time.time(), report=report)
    return JSONResponse(_EVAL_CACHE["report"])


@app.get("/evals", response_class=HTMLResponse)
def evals_page() -> FileResponse:
    return FileResponse(STATIC / "evals.html")
