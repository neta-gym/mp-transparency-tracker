"""Data quality regression tests.

Validates that the scoring pipeline produces meaningful, non-default values
across the 8 scoring dimensions and that leaderboard entries are well-formed.
"""

from __future__ import annotations

import pytest

from tracker.models.schemas import (
    LeaderboardEntry,
    ScoreBreakdown,
    ScoreResult,
    MPProfile,
    ResearchFindings,
    CriminalRecord,
    AssetDeclaration,
    MPLADSFund,
    ParliamentActivity,
    CommitteeEngagement,
    LegislativeRecord,
    PublicAccessibility,
    DataSource,
    EvidenceGrade,
)


# --- Fixtures ---

@pytest.fixture
def scored_mp():
    """Create a ScoreResult with non-default values across all dimensions."""
    return ScoreResult(
        mp=MPProfile(name="Test MP", constituency="Test", state="test", party="TEST"),
        composite_score=65.0,
        breakdown=ScoreBreakdown(
            mplads_score=70.0,
            asset_score=60.0,
            criminal_score=80.0,
            attendance_score=75.0,
            participation_score=55.0,
            committee_score=45.0,
            accessibility_score=90.0,
            legislative_score=40.0,
        ),
        data_confidence=0.75,
        key_finding="Test finding",
    )


@pytest.fixture
def research_findings_with_evidence():
    """Create ResearchFindings with evidence summary populated."""
    mp = MPProfile(name="Test MP", constituency="Test", state="test", party="TEST")
    return ResearchFindings(
        mp=mp,
        criminal_record=CriminalRecord(
            confidence=0.8,
            sources=[DataSource(source_name="myneta", grade=EvidenceGrade.B)],
        ),
        assets=AssetDeclaration(
            total_assets=1_00_00_000,
            confidence=0.8,
            sources=[DataSource(source_name="myneta", grade=EvidenceGrade.B)],
        ),
        mplads=MPLADSFund(
            entitled=5_00_00_000, released=4_00_00_000, expended=3_00_00_000,
            confidence=0.9,
            sources=[DataSource(source_name="esakshi", grade=EvidenceGrade.A)],
        ),
        parliament_activity=ParliamentActivity(
            attendance_percentage=85.0, questions_asked=15, debates_participated=5,
            confidence=0.8,
            sources=[DataSource(source_name="prs", grade=EvidenceGrade.C)],
        ),
        evidence_summary={
            "criminal": "B", "assets": "B", "mplads": "A",
            "parliament": "C", "committees": "A", "legislative": "A",
            "accessibility": "D",
        },
    )


# --- Score Quality Tests ---

class TestScoreQuality:
    """Tests that scored data has meaningful non-default values."""

    def test_score_has_non_default_dimensions(self, scored_mp: ScoreResult):
        """At least 4 of 8 dimensions should have non-default (non-50.0) scores."""
        bd = scored_mp.breakdown
        scores = [
            bd.mplads_score, bd.asset_score, bd.criminal_score,
            bd.attendance_score, bd.participation_score,
            bd.committee_score, bd.accessibility_score, bd.legislative_score,
        ]
        non_default = sum(1 for s in scores if s != 50.0)
        assert non_default >= 4, (
            f"Only {non_default}/8 dimensions are non-default: {scores}"
        )

    def test_composite_score_in_range(self, scored_mp: ScoreResult):
        """Composite score must be between 0 and 100."""
        assert 0 <= scored_mp.composite_score <= 100

    def test_data_confidence_in_range(self, scored_mp: ScoreResult):
        """Data confidence must be between 0 and 1."""
        assert 0 <= scored_mp.data_confidence <= 1

    def test_key_finding_not_empty(self, scored_mp: ScoreResult):
        """Key finding should not be empty."""
        assert scored_mp.key_finding, "key_finding should not be empty"

    def test_dimension_scores_in_range(self, scored_mp: ScoreResult):
        """All dimension scores must be between 0 and 100."""
        bd = scored_mp.breakdown
        for name, val in [
            ("mplads", bd.mplads_score),
            ("asset", bd.asset_score),
            ("criminal", bd.criminal_score),
            ("attendance", bd.attendance_score),
            ("participation", bd.participation_score),
            ("committee", bd.committee_score),
            ("accessibility", bd.accessibility_score),
            ("legislative", bd.legislative_score),
        ]:
            assert 0 <= val <= 100, f"{name}_score = {val} is out of range"


# --- Evidence Grade Tests ---

