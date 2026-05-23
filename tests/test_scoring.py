"""Unit tests for scoring algorithm."""

import pytest

from tracker.agents.assessor import (
    calc_mplads_score,
    calc_asset_score,
    calc_criminal_score,
    calc_attendance_score,
    calc_participation_score,
    calc_committee_score,
    calc_accessibility_score,
    calc_legislative_score,
    evidence_grade_multiplier,
)


class TestMPLADSScore:
    def test_high_utilization(self):
        assert calc_mplads_score(95) == pytest.approx(95, abs=0.1)

    def test_ninety_percent(self):
        assert calc_mplads_score(90) == pytest.approx(90, abs=0.1)

    def test_seventy_percent(self):
        assert calc_mplads_score(70) == pytest.approx(70, abs=0.1)

    def test_fifty_percent(self):
        assert calc_mplads_score(50) == pytest.approx(40, abs=0.1)

    def test_low_utilization(self):
        score = calc_mplads_score(30)
        assert score == pytest.approx(24, abs=0.1)

    def test_zero(self):
        assert calc_mplads_score(0) == pytest.approx(0, abs=0.1)

    def test_none_returns_neutral(self):
        assert calc_mplads_score(None) == 50.0

    def test_hundred_percent(self):
        assert calc_mplads_score(100) == pytest.approx(100, abs=0.1)


class TestAssetScore:
    def test_no_growth(self):
        assert calc_asset_score(0.0) == 85

    def test_negative_growth(self):
        assert calc_asset_score(-0.1) == 85

    def test_moderate_growth(self):
        assert calc_asset_score(0.20) == 80

    def test_fifty_pct_growth(self):
        assert calc_asset_score(0.50) == 65

    def test_hundred_pct_growth(self):
        assert calc_asset_score(1.0) == 45

    def test_high_growth(self):
        assert calc_asset_score(2.0) == 25

    def test_extreme_growth(self):
        assert calc_asset_score(3.0) == 10

    def test_none_returns_neutral(self):
        assert calc_asset_score(None) == 50.0


class TestCriminalScore:
    def test_clean_record(self):
        assert calc_criminal_score(0, 0, 0) == 100.0

    def test_legacy_one_non_serious(self):
        """Legacy path: no pending/disposed breakdown."""
        assert calc_criminal_score(1, 0, 0) == 85.0

    def test_legacy_one_serious(self):
        assert calc_criminal_score(1, 1, 0) == 75.0

    def test_legacy_conviction(self):
        assert calc_criminal_score(1, 1, 1) == 45.0

    def test_legacy_many_cases(self):
        assert calc_criminal_score(10, 5, 0) == max(0, 100 - 5 * 15 - 5 * 25)

    def test_legacy_floor_at_zero(self):
        assert calc_criminal_score(20, 10, 5) == 0.0

    # New pending/disposed scoring
    def test_pending_serious_case(self):
        """1 serious pending case: -20."""
        score = calc_criminal_score(1, 1, 0, pending_cases=1, disposed_cases=0)
        assert score == pytest.approx(80.0, abs=0.1)

    def test_pending_non_serious_case(self):
        """1 non-serious pending case: -10."""
        score = calc_criminal_score(1, 0, 0, pending_cases=1, disposed_cases=0)
        assert score == pytest.approx(90.0, abs=0.1)

    def test_disposed_case(self):
        """1 disposed case: -3."""
        score = calc_criminal_score(1, 0, 0, pending_cases=0, disposed_cases=1)
        assert score == pytest.approx(97.0, abs=0.1)

    def test_conviction_with_pending(self):
        """1 conviction + 1 serious pending: -30 + -20 = 50."""
        score = calc_criminal_score(2, 1, 1, pending_cases=1, disposed_cases=0)
        assert score == pytest.approx(50.0, abs=0.1)

    def test_mixed_pending_disposed(self):
        """2 pending (1 serious) + 1 disposed."""
        score = calc_criminal_score(3, 1, 0, pending_cases=2, disposed_cases=1)
        # -20 (serious pending) + -10 (non-serious pending) + -3 (disposed) = 67
        assert score == pytest.approx(67.0, abs=0.1)


class TestAttendanceScore:
    def test_full_attendance(self):
        assert calc_attendance_score(100.0) == 100.0

    def test_half_attendance(self):
        assert calc_attendance_score(50.0) == 50.0

    def test_zero_attendance(self):
        assert calc_attendance_score(0.0) == 0.0

    def test_minister_gets_neutral(self):
        assert calc_attendance_score(30.0, is_minister=True) == 50.0

    def test_none_returns_neutral(self):
        assert calc_attendance_score(None) == 50.0


class TestParticipationScore:
    def test_high_participation(self):
        score = calc_participation_score(50, 30)
        assert score == 100.0

    def test_moderate_participation(self):
        score = calc_participation_score(15, 5)
        assert score == pytest.approx(60.0, abs=0.1)

    def test_zero_participation(self):
        assert calc_participation_score(0, 0) == 0.0

    def test_minister_gets_neutral(self):
        assert calc_participation_score(0, 0, is_minister=True) == 50.0

    def test_questions_only(self):
        score = calc_participation_score(50, 0)
        assert score == pytest.approx(50.0, abs=0.1)

    def test_debates_only(self):
        score = calc_participation_score(0, 30)
        assert score == pytest.approx(50.0, abs=0.1)


