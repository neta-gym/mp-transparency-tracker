"""Async SQLite database operations."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import aiosqlite

from ..models.schemas import (
    MPProfile,
    ResearchFindings,
    ValidatedFindings,
    ScoreResult,
    Leaderboard,
)
from ..utils.logger import get_logger
from .migrations import TABLES, ALTER_STATEMENTS, MIGRATIONS, CURRENT_SCHEMA_VERSION

log = get_logger(__name__)


class Database:
    """Async SQLite wrapper for MP transparency data."""

    def __init__(self, db_path: str = "data/tracker.db") -> None:
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._run_migrations()
        log.info("Database connected: %s", self.db_path)

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def __aenter__(self) -> "Database":
        await self.connect()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def _run_migrations(self) -> None:
        assert self._conn is not None
        # Create base tables (including schema_version)
        for ddl in TABLES:
            await self._conn.execute(ddl)
        # Run ALTER statements for existing databases; ignore if column already exists
        for alter in ALTER_STATEMENTS:
            try:
                await self._conn.execute(alter)
            except sqlite3.OperationalError as e:
                if "duplicate column" not in str(e).lower():
                    log.warning("Migration failed: %s — %s", alter.strip()[:60], e)
        await self._conn.commit()

        # Apply versioned migrations incrementally
        cursor = await self._conn.execute("SELECT MAX(version) FROM schema_version")
        row = await cursor.fetchone()
        current_version = (row[0] or 0) if row else 0

        if current_version == 0 and MIGRATIONS:
            # First time — mark version 1 as applied (base tables)
            await self._conn.execute(
                "INSERT INTO schema_version (version, description) VALUES (?, ?)",
                (1, "Initial schema"),
            )
            current_version = 1

        for version in sorted(MIGRATIONS.keys()):
            if version <= current_version:
                continue
            migration = MIGRATIONS[version]
            log.info("Applying migration v%d: %s", version, migration["description"])
            for stmt in migration["statements"]:
                await self._conn.execute(stmt)
            await self._conn.execute(
                "INSERT INTO schema_version (version, description) VALUES (?, ?)",
                (version, migration["description"]),
            )
            log.info("Migration v%d applied", version)

        await self._conn.commit()

    # --- MP operations ---

    async def upsert_mp(self, mp: MPProfile) -> None:
        assert self._conn is not None
        await self._conn.execute(
            """
            INSERT INTO mps (slug, state, name, constituency, party, myneta_candidate_id,
                             house, sansad_member_id, profile_url, canonical_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (slug, state) DO UPDATE SET
                name=excluded.name, constituency=excluded.constituency,
                party=excluded.party, myneta_candidate_id=excluded.myneta_candidate_id,
                house=excluded.house, sansad_member_id=excluded.sansad_member_id,
                profile_url=excluded.profile_url, canonical_name=excluded.canonical_name
            """,
            (
                mp.slug, mp.state, mp.name, mp.constituency, mp.party,
                mp.myneta_candidate_id, mp.house.value, mp.sansad_member_id,
                mp.profile_url, mp.canonical_name,
            ),
        )
        await self._conn.commit()

    async def get_mps_by_state(self, state: str) -> list[dict]:
        assert self._conn is not None
        cursor = await self._conn.execute(
            "SELECT * FROM mps WHERE state = ? ORDER BY constituency", (state,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # --- Research findings ---

    async def save_research_findings(self, mp_slug: str, state: str, findings: ResearchFindings) -> None:
        assert self._conn is not None
        # Delete prior run for this MP then insert fresh — avoids duplicate accumulation
        await self._conn.execute(
            "DELETE FROM research_findings WHERE mp_slug = ? AND state = ?", (mp_slug, state),
        )
        await self._conn.execute(
            "INSERT INTO research_findings (mp_slug, state, findings_json) VALUES (?, ?, ?)",
            (mp_slug, state, findings.model_dump_json()),
        )
        await self._conn.commit()

    # --- Validated findings ---

    async def save_validated_findings(self, mp_slug: str, state: str, validated: ValidatedFindings) -> None:
        assert self._conn is not None
        await self._conn.execute(
            "DELETE FROM validated_findings WHERE mp_slug = ? AND state = ?", (mp_slug, state),
        )
        await self._conn.execute(
            "INSERT INTO validated_findings (mp_slug, state, validated_json, overall_confidence, num_flags) VALUES (?, ?, ?, ?, ?)",
            (mp_slug, state, validated.model_dump_json(), validated.overall_confidence, len(validated.flags)),
        )
        await self._conn.commit()

    # --- Scores ---

    async def save_score(self, mp_slug: str, state: str, result: ScoreResult) -> None:
        assert self._conn is not None
        b = result.breakdown
        await self._conn.execute(
            "DELETE FROM scores WHERE mp_slug = ? AND state = ?", (mp_slug, state),
        )
        await self._conn.execute(
            """INSERT INTO scores (mp_slug, state, composite_score, mplads_score, asset_score,
               criminal_score, attendance_score, participation_score,
               committee_score, accessibility_score, legislative_score,
               data_confidence, score_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                mp_slug, state, result.composite_score,
                b.mplads_score, b.asset_score, b.criminal_score,
                b.attendance_score, b.participation_score,
                b.committee_score, b.accessibility_score, b.legislative_score,
                result.data_confidence, result.model_dump_json(),
            ),
        )
        # Also append to score_history (never deleted — tracks trends over time)
        try:
            await self._conn.execute(
                "INSERT INTO score_history (mp_slug, state, composite_score, score_json) VALUES (?, ?, ?, ?)",
                (mp_slug, state, result.composite_score, result.model_dump_json()),
            )
        except sqlite3.OperationalError:
            pass  # score_history table may not exist yet in old DBs
        await self._conn.commit()

    # --- Leaderboard ---

    async def save_leaderboard(self, state: str, leaderboard: Leaderboard) -> None:
        assert self._conn is not None
        await self._conn.execute(
            "INSERT INTO leaderboards (state, leaderboard_json, methodology_version, num_mps) VALUES (?, ?, ?, ?)",
            (state, leaderboard.model_dump_json(), leaderboard.methodology_version, leaderboard.total_mps),
        )
        await self._conn.commit()

    # --- Score history (trend tracking) ---

    async def get_previous_scores(self, state: str) -> dict[str, dict]:
        """Get the most recent prior-run score for each MP in a state."""
        assert self._conn is not None
        try:
            cursor = await self._conn.execute(
                """
                SELECT mp_slug, score_json, run_timestamp FROM score_history
                WHERE state = ? AND run_timestamp < (
                    SELECT MAX(run_timestamp) FROM score_history WHERE state = ?
                )
                GROUP BY mp_slug
                HAVING run_timestamp = MAX(run_timestamp)
                ORDER BY mp_slug
                """,
                (state, state),
            )
            rows = await cursor.fetchall()
            return {row["mp_slug"]: json.loads(row["score_json"]) for row in rows}
        except (sqlite3.OperationalError, KeyError):
            return {}

    async def get_score_history(self, mp_slug: str, state: str) -> list[dict]:
        """Get full score history for one MP, ordered chronologically."""
        assert self._conn is not None
        try:
            cursor = await self._conn.execute(
                "SELECT composite_score, score_json, run_timestamp FROM score_history WHERE mp_slug = ? AND state = ? ORDER BY run_timestamp",
                (mp_slug, state),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        except sqlite3.OperationalError:
            return []

    # --- Cross-state queries ---

    async def find_mp_by_name(self, name: str) -> list[dict]:
        """Fuzzy search for an MP by name across all states."""
        assert self._conn is not None
        cursor = await self._conn.execute(
            "SELECT * FROM mps WHERE LOWER(name) LIKE ? ORDER BY state, name",
            (f"%{name.lower()}%",),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_all_latest_leaderboards(self) -> list[dict]:
        """Get the latest leaderboard for every state."""
        assert self._conn is not None
        cursor = await self._conn.execute(
            """
            SELECT state, leaderboard_json, methodology_version, num_mps, created_at
            FROM leaderboards
            WHERE id IN (SELECT MAX(id) FROM leaderboards GROUP BY state)
            ORDER BY state
            """
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
