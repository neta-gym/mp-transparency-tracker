"""Tests for MP compensation utility."""

from tracker.utils.mp_compensation import get_mp_compensation


class TestMPCompensation:
    def test_returns_non_zero_values(self):
        comp = get_mp_compensation()
        assert comp.salary_per_month > 0
        assert comp.constituency_allowance_per_month > 0
        assert comp.office_expense_allowance_per_month > 0
        assert comp.total_monthly > 0
        assert comp.total_annual > 0

    def test_total_monthly_is_sum(self):
        comp = get_mp_compensation()
        expected = (
            comp.salary_per_month
            + comp.constituency_allowance_per_month
            + comp.office_expense_allowance_per_month
            + comp.sumptuary_allowance_per_month
        )
        assert comp.total_monthly == expected

    def test_total_annual_is_12x_monthly(self):
        comp = get_mp_compensation()
        assert comp.total_annual == comp.total_monthly * 12

    def test_has_source_notification(self):
        comp = get_mp_compensation()
        assert len(comp.source_notification) > 0
        assert "MPA" in comp.source_notification or "Members of Parliament" in comp.source_notification

    def test_has_effective_date(self):
        comp = get_mp_compensation()
        assert comp.effective_from != ""

    def test_rajya_sabha_variant(self):
        comp = get_mp_compensation(is_rajya_sabha=True)
        # Should still return valid data
        assert comp.total_monthly > 0
