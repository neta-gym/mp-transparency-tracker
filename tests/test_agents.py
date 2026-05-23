"""Agent logic tests with mocked dependencies."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from tracker.models.schemas import (
    MPProfile,
    House,
    ResearchFindings,
    CriminalRecord,
    AssetDeclaration,
    MPLADSFund,
    ParliamentActivity,
    ValidatedFindings,
    ValidationFlag,
    ScoreBreakdown,
    ScoreResult,
    EvidenceGrade,
    DataSource,
)


class TestValidatorRules:
    """Test validator rule-based checks without Claude."""

    def _make_findings(self, **kwargs) -> ResearchFindings:
        mp = MPProfile(name="Test MP", constituency="Test", state="test", party="TEST")
        defaults = {
            "mp": mp,
            "criminal_record": CriminalRecord(confidence=0.8),
            "assets": AssetDeclaration(confidence=0.8),
            "mplads": MPLADSFund(confidence=0.8),
            "parliament_activity": ParliamentActivity(confidence=0.8),
            "sources_consulted": ["myneta", "prs", "mplads"],
        }
        defaults.update(kwargs)
        return ResearchFindings(**defaults)

    def test_criminal_serious_exceeds_total(self):
        from tracker.agents.validator import ValidatorAgent
        agent = ValidatorAgent.__new__(ValidatorAgent)
        flags: list[ValidationFlag] = []
        findings = self._make_findings(
            criminal_record=CriminalRecord(total_cases=1, serious_cases=5, confidence=0.8)
        )
        agent._check_criminal(findings, flags)
        assert any("Serious cases exceed" in f.issue for f in flags)

    def test_criminal_pending_disposed_exceeds_total(self):
        from tracker.agents.validator import ValidatorAgent
        agent = ValidatorAgent.__new__(ValidatorAgent)
        flags: list[ValidationFlag] = []
        findings = self._make_findings(
            criminal_record=CriminalRecord(
                total_cases=2, serious_cases=0, convictions=0,
                pending_cases=2, disposed_cases=2, confidence=0.8
            )
        )
        agent._check_criminal(findings, flags)
        assert any("exceeds total" in f.issue for f in flags)

    def test_negative_assets_flagged(self):
        from tracker.agents.validator import ValidatorAgent
        agent = ValidatorAgent.__new__(ValidatorAgent)
        flags: list[ValidationFlag] = []
        findings = self._make_findings(
            assets=AssetDeclaration(total_assets=-100, confidence=0.8)
        )
        agent._check_assets(findings, flags)
        assert any("Negative total assets" in f.issue for f in flags)

    def test_high_utilization_flagged(self):
        from tracker.agents.validator import ValidatorAgent
        agent = ValidatorAgent.__new__(ValidatorAgent)
        flags: list[ValidationFlag] = []
        findings = self._make_findings(
            mplads=MPLADSFund(released=100, expended=150, confidence=0.8)
        )
        agent._check_mplads(findings, flags)
        assert any("100%" in f.issue for f in flags)

    def test_low_source_count_flagged(self):
        from tracker.agents.validator import ValidatorAgent
        agent = ValidatorAgent.__new__(ValidatorAgent)
        flags: list[ValidationFlag] = []
        findings = self._make_findings(sources_consulted=["myneta"])
        agent._check_sources(findings, flags)
        assert any("source" in f.issue.lower() for f in flags)

    def test_attendance_over_100_flagged(self):
        from tracker.agents.validator import ValidatorAgent
        agent = ValidatorAgent.__new__(ValidatorAgent)
        flags: list[ValidationFlag] = []
        findings = self._make_findings(
            parliament_activity=ParliamentActivity(attendance_percentage=110, confidence=0.8)
        )
        agent._check_parliament(findings, flags)
        assert any("100%" in f.issue for f in flags)

    def test_evidence_quality_all_low(self):
        from tracker.agents.validator import ValidatorAgent
        agent = ValidatorAgent.__new__(ValidatorAgent)
        flags: list[ValidationFlag] = []
        findings = self._make_findings(
            evidence_summary={"criminal": "E", "assets": "E", "parliament": "E", "mplads": "E"}
        )
        agent._check_evidence_quality(findings, flags)
        assert any("Grade D or E" in f.issue for f in flags)

    def test_evidence_quality_majority_low(self):
        from tracker.agents.validator import ValidatorAgent
        agent = ValidatorAgent.__new__(ValidatorAgent)
        flags: list[ValidationFlag] = []
        findings = self._make_findings(
            evidence_summary={"criminal": "B", "assets": "E", "parliament": "E", "mplads": "E"}
        )
        agent._check_evidence_quality(findings, flags)
        assert any("Majority" in f.issue for f in flags)

    def test_evidence_quality_all_good(self):
        from tracker.agents.validator import ValidatorAgent
        agent = ValidatorAgent.__new__(ValidatorAgent)
        flags: list[ValidationFlag] = []
        findings = self._make_findings(
            evidence_summary={"criminal": "B", "assets": "B", "parliament": "C", "mplads": "C"}
        )
        agent._check_evidence_quality(findings, flags)
        # No evidence quality flags should be raised
        assert not any("Grade" in f.issue for f in flags)


class TestAssessorAutoKeyFinding:
    def test_clean_high_utilization(self):
        from tracker.agents.assessor import AssessorAgent
        agent = AssessorAgent.__new__(AssessorAgent)
        breakdown = ScoreBreakdown(
            criminal_score=100, mplads_score=85, attendance_score=90,
            asset_score=50, participation_score=50,
        )
        finding = agent._auto_key_finding(breakdown)
        assert "Clean record" in finding
        assert "Strong fund utilization" in finding
        assert "High attendance" in finding

    def test_poor_record(self):
        from tracker.agents.assessor import AssessorAgent
        agent = AssessorAgent.__new__(AssessorAgent)
        breakdown = ScoreBreakdown(
            criminal_score=30, mplads_score=20, attendance_score=30,
            asset_score=50, participation_score=50,
        )
        finding = agent._auto_key_finding(breakdown)
        assert "criminal" in finding.lower()
        assert "Low fund utilization" in finding
        assert "Low attendance" in finding


class TestMPProfile:
    def test_slug_generation(self):
        mp = MPProfile(name="Manoj Tiwari", constituency="North East Delhi", state="delhi", party="BJP")
        assert mp.slug == "manoj-tiwari"

    def test_custom_slug(self):
        mp = MPProfile(name="Test", constituency="Test", state="test", party="T", slug="custom-slug")
        assert mp.slug == "custom-slug"

    def test_house_default(self):
        mp = MPProfile(name="Test", constituency="Test", state="test", party="T")
        assert mp.house == House.LOK_SABHA

    def test_house_rajya_sabha(self):
        mp = MPProfile(name="Test", constituency="Test", state="test", party="T", house=House.RAJYA_SABHA)
        assert mp.house == House.RAJYA_SABHA

    def test_sansad_fields(self):
        mp = MPProfile(
            name="Test", constituency="Test", state="test", party="T",
            sansad_member_id=101, profile_url="https://sansad.in/101",
            canonical_name="Test MP", name_aliases=["T. MP"],
        )
        assert mp.sansad_member_id == 101
        assert mp.canonical_name == "Test MP"
        assert mp.name_aliases == ["T. MP"]


class TestAssetGrowthRatio:
    def test_growth_calculated(self):
        assets = AssetDeclaration(total_assets=200, previous_total_assets=100)
        assert assets.growth_ratio == 1.0

    def test_no_previous(self):
        assets = AssetDeclaration(total_assets=200)
        assert assets.growth_ratio is None

    def test_zero_previous(self):
        assets = AssetDeclaration(total_assets=200, previous_total_assets=0)
        assert assets.growth_ratio is None


class TestMPLADSUtilization:
    def test_utilization_calculated(self):
        fund = MPLADSFund(released=100, expended=75)
        assert fund.utilization_rate == 75.0

    def test_no_released(self):
        fund = MPLADSFund(expended=75)
        assert fund.utilization_rate is None


class TestDataSource:
    def test_data_source_creation(self):
        ds = DataSource(
            url="https://example.com",
            source_name="test",
            grade=EvidenceGrade.B,
        )
        assert ds.grade == EvidenceGrade.B
        assert ds.source_name == "test"

    def test_evidence_grade_enum(self):
        assert EvidenceGrade.A.value == "A"
        assert EvidenceGrade.E.value == "E"
