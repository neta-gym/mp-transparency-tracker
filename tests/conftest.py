"""Shared pytest fixtures for MP Transparency Tracker tests."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from tracker.models.schemas import (
    MPProfile,
    House,
    CriminalRecord,
    CriminalCase,
    AssetDeclaration,
    MPLADSFund,
    ParliamentActivity,
    CommitteeEngagement,
    CommitteeMembership,
    PublicAccessibility,
    SocialMediaProfile,
    NewsSentiment,
    LegislativeRecord,
    ConstituencyContext,
    ResearchFindings,
    ValidatedFindings,
    ValidationFlag,
    ScoreBreakdown,
    ScoreResult,
    EvidenceGrade,
    DataSource,
)
from tracker.storage.database import Database


# ---------------------------------------------------------------------------
# Factory helpers — tests can override specific fields via kwargs
# ---------------------------------------------------------------------------


def make_mp(**overrides) -> MPProfile:
    """Create a sample Lok Sabha MP profile."""
    defaults = dict(
        name="Bansuri Swaraj",
        constituency="New Delhi",
        state="delhi",
        party="BJP",
        myneta_candidate_id=7901,
        house=House.LOK_SABHA,
        sansad_member_id=1234,
        education="LLB",
        profession="Lawyer",
        age=35,
    )
    defaults.update(overrides)
    return MPProfile(**defaults)


def make_mp_rs(**overrides) -> MPProfile:
    """Create a sample Rajya Sabha MP profile."""
    defaults = dict(
        name="Sanjay Singh",
        constituency="Delhi",
        state="delhi",
        party="AAP",
        house=House.RAJYA_SABHA,
    )
    defaults.update(overrides)
    return MPProfile(**defaults)


def make_criminal_record(**overrides) -> CriminalRecord:
    defaults = dict(
        total_cases=2,
        serious_cases=1,
        convictions=0,
        pending_cases=1,
        disposed_cases=1,
        cases=[
            CriminalCase(description="IPC 420 Fraud", ipc_sections=["420"], is_serious=True, status="pending"),
            CriminalCase(description="IPC 500 Defamation", ipc_sections=["500"], status="disposed"),
        ],
        confidence=0.8,
        sources=[DataSource(source_name="myneta", grade=EvidenceGrade.B)],
    )
    defaults.update(overrides)
    return CriminalRecord(**defaults)


def make_assets(**overrides) -> AssetDeclaration:
    defaults = dict(
        movable_assets=5_00_00_000.0,
        immovable_assets=10_00_00_000.0,
        total_assets=15_00_00_000.0,
        liabilities=2_00_00_000.0,
        net_worth=13_00_00_000.0,
        previous_total_assets=10_00_00_000.0,
        confidence=0.8,
        sources=[DataSource(source_name="myneta", grade=EvidenceGrade.B)],
    )
    defaults.update(overrides)
    return AssetDeclaration(**defaults)


def make_mplads(**overrides) -> MPLADSFund:
    defaults = dict(
        entitled=5_00_00_000.0,
        released=4_50_00_000.0,
        sanctioned=4_00_00_000.0,
        expended=3_80_00_000.0,
        confidence=0.9,
        sources=[DataSource(source_name="esakshi", grade=EvidenceGrade.A)],
    )
    defaults.update(overrides)
    return MPLADSFund(**defaults)


def make_parliament(**overrides) -> ParliamentActivity:
    defaults = dict(
        attendance_percentage=78.5,
        questions_asked=25,
        debates_participated=8,
        private_bills_introduced=1,
        is_minister=False,
        confidence=0.7,
        sources=[DataSource(source_name="prs", grade=EvidenceGrade.C)],
        focus_topics=["Education", "Healthcare", "Infrastructure"],
    )
    defaults.update(overrides)
    return ParliamentActivity(**defaults)


def make_committees(**overrides) -> CommitteeEngagement:
    defaults = dict(
        memberships=[
            CommitteeMembership(committee_name="Standing Committee on Finance", role="member", committee_type="standing"),
            CommitteeMembership(committee_name="Joint Committee on Education", role="chairperson", committee_type="joint"),
        ],
        total_committees=2,
        leadership_roles=1,
        confidence=0.8,
        sources=[DataSource(source_name="sansad", grade=EvidenceGrade.A)],
    )
    defaults.update(overrides)
    return CommitteeEngagement(**defaults)


def make_social_media(**overrides) -> PublicAccessibility:
    defaults = dict(
        profiles=[
            SocialMediaProfile(platform="twitter", handle="BansuriSwaraj", verified=True, active=True),
            SocialMediaProfile(platform="facebook", handle="BansuriSwaraj", active=True),
        ],
        total_platforms=2,
        total_followers=50000,
        confidence=0.7,
    )
    defaults.update(overrides)
    return PublicAccessibility(**defaults)


def make_legislative(**overrides) -> LegislativeRecord:
    defaults = dict(
        private_member_bills=1,
        zero_hour_mentions=3,
        special_mentions=2,
        confidence=0.6,
        sources=[DataSource(source_name="sansad", grade=EvidenceGrade.A)],
    )
    defaults.update(overrides)
    return LegislativeRecord(**defaults)


def make_findings(mp: MPProfile | None = None, **overrides) -> ResearchFindings:
    """Create a full ResearchFindings with realistic data across all 8 dimensions."""
    if mp is None:
        mp = make_mp()
    defaults = dict(
        mp=mp,
        criminal_record=make_criminal_record(),
        assets=make_assets(),
        mplads=make_mplads(),
        parliament_activity=make_parliament(),
        committees=make_committees(),
        social_media=make_social_media(),
        legislative=make_legislative(),
        news_sentiment=NewsSentiment(total_articles=5, positive=2, negative=1, neutral=2, confidence=0.5),
        constituency_context=ConstituencyContext(population=2_000_000, literacy_rate=86.5, urban_percentage=97.5, district="New Delhi"),
        sources_consulted=["myneta", "prs", "mplads", "sansad_committees", "sansad_legislative", "social_media", "news"],
        evidence_summary={"criminal": "B", "assets": "B", "mplads": "A", "parliament": "C", "committees": "A", "accessibility": "D", "legislative": "A"},
    )
    defaults.update(overrides)
    return ResearchFindings(**defaults)


def make_validated(findings: ResearchFindings | None = None, **overrides) -> ValidatedFindings:
    if findings is None:
        findings = make_findings()
    defaults = dict(
        mp=findings.mp,
        findings=findings,
        overall_confidence=0.72,
        flags=[
            ValidationFlag(field="mplads", issue="Utilization rate below 90%", severity="info"),
        ],
    )
    defaults.update(overrides)
    return ValidatedFindings(**defaults)


def make_score(mp: MPProfile | None = None, **overrides) -> ScoreResult:
    if mp is None:
        mp = make_mp()
    defaults = dict(
        mp=mp,
        composite_score=62.5,
        breakdown=ScoreBreakdown(
            mplads_score=72.0,
            asset_score=65.0,
            criminal_score=80.0,
            attendance_score=78.5,
            participation_score=50.0,
            committee_score=65.0,
            accessibility_score=50.0,
            legislative_score=55.0,
        ),
        data_confidence=0.72,
        key_finding="Strong fund utilization, moderate attendance",
    )
    defaults.update(overrides)
    return ScoreResult(**defaults)


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_mp() -> MPProfile:
    return make_mp()


@pytest.fixture
def sample_mp_rs() -> MPProfile:
    return make_mp_rs()


@pytest.fixture
def sample_findings(sample_mp) -> ResearchFindings:
    return make_findings(mp=sample_mp)


@pytest.fixture
def sample_validated(sample_findings) -> ValidatedFindings:
    return make_validated(findings=sample_findings)


@pytest.fixture
def sample_score(sample_mp) -> ScoreResult:
    return make_score(mp=sample_mp)


@pytest.fixture
def mock_db() -> AsyncMock:
    """AsyncMock of Database — stubs all write methods."""
    db = AsyncMock(spec=Database)
    db.upsert_mp = AsyncMock()
    db.save_research_findings = AsyncMock()
    db.save_validated_findings = AsyncMock()
    db.save_score = AsyncMock()
    db.save_leaderboard = AsyncMock()
    db.log_api_usage = AsyncMock()
    db.get_total_usage = AsyncMock(return_value={"total_input": 0, "total_output": 0})
    db.get_mps_by_state = AsyncMock(return_value=[])
    return db


@pytest.fixture
async def tmp_db(tmp_path) -> Database:
    """Real SQLite Database in a temp directory for integration tests."""
    db_path = str(tmp_path / "test_tracker.db")
    db = Database(db_path=db_path)
    await db.connect()
    yield db
    await db.close()


@pytest.fixture
def mock_scraper() -> AsyncMock:
    """AsyncMock of AsyncScraper."""
    scraper = AsyncMock()
    scraper.fetch = AsyncMock(return_value="")
    scraper.fetch_json = AsyncMock(return_value={})
    scraper.fetch_html = AsyncMock(return_value=MagicMock())
    scraper.close = AsyncMock()
    return scraper