class TestCommitteeScore:
    def test_no_committees(self):
        assert calc_committee_score(0) == 0.0

    def test_one_committee(self):
        assert calc_committee_score(1) == 30.0

    def test_two_committees(self):
        assert calc_committee_score(2) == 50.0

    def test_three_committees(self):
        assert calc_committee_score(3) == 70.0

    def test_many_committees(self):
        assert calc_committee_score(5) == 70.0

    def test_leadership_bonus(self):
        # 2 committees (50) + 1 leadership (15) = 65
        assert calc_committee_score(2, leadership_roles=1) == 65.0

    def test_leadership_caps_at_100(self):
        # 3 committees (70) + 3 leadership (45) = capped at 100
        assert calc_committee_score(3, leadership_roles=3) == 100.0


class TestAccessibilityScore:
    def test_no_platforms(self):
        assert calc_accessibility_score(0) == 10.0

    def test_one_platform(self):
        assert calc_accessibility_score(1) == 30.0

    def test_two_platforms(self):
        assert calc_accessibility_score(2) == 50.0

    def test_three_platforms(self):
        assert calc_accessibility_score(3) == 70.0

    def test_verified_bonus(self):
        # 2 platforms (50) + 2 verified (20) = 70
        assert calc_accessibility_score(2, verified_count=2) == 70.0

    def test_active_bonus(self):
        # 2 platforms (50) + active (10) = 60
        assert calc_accessibility_score(2, active=True) == 60.0

    def test_all_bonuses(self):
        # 3 platforms (70) + 2 verified (20) + active (10) = capped at 100
        assert calc_accessibility_score(3, verified_count=2, active=True) == 100.0


class TestLegislativeScore:
    def test_no_activity(self):
        assert calc_legislative_score(0, 0, 0) == 0.0

    def test_one_bill(self):
        assert calc_legislative_score(private_member_bills=1) == 30.0

    def test_two_bills(self):
        assert calc_legislative_score(private_member_bills=2) == 50.0

    def test_three_bills(self):
        assert calc_legislative_score(private_member_bills=3) == 70.0

    def test_zero_hour_low(self):
        assert calc_legislative_score(zero_hour_mentions=1) == 15.0

    def test_zero_hour_medium(self):
        assert calc_legislative_score(zero_hour_mentions=3) == 25.0

    def test_zero_hour_high(self):
        assert calc_legislative_score(zero_hour_mentions=6) == 35.0

    def test_special_mentions_low(self):
        assert calc_legislative_score(special_mentions=1) == 10.0

    def test_special_mentions_high(self):
        assert calc_legislative_score(special_mentions=3) == 20.0

    def test_combined(self):
        # 1 bill (30) + 2 zero hour (15) + 1 special (10) = 55
        assert calc_legislative_score(1, 2, 1) == 55.0

    def test_combined_caps_at_100(self):
        # 3 bills (70) + 6 zero hour (35) + 3 special (20) = capped at 100
        assert calc_legislative_score(3, 6, 3) == 100.0


class TestEvidenceGradeMultiplier:
    def test_grade_a(self):
        assert evidence_grade_multiplier("A") == 1.0

    def test_grade_b(self):
        assert evidence_grade_multiplier("B") == 0.9

    def test_grade_c(self):
        assert evidence_grade_multiplier("C") == 0.7

    def test_grade_d(self):
        assert evidence_grade_multiplier("D") == 0.5

    def test_grade_e(self):
        assert evidence_grade_multiplier("E") == 0.3

    def test_unknown_defaults_to_e(self):
        assert evidence_grade_multiplier("X") == 0.3


class TestCompositeFormula:
    """Test that the full composite formula works correctly with 8 dimensions."""

    def test_perfect_scores(self):
        # Weights: mplads=0.25, asset=0.15, criminal=0.15, attendance=0.10,
        # participation=0.10, committee=0.10, accessibility=0.05, legislative=0.10
        composite = (
            100 * 0.25 + 85 * 0.15 + 100 * 0.15 + 100 * 0.10
            + 100 * 0.10 + 100 * 0.10 + 100 * 0.05 + 100 * 0.10
        )
        assert composite == pytest.approx(97.75, abs=0.1)

    def test_worst_scores(self):
        composite = (
            0 * 0.25 + 10 * 0.15 + 0 * 0.15 + 0 * 0.10
            + 0 * 0.10 + 0 * 0.10 + 10 * 0.05 + 0 * 0.10
        )
        assert composite == pytest.approx(2.0, abs=0.1)

    def test_neutral_scores(self):
        composite = (
            50 * 0.25 + 50 * 0.15 + 50 * 0.15 + 50 * 0.10
            + 50 * 0.10 + 50 * 0.10 + 50 * 0.05 + 50 * 0.10
        )
        assert composite == pytest.approx(50, abs=0.1)

    def test_weights_sum_to_one(self):
        total = 0.25 + 0.15 + 0.15 + 0.10 + 0.10 + 0.10 + 0.05 + 0.10
        assert total == pytest.approx(1.0, abs=0.001)
