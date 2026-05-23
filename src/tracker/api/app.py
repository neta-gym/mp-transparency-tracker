"""FastAPI-based read-only REST API for MP transparency data.

Start with: python -m tracker.api --port 8000
Or:         uvicorn tracker.api.app:app --port 8000
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import asynccontextmanager
from typing import Optional

import aiosqlite

from ..config import settings
from ..models.schemas import (
    Leaderboard,
    ScoreResult,
    ResearchFindings,
)

try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse, PlainTextResponse
except ImportError:
    raise ImportError(
        "FastAPI is required for the API server. Install with: pip install 'mp-transparency-tracker[api]'"
    )


_db_conn: aiosqlite.Connection | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _db_conn
    _db_conn = await aiosqlite.connect(settings.database_path)
    _db_conn.row_factory = aiosqlite.Row
    yield
    if _db_conn:
        await _db_conn.close()


app = FastAPI(
    title="MP Transparency Tracker API",
    description="Read-only API serving transparency scores for Indian Members of Parliament",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _conn() -> aiosqlite.Connection:
    if _db_conn is None:
        raise HTTPException(503, "Database not connected")
    return _db_conn


# --- Endpoints ---


@app.get("/api/v1/states")
async def list_states():
    """List all states with MP counts."""
    cursor = await _conn().execute(
        "SELECT state, COUNT(*) as mp_count FROM mps GROUP BY state ORDER BY state"
    )
    rows = await cursor.fetchall()
    return [{"state": r["state"], "mp_count": r["mp_count"]} for r in rows]


@app.get("/api/v1/states/{state}/leaderboard")
async def get_state_leaderboard(state: str):
    """Get the latest leaderboard for a state."""
    cursor = await _conn().execute(
        "SELECT leaderboard_json FROM leaderboards WHERE state = ? ORDER BY id DESC LIMIT 1",
        (state,),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(404, f"No leaderboard found for state: {state}")
    return json.loads(row["leaderboard_json"])


@app.get("/api/v1/states/{state}/mps")
async def get_state_mps(state: str):
    """List all scored MPs for a state."""
    cursor = await _conn().execute(
        """SELECT s.mp_slug, s.composite_score, s.data_confidence, s.score_json,
                  m.name, m.constituency, m.party, m.house
           FROM scores s JOIN mps m ON s.mp_slug = m.slug AND s.state = m.state
           WHERE s.state = ? ORDER BY s.composite_score DESC""",
        (state,),
    )
    rows = await cursor.fetchall()
    return [
        {
            "slug": r["mp_slug"],
            "name": r["name"],
            "constituency": r["constituency"],
            "party": r["party"],
            "house": r["house"],
            "composite_score": r["composite_score"],
            "data_confidence": r["data_confidence"],
        }
        for r in rows
    ]


@app.get("/api/v1/mps/{slug}")
async def get_mp_profile(slug: str, state: Optional[str] = Query(None)):
    """Get full score breakdown for a specific MP."""
    if state:
        cursor = await _conn().execute(
            "SELECT score_json FROM scores WHERE mp_slug = ? AND state = ? ORDER BY created_at DESC LIMIT 1",
            (slug, state),
        )
    else:
        cursor = await _conn().execute(
            "SELECT score_json FROM scores WHERE mp_slug = ? ORDER BY created_at DESC LIMIT 1",
            (slug,),
        )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(404, f"No score data for MP: {slug}")
    return json.loads(row["score_json"])


@app.get("/api/v1/mps/{slug}/report")
async def get_mp_report(slug: str, state: Optional[str] = Query(None)):
    """Get the Markdown report for an MP."""
    # Find the state from DB if not provided
    if not state:
        cursor = await _conn().execute("SELECT state FROM mps WHERE slug = ? LIMIT 1", (slug,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(404, f"MP not found: {slug}")
        state = row["state"]

    state_slug = state.replace(" ", "-").lower()
    report_path = os.path.join(settings.data_dir, state_slug, "reports", f"{slug}.md")
    if not os.path.exists(report_path):
        raise HTTPException(404, f"Report not found for {slug}")

    with open(report_path) as f:
        return PlainTextResponse(f.read(), media_type="text/markdown")


@app.get("/api/v1/mps/{slug}/history")
async def get_mp_history(slug: str, state: Optional[str] = Query(None)):
    """Get score history over time for an MP."""
    if state:
        cursor = await _conn().execute(
            "SELECT composite_score, run_timestamp FROM score_history WHERE mp_slug = ? AND state = ? ORDER BY run_timestamp",
            (slug, state),
        )
    else:
        cursor = await _conn().execute(
            "SELECT composite_score, run_timestamp, state FROM score_history WHERE mp_slug = ? ORDER BY run_timestamp",
            (slug,),
        )
    rows = await cursor.fetchall()
    if not rows:
        raise HTTPException(404, f"No history for MP: {slug}")
    return [dict(r) for r in rows]


@app.get("/api/v1/national/leaderboard")
async def get_national_leaderboard(top_n: int = Query(50, le=200)):
    """Get aggregated national leaderboard."""
    cursor = await _conn().execute(
        """SELECT state, leaderboard_json FROM leaderboards
           WHERE id IN (SELECT MAX(id) FROM leaderboards GROUP BY state)"""
    )
    rows = await cursor.fetchall()
    if not rows:
        raise HTTPException(404, "No leaderboard data available")

    all_entries = []
    for row in rows:
        lb = json.loads(row["leaderboard_json"])
        all_entries.extend(lb.get("entries", []))

    all_entries.sort(key=lambda e: e.get("composite_score", 0), reverse=True)
    for i, entry in enumerate(all_entries[:top_n], 1):
        entry["rank"] = i

    return {
        "total_mps": len(all_entries),
        "states": len(rows),
        "top_n": top_n,
        "entries": all_entries[:top_n],
    }


@app.get("/api/v1/compare")
async def compare_mps(
    mp1: str = Query(..., description="First MP slug"),
    mp2: str = Query(..., description="Second MP slug"),
):
    """Side-by-side comparison of two MPs."""
    scores = []
    for slug in [mp1, mp2]:
        cursor = await _conn().execute(
            "SELECT score_json FROM scores WHERE mp_slug = ? ORDER BY created_at DESC LIMIT 1",
            (slug,),
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(404, f"No score data for MP: {slug}")
        scores.append(json.loads(row["score_json"]))

    return {
        "mp1": scores[0],
        "mp2": scores[1],
        "comparison": {
            "composite_delta": scores[0].get("composite_score", 0) - scores[1].get("composite_score", 0),
        },
    }


# Allow running as: python -m tracker.api
def main():
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="MP Transparency Tracker API Server")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()

    uvicorn.run("tracker.api.app:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
