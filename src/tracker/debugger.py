"""Debugger agent — validates pipeline output, data integrity, and scoring logic.

Standalone class (not a BaseAgent subclass) that runs without API costs.
Invoked via ``python -m tracker.main --debug``.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import aiosqlite
from rich.console import Console
from rich.table import Table

console = Console()


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class CheckStatus(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"


@dataclass
class CheckResult:
    name: str
    status: CheckStatus
    message: str = ""
    details: str = ""
    duration_ms: float = 0.0


@dataclass
class SuiteResult:
    suite_name: str
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.status == CheckStatus.PASS)

    @property
    def failed(self) -> int:
        return sum(1 for c in self.checks if c.status == CheckStatus.FAIL)

    @property
    def warned(self) -> int:
        return sum(1 for c in self.checks if c.status == CheckStatus.WARN)

    @property
    def skipped(self) -> int:
        return sum(1 for c in self.checks if c.status == CheckStatus.SKIP)


# ---------------------------------------------------------------------------
# Suite name mapping
# ---------------------------------------------------------------------------

SUITE_MAP = {
    "env": "check_environment",
    "db": "check_database_integrity",
    "files": "check_output_files",
    "models": "check_model_roundtrip",
    "scoring": "check_scoring_invariants",
    "leaderboard": "check_leaderboard_consistency",
    "cross": "check_cross_artifact_consistency",
    "pytest": "check_pytest",
}


# ---------------------------------------------------------------------------
# DebuggerAgent
# ---------------------------------------------------------------------------

class DebuggerAgent:
    """Comprehensive validation layer for the MP Transparency Tracker pipeline."""

    def __init__(
        self,
        data_dir: str = "data",
        db_path: str = "data/tracker.db",
        state: str | None = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.db_path = Path(db_path)
        self.state = state
        self.results: list[SuiteResult] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run_all(self) -> list[SuiteResult]:
        """Run all 8 check suites and display results."""
        self.results = []
        for method_name in SUITE_MAP.values():
            suite = await getattr(self, method_name)()
            self.results.append(suite)
        self._render(self.results)
        self._save_report(self.results)
        return self.results

    async def run_suite(self, name: str) -> list[SuiteResult]:
        """Run a single suite by short name (e.g. 'scoring')."""
        method_name = SUITE_MAP.get(name)
        if not method_name:
            console.print(f"[red]Unknown suite '{name}'. Choose from: {', '.join(SUITE_MAP)}[/red]")
            return []
        suite = await getattr(self, method_name)()
        self.results = [suite]
        self._render(self.results)
        self._save_report(self.results)
        return self.results

    # ------------------------------------------------------------------
    # Suite 1: Environment & Configuration
    # ------------------------------------------------------------------

    async def check_environment(self) -> SuiteResult:
        suite = SuiteResult(suite_name="Environment & Configuration")

        # Score weights sum to 1.0
        try:
            from .config import Settings
            s = Settings()
            w = s.weights
            total = w.mplads + w.asset + w.criminal + w.attendance + w.participation + w.committee + w.accessibility + w.legislative
            suite.checks.append(_check(
                "Score weights sum to 1.0",
                abs(total - 1.0) < 1e-9,
                f"Sum = {total}",
            ))
        except Exception as exc:
            suite.checks.append(CheckResult("Score weights sum to 1.0", CheckStatus.FAIL, str(exc)))

        # Data directory exists
        suite.checks.append(_check(
            "Data directory exists",
            self.data_dir.exists(),
            f"{self.data_dir}",
        ))

        # Database file exists (warn if not)
        if self.db_path.exists():
            suite.checks.append(CheckResult("Database file exists", CheckStatus.PASS, str(self.db_path)))
        else:
            suite.checks.append(CheckResult("Database file exists", CheckStatus.WARN, f"Not found: {self.db_path}"))

        # Python version >= 3.10
        v = sys.version_info
        suite.checks.append(_check(
            "Python >= 3.10",
            (v.major, v.minor) >= (3, 10),
            f"{v.major}.{v.minor}.{v.micro}",
        ))

        # Key dependencies importable
        for dep in ("aiohttp", "aiosqlite", "pydantic", "rich", "bs4", "lxml"):
            try:
                importlib.import_module(dep)
                suite.checks.append(CheckResult(f"Import {dep}", CheckStatus.PASS))
            except ImportError:
                suite.checks.append(CheckResult(f"Import {dep}", CheckStatus.FAIL, f"Cannot import {dep}"))

        # .env file exists (warn only)
        env_path = Path(".env")
        if env_path.exists():
            suite.checks.append(CheckResult(".env file exists", CheckStatus.PASS))
        else:
            suite.checks.append(CheckResult(".env file exists", CheckStatus.WARN, "No .env file found"))

        return suite

    # ------------------------------------------------------------------
    # Suite 2: Database Integrity
    # ------------------------------------------------------------------

    async def check_database_integrity(self) -> SuiteResult:
        suite = SuiteResult(suite_name="Database Integrity")

        if not self.db_path.exists():
            suite.checks.append(CheckResult("Database exists", CheckStatus.SKIP, "No database file"))
            return suite

        try:
            async with aiosqlite.connect(str(self.db_path)) as db:
                db.row_factory = aiosqlite.Row

                # All 6 expected tables exist
                expected_tables = ["mps", "research_findings", "validated_findings", "scores", "leaderboards"]
                cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
                existing = {row[0] for row in await cursor.fetchall()}
                for tbl in expected_tables:
                    suite.checks.append(_check(f"Table '{tbl}' exists", tbl in existing))

                if "mps" not in existing:
                    return suite

                # No NULL values in required MP fields
                required_fields = ["slug", "state", "name", "constituency", "party"]
                for col in required_fields:
                    cursor = await db.execute(f"SELECT COUNT(*) FROM mps WHERE {col} IS NULL OR {col} = ''")
                    count = (await cursor.fetchone())[0]
                    suite.checks.append(_check(f"No NULL/empty '{col}' in mps", count == 0, f"{count} invalid rows"))

                # composite_score in [0, 100]
                if "scores" in existing:
                    cursor = await db.execute(
                        "SELECT COUNT(*) FROM scores WHERE composite_score < 0 OR composite_score > 100"
                    )
                    count = (await cursor.fetchone())[0]
                    suite.checks.append(_check("composite_score in [0, 100]", count == 0, f"{count} out-of-range"))

                    # All component scores in [0, 100]
                    for col in ["mplads_score", "asset_score", "criminal_score", "attendance_score", "participation_score", "committee_score", "accessibility_score", "legislative_score"]:
                        cursor = await db.execute(
                            f"SELECT COUNT(*) FROM scores WHERE {col} IS NOT NULL AND ({col} < 0 OR {col} > 100)"
                        )
                        count = (await cursor.fetchone())[0]
                        suite.checks.append(_check(f"{col} in [0, 100]", count == 0, f"{count} out-of-range"))

                # Confidence values in [0, 1]
                if "validated_findings" in existing:
                    cursor = await db.execute(
                        "SELECT COUNT(*) FROM validated_findings WHERE overall_confidence < 0 OR overall_confidence > 1"
                    )
                    count = (await cursor.fetchone())[0]
                    suite.checks.append(_check("overall_confidence in [0, 1]", count == 0, f"{count} out-of-range"))

                if "scores" in existing:
                    cursor = await db.execute(
                        "SELECT COUNT(*) FROM scores WHERE data_confidence IS NOT NULL AND (data_confidence < 0 OR data_confidence > 1)"
                    )
                    count = (await cursor.fetchone())[0]
                    suite.checks.append(_check("data_confidence in [0, 1]", count == 0, f"{count} out-of-range"))

                # JSON columns deserializable
                await self._check_json_column(db, suite, "research_findings", "findings_json", "ResearchFindings")
                await self._check_json_column(db, suite, "validated_findings", "validated_json", "ValidatedFindings")

                # Foreign key consistency
                for child_table in ["research_findings", "validated_findings", "scores"]:
                    if child_table in existing:
                        cursor = await db.execute(
                            f"SELECT COUNT(*) FROM {child_table} cf "
                            f"WHERE NOT EXISTS (SELECT 1 FROM mps m WHERE m.slug = cf.mp_slug AND m.state = cf.state)"
                        )
                        count = (await cursor.fetchone())[0]
                        suite.checks.append(_check(
                            f"FK: {child_table}.mp_slug → mps",
                            count == 0,
                            f"{count} orphaned rows",
                        ))
        except Exception as exc:
            suite.checks.append(CheckResult("Database access", CheckStatus.FAIL, str(exc)))

        return suite

    async def _check_json_column(
        self,
        db: aiosqlite.Connection,
        suite: SuiteResult,
        table: str,
        column: str,
        model_name: str,
    ) -> None:
        """Verify that JSON in a column deserializes to the expected Pydantic model."""
        from .models.schemas import ResearchFindings, ValidatedFindings

        model_cls = {"ResearchFindings": ResearchFindings, "ValidatedFindings": ValidatedFindings}.get(model_name)
        if model_cls is None:
            return

        cursor = await db.execute(f"SELECT {column} FROM {table} LIMIT 10")
        rows = await cursor.fetchall()
        failures = 0
        for row in rows:
            try:
                model_cls.model_validate_json(row[0])
            except Exception:
                failures += 1
        suite.checks.append(_check(
            f"{table}.{column} → {model_name}",
            failures == 0,
            f"{failures}/{len(rows)} failed to deserialize",
        ))

    # ------------------------------------------------------------------
    # Suite 3: Output File Compliance
    # ------------------------------------------------------------------

    async def check_output_files(self) -> SuiteResult:
        suite = SuiteResult(suite_name="Output File Compliance")

        from .models.schemas import ResearchFindings, ValidatedFindings, ScoreResult, Leaderboard

        state_dirs = self._get_state_dirs()
        if not state_dirs:
            suite.checks.append(CheckResult("State directories found", CheckStatus.SKIP, "No state data directories"))
            return suite

        for state_dir in state_dirs:
            state_name = state_dir.name

            # Raw JSON files are valid JSON
            raw_dir = state_dir / "raw"
            if raw_dir.exists():
                for jf in raw_dir.glob("*.json"):
                    suite.checks.append(self._check_file_valid_json(jf))
                    # 0-byte check
                    if jf.stat().st_size == 0:
                        suite.checks.append(CheckResult(f"Non-empty: {jf.name}", CheckStatus.FAIL, "0-byte file"))

                # Deserialize raw files to correct models
                for jf in raw_dir.glob("*.json"):
                    if jf.name.endswith("_validated.json"):
                        suite.checks.append(self._check_file_model(jf, ValidatedFindings, "ValidatedFindings"))
                    elif not jf.name.startswith("."):
                        suite.checks.append(self._check_file_model(jf, ResearchFindings, "ResearchFindings"))

            # Score files
            scores_dir = state_dir / "scores"
            if scores_dir.exists():
                for jf in scores_dir.glob("*.json"):
                    suite.checks.append(self._check_file_model(jf, ScoreResult, "ScoreResult"))
                    if jf.stat().st_size == 0:
                        suite.checks.append(CheckResult(f"Non-empty: {jf.name}", CheckStatus.FAIL, "0-byte file"))

            # Leaderboard
            lb_dir = state_dir / "leaderboard"
            lb_json = lb_dir / "latest.json"
            lb_md = lb_dir / "latest.md"

            if lb_dir.exists():
                suite.checks.append(_check(f"[{state_name}] leaderboard JSON exists", lb_json.exists()))
                suite.checks.append(_check(f"[{state_name}] leaderboard MD exists", lb_md.exists()))

                if lb_json.exists():
                    suite.checks.append(self._check_file_model(lb_json, Leaderboard, "Leaderboard"))

                    # Leaderboard-specific checks
                    try:
                        lb = Leaderboard.model_validate_json(lb_json.read_text())

                        # Entry count matches total_mps
                        suite.checks.append(_check(
                            f"[{state_name}] entry count == total_mps",
                            len(lb.entries) == lb.total_mps,
                            f"entries={len(lb.entries)}, total_mps={lb.total_mps}",
                        ))

                        # Ranks are sequential
                        if lb.entries:
                            expected_ranks = list(range(1, len(lb.entries) + 1))
                            actual_ranks = [e.rank for e in lb.entries]
                            suite.checks.append(_check(
                                f"[{state_name}] ranks sequential",
                                actual_ranks == expected_ranks,
                                f"Expected {expected_ranks[:5]}..., got {actual_ranks[:5]}...",
                            ))

                            # Sorted by composite_score descending
                            scores_list = [e.composite_score for e in lb.entries]
                            suite.checks.append(_check(
                                f"[{state_name}] sorted by score desc",
                                scores_list == sorted(scores_list, reverse=True),
                            ))
                    except Exception as exc:
                        suite.checks.append(CheckResult(
                            f"[{state_name}] leaderboard validation",
                            CheckStatus.FAIL,
                            str(exc),
                        ))

            # Reports exist for every MP with scores
            reports_dir = state_dir / "reports"
            if scores_dir.exists() and reports_dir.exists():
                score_slugs = {jf.stem for jf in scores_dir.glob("*.json")}
                report_slugs = {jf.stem for jf in reports_dir.glob("*.md")}
                missing = score_slugs - report_slugs
                suite.checks.append(_check(
                    f"[{state_name}] reports for all scored MPs",
                    len(missing) == 0,
                    f"Missing reports for: {', '.join(sorted(missing)[:5])}" if missing else "",
                ))

        return suite

    # ------------------------------------------------------------------
    # Suite 4: Pydantic Model Round-Trip
    # ------------------------------------------------------------------

    async def check_model_roundtrip(self) -> SuiteResult:
        suite = SuiteResult(suite_name="Pydantic Model Round-Trip")

        from .models.schemas import (
            MPProfile, ResearchFindings, ValidatedFindings, ScoreResult,
            Leaderboard, LeaderboardEntry, ScoreBreakdown,
            CriminalRecord, AssetDeclaration, MPLADSFund,
            ParliamentActivity, House, EvidenceGrade, DataSource,
        )

        # MPProfile
        mp = MPProfile(
            name="Test MP", constituency="Test Constituency",
            state="delhi", party="Test Party", slug="test-mp",
            house=House.LOK_SABHA,
        )
        suite.checks.append(self._roundtrip(mp, "MPProfile"))

        # ResearchFindings
        rf = ResearchFindings(
            mp=mp,
            criminal_record=CriminalRecord(total_cases=2, serious_cases=1),
            assets=AssetDeclaration(
                total_assets=1_000_000, previous_total_assets=500_000,
                asset_year=2024, previous_asset_year=2019,
            ),
            mplads=MPLADSFund(released=500, expended=400),
            parliament_activity=ParliamentActivity(
                attendance_percentage=75.0, questions_asked=10, debates_participated=5,
            ),
            sources_consulted=["myneta", "prs"],
        )
        suite.checks.append(self._roundtrip(rf, "ResearchFindings"))

        # Check computed fields survive
        assert rf.assets.growth_ratio is not None
        assert rf.mplads.utilization_rate is not None
        rf_json = rf.model_dump_json()
        rf2 = ResearchFindings.model_validate_json(rf_json)
        suite.checks.append(_check(
            "ResearchFindings computed fields",
            rf2.assets.growth_ratio == rf.assets.growth_ratio
            and rf2.mplads.utilization_rate == rf.mplads.utilization_rate,
            f"growth_ratio={rf2.assets.growth_ratio}, utilization_rate={rf2.mplads.utilization_rate}",
        ))

        # ValidatedFindings
        vf = ValidatedFindings(
            mp=mp, findings=rf, overall_confidence=0.85,
        )
        suite.checks.append(self._roundtrip(vf, "ValidatedFindings"))

        # ScoreResult
        sr = ScoreResult(
            mp=mp, composite_score=72.5,
            breakdown=ScoreBreakdown(
                mplads_score=80, asset_score=65, criminal_score=100,
                attendance_score=75, participation_score=60,
                committee_score=50, accessibility_score=40, legislative_score=30,
            ),
            data_confidence=0.7,
        )
        suite.checks.append(self._roundtrip(sr, "ScoreResult"))

        # Leaderboard
        lb = Leaderboard(
            state="delhi", total_mps=1,
            entries=[LeaderboardEntry(
                rank=1, mp_name="Test MP", constituency="Test",
                party="Test", state="delhi", composite_score=72.5,
                mplads_score=80, asset_score=65, criminal_score=100,
                attendance_score=75, participation_score=60,
                committee_score=50, accessibility_score=40, legislative_score=30,
                data_confidence=0.7, house="lok_sabha",
            )],
        )
        suite.checks.append(self._roundtrip(lb, "Leaderboard"))

        # Enum round-trip
        suite.checks.append(_check(
            "House enum round-trip",
            House(mp.house.value) == mp.house,
        ))
        for grade in EvidenceGrade:
            ds = DataSource(grade=grade)
            ds2 = DataSource.model_validate_json(ds.model_dump_json())
            if ds2.grade != grade:
                suite.checks.append(CheckResult(
                    f"EvidenceGrade.{grade.name} round-trip",
                    CheckStatus.FAIL,
                ))
                break
        else:
            suite.checks.append(CheckResult("EvidenceGrade enum round-trip", CheckStatus.PASS))

        return suite

    # ------------------------------------------------------------------
    # Suite 5: Scoring Algorithm Invariants
    # ------------------------------------------------------------------

    async def check_scoring_invariants(self) -> SuiteResult:
        suite = SuiteResult(suite_name="Scoring Algorithm Invariants")

        from .agents.assessor import (
            calc_mplads_score, calc_asset_score, calc_criminal_score,
            calc_attendance_score, calc_participation_score,
            calc_committee_score, calc_accessibility_score, calc_legislative_score,
        )
        from .config import Settings

        # --- MPLADS ---
        suite.checks.append(_check("MPLADS: None → 50.0", calc_mplads_score(None) == 50.0))
        suite.checks.append(_check("MPLADS: 0 → 0", calc_mplads_score(0) == 0.0))
        suite.checks.append(_check("MPLADS: capped at 100", calc_mplads_score(200) <= 100.0))

        # Monotonically increasing
        prev = calc_mplads_score(0)
        monotonic = True
        for r in range(1, 101):
            cur = calc_mplads_score(r)
            if cur < prev:
                monotonic = False
                suite.checks.append(CheckResult(
                    "MPLADS: monotonically increasing",
                    CheckStatus.FAIL,
                    f"score({r})={cur} < score({r-1})={prev}",
                ))
                break
            prev = cur
        if monotonic:
            suite.checks.append(CheckResult("MPLADS: monotonically increasing", CheckStatus.PASS))

        # --- Asset ---
        suite.checks.append(_check("Asset: None → 50.0", calc_asset_score(None) == 50.0))
        suite.checks.append(_check("Asset: 0.0 → 85", calc_asset_score(0.0) == 85))

        # Monotonically decreasing as growth increases
        asset_vals = [0.0, 0.1, 0.2, 0.5, 1.0, 2.0, 3.0]
        asset_scores = [calc_asset_score(v) for v in asset_vals]
        suite.checks.append(_check(
            "Asset: decreasing with growth",
            all(asset_scores[i] >= asset_scores[i + 1] for i in range(len(asset_scores) - 1)),
            f"Scores: {asset_scores}",
        ))

        # --- Criminal ---
        suite.checks.append(_check(
            "Criminal: clean → 100",
            calc_criminal_score(0, 0, 0) == 100.0,
        ))
        suite.checks.append(_check(
            "Criminal: floor at 0",
            calc_criminal_score(100, 50, 10) >= 0.0,
        ))
        # Severity ordering: conviction > pending > disposed
        conv_score = calc_criminal_score(1, 0, 1, 0, 0)
        pending_score = calc_criminal_score(1, 0, 0, 1, 0)
        disposed_score = calc_criminal_score(1, 0, 0, 0, 1)
        suite.checks.append(_check(
            "Criminal: conviction > pending > disposed severity",
            conv_score < pending_score < disposed_score,
            f"convicted={conv_score}, pending={pending_score}, disposed={disposed_score}",
        ))

        # --- Attendance ---
        suite.checks.append(_check("Attendance: None → 50.0", calc_attendance_score(None) == 50.0))
        suite.checks.append(_check("Attendance: minister → 50.0", calc_attendance_score(80, is_minister=True) == 50.0))
        suite.checks.append(_check(
            "Attendance: clamped [0, 100]",
            calc_attendance_score(-10) == 0.0 and calc_attendance_score(150) == 100.0,
        ))

        # --- Participation ---
        suite.checks.append(_check("Participation: (0,0) → 0", calc_participation_score(0, 0) == 0.0))
        suite.checks.append(_check("Participation: (50,30) → 100", calc_participation_score(50, 30) == 100.0))
        suite.checks.append(_check(
            "Participation: minister → 50.0",
            calc_participation_score(50, 30, is_minister=True) == 50.0,
        ))

        # --- Committee ---
        suite.checks.append(_check("Committee: 0 → 0", calc_committee_score(0) == 0.0))
        suite.checks.append(_check("Committee: 1 → 30", calc_committee_score(1) == 30.0))
        suite.checks.append(_check("Committee: 3 → 70", calc_committee_score(3) == 70.0))
        suite.checks.append(_check("Committee: capped at 100", calc_committee_score(5, 3) <= 100.0))

        # --- Accessibility ---
        suite.checks.append(_check("Accessibility: 0 → 10", calc_accessibility_score(0) == 10.0))
        suite.checks.append(_check("Accessibility: 3 → 70", calc_accessibility_score(3) == 70.0))
        suite.checks.append(_check("Accessibility: capped at 100", calc_accessibility_score(5, 3, True) <= 100.0))

        # --- Legislative ---
        suite.checks.append(_check("Legislative: (0,0,0) → 0", calc_legislative_score(0, 0, 0) == 0.0))
        suite.checks.append(_check("Legislative: 1 bill → 30", calc_legislative_score(1, 0, 0) == 30.0))
        suite.checks.append(_check("Legislative: capped at 100", calc_legislative_score(5, 10, 10) <= 100.0))

        # --- Composite: weighted sum in [0, 100] ---
        w = Settings().weights
        test_cases = [
            (0, 0, 0, 0, 0, 0, 0, 0),
            (100, 100, 100, 100, 100, 100, 100, 100),
            (50, 50, 50, 50, 50, 50, 50, 50),
            (0, 100, 0, 100, 0, 50, 50, 50),
        ]
        for mplads_s, asset_s, crim_s, att_s, part_s, comm_s, acc_s, leg_s in test_cases:
            composite = (
                mplads_s * w.mplads
                + asset_s * w.asset
                + crim_s * w.criminal
                + att_s * w.attendance
                + part_s * w.participation
                + comm_s * w.committee
                + acc_s * w.accessibility
                + leg_s * w.legislative
            )
            if not (0 <= composite <= 100):
                suite.checks.append(CheckResult(
                    "Composite in [0, 100]",
                    CheckStatus.FAIL,
                    f"composite={composite} for inputs ({mplads_s},{asset_s},{crim_s},{att_s},{part_s},{comm_s},{acc_s},{leg_s})",
                ))
                break
        else:
            suite.checks.append(CheckResult("Composite in [0, 100]", CheckStatus.PASS))

        return suite

    # ------------------------------------------------------------------
    # Suite 6: Leaderboard Consistency
    # ------------------------------------------------------------------

    async def check_leaderboard_consistency(self) -> SuiteResult:
        suite = SuiteResult(suite_name="Leaderboard Consistency")

        from .models.schemas import Leaderboard, ScoreResult

        state_dirs = self._get_state_dirs()
        if not state_dirs:
            suite.checks.append(CheckResult("State directories", CheckStatus.SKIP, "No state data"))
            return suite

        for state_dir in state_dirs:
            state_name = state_dir.name
            lb_json = state_dir / "leaderboard" / "latest.json"
            scores_dir = state_dir / "scores"

            if not lb_json.exists():
                continue

            try:
                lb = Leaderboard.model_validate_json(lb_json.read_text())
            except Exception as exc:
                suite.checks.append(CheckResult(f"[{state_name}] parse leaderboard", CheckStatus.FAIL, str(exc)))
                continue

            # No duplicate entries
            slugs_in_lb = [_slug_from_entry(e) for e in lb.entries]
            suite.checks.append(_check(
                f"[{state_name}] no duplicate entries",
                len(slugs_in_lb) == len(set(slugs_in_lb)),
                f"Duplicates found" if len(slugs_in_lb) != len(set(slugs_in_lb)) else "",
            ))

            # data_confidence in [0, 1] and house valid
            for entry in lb.entries:
                if not (0 <= entry.data_confidence <= 1):
                    suite.checks.append(CheckResult(
                        f"[{state_name}] {entry.mp_name} confidence in [0,1]",
                        CheckStatus.FAIL,
                        f"data_confidence={entry.data_confidence}",
                    ))
                    break
                if entry.house not in ("lok_sabha", "rajya_sabha"):
                    suite.checks.append(CheckResult(
                        f"[{state_name}] {entry.mp_name} valid house",
                        CheckStatus.FAIL,
                        f"house={entry.house}",
                    ))
                    break
            else:
                suite.checks.append(CheckResult(f"[{state_name}] entries valid confidence & house", CheckStatus.PASS))

            if not scores_dir.exists():
                continue

            # Cross-check: each entry's composite_score matches scores/{slug}.json
            score_files = {jf.stem: jf for jf in scores_dir.glob("*.json")}
            mismatches = []
            for entry in lb.entries:
                entry_slug = _slug_from_entry(entry)
                if entry_slug in score_files:
                    try:
                        sr = ScoreResult.model_validate_json(score_files[entry_slug].read_text())
                        if abs(sr.composite_score - entry.composite_score) > 0.01:
                            mismatches.append(f"{entry_slug}: lb={entry.composite_score}, file={sr.composite_score}")
                    except Exception:
                        pass
            suite.checks.append(_check(
                f"[{state_name}] scores match leaderboard",
                len(mismatches) == 0,
                "; ".join(mismatches[:3]) if mismatches else "",
            ))

            # Weighted sum ≈ composite (within rounding tolerance)
            from .config import Settings
            w = Settings().weights
            sum_mismatches = []
            for entry in lb.entries:
                expected = (
                    entry.mplads_score * w.mplads
                    + entry.asset_score * w.asset
                    + entry.criminal_score * w.criminal
                    + entry.attendance_score * w.attendance
                    + entry.participation_score * w.participation
                    + entry.committee_score * w.committee
                    + entry.accessibility_score * w.accessibility
                    + entry.legislative_score * w.legislative
                )
                if abs(expected - entry.composite_score) > 0.5:
                    sum_mismatches.append(f"{entry.mp_name}: expected={expected:.2f}, actual={entry.composite_score:.2f}")
            suite.checks.append(_check(
                f"[{state_name}] weighted sum ≈ composite",
                len(sum_mismatches) == 0,
                "; ".join(sum_mismatches[:3]) if sum_mismatches else "",
            ))

            # All MP slugs with score files appear in leaderboard
            lb_slugs = set(slugs_in_lb)
            score_slugs = set(score_files.keys())
            missing = score_slugs - lb_slugs
            suite.checks.append(_check(
                f"[{state_name}] all scored MPs in leaderboard",
                len(missing) == 0,
                f"Missing: {', '.join(sorted(missing)[:5])}" if missing else "",
            ))

        return suite

    # ------------------------------------------------------------------
    # Suite 7: Cross-Artifact Consistency
    # ------------------------------------------------------------------

    async def check_cross_artifact_consistency(self) -> SuiteResult:
        suite = SuiteResult(suite_name="Cross-Artifact Consistency")

        from .models.schemas import ResearchFindings, ValidatedFindings, ScoreResult

        state_dirs = self._get_state_dirs()
        if not state_dirs:
            suite.checks.append(CheckResult("State directories", CheckStatus.SKIP, "No state data"))
            return suite

        for state_dir in state_dirs:
            state_name = state_dir.name
            raw_dir = state_dir / "raw"
            scores_dir = state_dir / "scores"

            if not raw_dir.exists():
                continue

            # Collect slugs across stages
            raw_slugs: set[str] = set()
            validated_slugs: set[str] = set()
            score_slugs: set[str] = set()

            for jf in raw_dir.glob("*.json"):
                if jf.name.endswith("_validated.json"):
                    validated_slugs.add(jf.name.replace("_validated.json", ""))
                elif not jf.name.startswith("."):
                    raw_slugs.add(jf.stem)

            if scores_dir.exists():
                score_slugs = {jf.stem for jf in scores_dir.glob("*.json")}

            # MP slug consistency across pipeline
            if validated_slugs:
                orphaned = validated_slugs - raw_slugs
                suite.checks.append(_check(
                    f"[{state_name}] validated → raw slug consistency",
                    len(orphaned) == 0,
                    f"Validated without raw: {', '.join(sorted(orphaned)[:5])}" if orphaned else "",
                ))

            if score_slugs:
                orphaned = score_slugs - raw_slugs
                suite.checks.append(_check(
                    f"[{state_name}] scores → raw slug consistency",
                    len(orphaned) == 0,
                    f"Scores without raw: {', '.join(sorted(orphaned)[:5])}" if orphaned else "",
                ))

            # MP profile preserved across stages (sample up to 5)
            sample_slugs = list(raw_slugs & validated_slugs & score_slugs)[:5]
            for slug in sample_slugs:
                try:
                    rf = ResearchFindings.model_validate_json((raw_dir / f"{slug}.json").read_text())
                    vf = ValidatedFindings.model_validate_json((raw_dir / f"{slug}_validated.json").read_text())
                    sr = ScoreResult.model_validate_json((scores_dir / f"{slug}.json").read_text())

                    name_match = rf.mp.name == vf.mp.name == sr.mp.name
                    slug_match = rf.mp.slug == vf.mp.slug == sr.mp.slug
                    suite.checks.append(_check(
                        f"[{state_name}] {slug} profile consistent",
                        name_match and slug_match,
                        f"name: {rf.mp.name}/{vf.mp.name}/{sr.mp.name}, slug: {rf.mp.slug}/{vf.mp.slug}/{sr.mp.slug}",
                    ))
                except Exception as exc:
                    suite.checks.append(CheckResult(
                        f"[{state_name}] {slug} profile check",
                        CheckStatus.FAIL,
                        str(exc),
                    ))

            # Research findings have at least one source
            for slug in list(raw_slugs)[:10]:
                raw_file = raw_dir / f"{slug}.json"
                try:
                    rf = ResearchFindings.model_validate_json(raw_file.read_text())
                    suite.checks.append(_check(
                        f"[{state_name}] {slug} has sources",
                        len(rf.sources_consulted) > 0,
                        f"sources_consulted={rf.sources_consulted}",
                    ))
                except Exception:
                    pass

            # Database scores match JSON file scores (sample)
            if self.db_path.exists() and score_slugs:
                try:
                    import aiosqlite as _aiosqlite
                    async with _aiosqlite.connect(str(self.db_path)) as db:
                        for slug in list(score_slugs)[:3]:
                            cursor = await db.execute(
                                "SELECT composite_score FROM scores WHERE mp_slug = ? AND state = ? "
                                "ORDER BY created_at DESC LIMIT 1",
                                (slug, state_name.replace("-", " ")),
                            )
                            row = await cursor.fetchone()
                            if row:
                                try:
                                    sr = ScoreResult.model_validate_json(
                                        (scores_dir / f"{slug}.json").read_text()
                                    )
                                    suite.checks.append(_check(
                                        f"[{state_name}] {slug} DB ↔ file score",
                                        abs(row[0] - sr.composite_score) < 0.01,
                                        f"DB={row[0]}, file={sr.composite_score}",
                                    ))
                                except Exception:
                                    pass
                except Exception:
                    pass

        return suite

    # ------------------------------------------------------------------
    # Suite 8: Existing Test Suite (pytest)
    # ------------------------------------------------------------------

    async def check_pytest(self) -> SuiteResult:
        suite = SuiteResult(suite_name="Existing Test Suite (pytest)")

        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short", "-q"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            output = result.stdout + result.stderr

            # Parse pass/fail counts from pytest output
            passed = failed = 0
            for line in output.splitlines():
                line = line.strip()
                # Look for summary line like "30 passed, 2 failed"
                if "passed" in line or "failed" in line:
                    import re
                    p = re.search(r"(\d+) passed", line)
                    f = re.search(r"(\d+) failed", line)
                    if p:
                        passed = int(p.group(1))
                    if f:
                        failed = int(f.group(1))

            suite.checks.append(_check(
                "pytest exit code",
                result.returncode == 0,
                f"exit code {result.returncode}",
            ))
            suite.checks.append(CheckResult(
                "pytest results",
                CheckStatus.PASS if failed == 0 else CheckStatus.FAIL,
                f"{passed} passed, {failed} failed",
                details=output[-2000:] if len(output) > 2000 else output,
            ))
        except subprocess.TimeoutExpired:
            suite.checks.append(CheckResult("pytest", CheckStatus.FAIL, "Timed out after 120s"))
        except FileNotFoundError:
            suite.checks.append(CheckResult("pytest", CheckStatus.SKIP, "pytest not found"))
        except Exception as exc:
            suite.checks.append(CheckResult("pytest", CheckStatus.FAIL, str(exc)))

        return suite

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_state_dirs(self) -> list[Path]:
        """Return state data directories, optionally filtered by --state."""
        if not self.data_dir.exists():
            return []
        if self.state:
            d = self.data_dir / self.state.replace(" ", "-").lower()
            return [d] if d.exists() else []
        return [
            d for d in sorted(self.data_dir.iterdir())
            if d.is_dir() and d.name not in ("__pycache__", ".git")
            and (d / "raw").exists()
        ]

    def _check_file_valid_json(self, path: Path) -> CheckResult:
        try:
            json.loads(path.read_text())
            return CheckResult(f"Valid JSON: {path.name}", CheckStatus.PASS)
        except Exception as exc:
            return CheckResult(f"Valid JSON: {path.name}", CheckStatus.FAIL, str(exc))

    def _check_file_model(self, path: Path, model_cls: type, model_name: str) -> CheckResult:
        try:
            model_cls.model_validate_json(path.read_text())
            return CheckResult(f"{path.name} → {model_name}", CheckStatus.PASS)
        except Exception as exc:
            return CheckResult(f"{path.name} → {model_name}", CheckStatus.FAIL, str(exc))

    def _roundtrip(self, instance: Any, name: str) -> CheckResult:
        try:
            json_str = instance.model_dump_json()
            restored = type(instance).model_validate_json(json_str)
            # Compare by serialized form (handles datetime precision)
            match = instance.model_dump_json() == restored.model_dump_json()
            return _check(f"{name} round-trip", match)
        except Exception as exc:
            return CheckResult(f"{name} round-trip", CheckStatus.FAIL, str(exc))

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def _render(self, results: list[SuiteResult]) -> None:
        """Print Rich tables summarizing all suite results."""
        # Summary table
        summary = Table(title="Debugger Report", show_header=True, header_style="bold cyan")
        summary.add_column("Suite", style="bold")
        summary.add_column("Pass", style="green", justify="right")
        summary.add_column("Fail", style="red", justify="right")
        summary.add_column("Warn", style="yellow", justify="right")
        summary.add_column("Skip", style="dim", justify="right")
        summary.add_column("Status", justify="center")

        total_pass = total_fail = total_warn = total_skip = 0
        for sr in results:
            status = "[green]OK[/green]" if sr.failed == 0 else "[red]FAIL[/red]"
            summary.add_row(
                sr.suite_name,
                str(sr.passed), str(sr.failed), str(sr.warned), str(sr.skipped),
                status,
            )
            total_pass += sr.passed
            total_fail += sr.failed
            total_warn += sr.warned
            total_skip += sr.skipped

        summary.add_section()
        overall = "[green]ALL PASSED[/green]" if total_fail == 0 else "[red]FAILURES DETECTED[/red]"
        summary.add_row(
            "TOTAL", str(total_pass), str(total_fail), str(total_warn), str(total_skip),
            overall,
        )
        console.print(summary)

        # Detail table for failures and warnings
        failures = [
            (sr.suite_name, c)
            for sr in results
            for c in sr.checks
            if c.status in (CheckStatus.FAIL, CheckStatus.WARN)
        ]
        if failures:
            detail = Table(title="Issues", show_header=True, header_style="bold red")
            detail.add_column("Suite")
            detail.add_column("Check")
            detail.add_column("Status")
            detail.add_column("Message")
            for suite_name, c in failures:
                style = "red" if c.status == CheckStatus.FAIL else "yellow"
                detail.add_row(suite_name, c.name, f"[{style}]{c.status.value}[/{style}]", c.message)
            console.print(detail)

    def _save_report(self, results: list[SuiteResult]) -> None:
        """Save structured JSON report to data/debug_report.json."""
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "state": self.state,
            "suites": [
                {
                    "name": sr.suite_name,
                    "passed": sr.passed,
                    "failed": sr.failed,
                    "warned": sr.warned,
                    "skipped": sr.skipped,
                    "checks": [
                        {
                            "name": c.name,
                            "status": c.status.value,
                            "message": c.message,
                            "details": c.details,
                            "duration_ms": c.duration_ms,
                        }
                        for c in sr.checks
                    ],
                }
                for sr in results
            ],
        }
        self.data_dir.mkdir(parents=True, exist_ok=True)
        report_path = self.data_dir / "debug_report.json"
        report_path.write_text(json.dumps(report, indent=2))
        console.print(f"\n[dim]Report saved to {report_path}[/dim]")


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _check(name: str, condition: bool, message: str = "") -> CheckResult:
    """Create a PASS/FAIL CheckResult from a boolean condition."""
    return CheckResult(
        name=name,
        status=CheckStatus.PASS if condition else CheckStatus.FAIL,
        message=message,
    )


def _slug_from_entry(entry: Any) -> str:
    """Derive a slug from a LeaderboardEntry (name → lowercase, spaces → hyphens)."""
    return entry.mp_name.lower().replace(" ", "-").replace(".", "")