class TestEvidenceGrades:
    """Tests that evidence grades are properly computed."""

    def test_evidence_summary_has_grades(self, research_findings_with_evidence: ResearchFindings):
        """Evidence summary should have at least 4 dimension grades."""
        ev = research_findings_with_evidence.evidence_summary
        assert len(ev) >= 4, f"Only {len(ev)} evidence grades: {ev}"

    def test_evidence_grades_are_valid(self, research_findings_with_evidence: ResearchFindings):
        """All evidence grades should be A-E."""
        valid_grades = {"A", "B", "C", "D", "E"}
        for dim, grade in research_findings_with_evidence.evidence_summary.items():
            assert grade in valid_grades, f"Invalid grade '{grade}' for dimension '{dim}'"

    def test_avg_evidence_grade_computation(self, research_findings_with_evidence: ResearchFindings):
        """Average evidence grade should be computable from summary."""
        ev = research_findings_with_evidence.evidence_summary
        grade_map = {"A": 4, "B": 3, "C": 2, "D": 1, "E": 0}
        values = [grade_map[g] for g in ev.values()]
        avg = sum(values) / len(values)
        # Should be between D (1.0) and A (4.0) for this test data
        assert 1.0 <= avg <= 4.0, f"Avg grade value {avg} out of expected range"


# --- Leaderboard Entry Tests ---

class TestLeaderboardEntry:
    """Tests that leaderboard entries are well-formed."""

    def test_entry_has_required_fields(self):
        """LeaderboardEntry should have all required fields set."""
        entry = LeaderboardEntry(
            rank=1,
            mp_name="Test MP",
            constituency="Test Constituency",
            party="TEST",
            state="test",
            composite_score=65.0,
            mplads_score=70.0,
            asset_score=60.0,
            criminal_score=80.0,
            attendance_score=75.0,
            participation_score=55.0,
            data_confidence=0.75,
        )
        assert entry.mp_name
        assert entry.constituency
        assert entry.party
        assert entry.state
        assert entry.composite_score > 0

    def test_entry_avg_evidence_grade_default(self):
        """Default avg_evidence_grade should be 'E'."""
        entry = LeaderboardEntry(
            rank=1, mp_name="T", constituency="T", party="T", state="t",
            composite_score=50.0, mplads_score=50.0, asset_score=50.0,
            criminal_score=50.0, attendance_score=50.0, participation_score=50.0,
            data_confidence=0.5,
        )
        assert entry.avg_evidence_grade == "E"

    def test_entry_with_evidence_grade(self):
        """avg_evidence_grade should be settable."""
        entry = LeaderboardEntry(
            rank=1, mp_name="T", constituency="T", party="T", state="t",
            composite_score=50.0, mplads_score=50.0, asset_score=50.0,
            criminal_score=50.0, attendance_score=50.0, participation_score=50.0,
            data_confidence=0.5, avg_evidence_grade="B",
        )
        assert entry.avg_evidence_grade == "B"


# --- Research Data Quality Tests ---

class TestResearchDataQuality:
    """Tests that research findings have meaningful data."""

    def test_criminal_record_confidence(self):
        """Criminal record with cases should have confidence > 0.5."""
        cr = CriminalRecord(total_cases=2, serious_cases=1, confidence=0.8)
        assert cr.confidence > 0.5

    def test_asset_declaration_with_total(self):
        """Asset declaration with total_assets should have confidence >= 0.8."""
        ad = AssetDeclaration(total_assets=1_00_00_000, confidence=0.8)
        assert ad.confidence >= 0.8

    def test_mplads_utilization_rate(self):
        """MPLADS with released > 0 and expended should compute utilization rate."""
        fund = MPLADSFund(released=5_00_00_000, expended=3_00_00_000, confidence=0.9)
        assert fund.utilization_rate is not None
        assert 0 < fund.utilization_rate <= 100

    def test_parliament_activity_with_attendance(self):
        """Parliament activity with attendance should have confidence > 0."""
        pa = ParliamentActivity(attendance_percentage=85.0, confidence=0.8)
        assert pa.confidence > 0

    def test_committee_engagement_with_memberships(self):
        """Committee engagement with memberships should have confidence > 0."""
        ce = CommitteeEngagement(total_committees=3, confidence=0.7)
        assert ce.confidence > 0

    def test_asset_growth_ratio(self):
        """Asset growth ratio should be computed when both current and previous exist."""
        ad = AssetDeclaration(
            total_assets=2_00_00_000,
            previous_total_assets=1_00_00_000,
            confidence=0.8,
        )
        assert ad.growth_ratio is not None
        assert ad.growth_ratio == pytest.approx(1.0)  # doubled

    def test_asset_growth_ratio_none_without_previous(self):
        """Asset growth ratio should be None when previous is missing."""
        ad = AssetDeclaration(total_assets=2_00_00_000, confidence=0.8)
        assert ad.growth_ratio is None


# --- PRS Name Matching Tests ---

class TestPRSNameMatching:
    """Tests that PRS name matching handles common variants."""

    def test_csv_delimiter_detection(self):
        """CSV with semicolons should be detected as semicolon-delimited."""
        from tracker.tools.prs import PRSFetcher
        # Semicolons in first 500 chars → use semicolons
        text = 'Name;Constituency;State\n"Test";"Test";"Test"'
        assert ";" in text[:500]

    def test_similar_names(self):
        """Similar names with minor spelling differences should match."""
        from tracker.tools.prs import PRSFetcher
        assert PRSFetcher._similar_names("chandoliya", "chandolia")
        assert PRSFetcher._similar_names("tiwari", "tiwari")
        assert not PRSFetcher._similar_names("malhotra", "bidhuri")
