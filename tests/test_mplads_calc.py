"""Tests for MPLADS calculation utilities (COVID awareness, multi-year reconciliation)."""

from datetime import date

from tracker.utils.mplads_calc import (
    is_covid_period,
    effective_months,
    adjusted_utilization_rate,
    multi_year_utilization_summary,
)
from tracker.models.schemas import MPLADSFund, MPLADSFundPeriod


class TestIsCOVIDPeriod:
    def test_2020_21_is_covid(self):
        assert is_covid_period("2020-21") is True

    def test_2021_22_is_covid(self):
        assert is_covid_period("2021-22") is True

    def test_2019_20_not_covid(self):
        assert is_covid_period("2019-20") is False

    def test_2022_23_not_covid(self):
        assert is_covid_period("2022-23") is False

    def test_invalid_format(self):
        assert is_covid_period("invalid") is False


class TestEffectiveMonths:
    def test_no_overlap_with_covid(self):
        """Period entirely outside COVID suspension."""
        start = date(2023, 4, 1)
        end = date(2024, 3, 31)
        assert effective_months(start, end) == 12

    def test_fully_within_covid(self):
        """Period entirely within COVID suspension."""
        start = date(2020, 6, 1)
        end = date(2021, 5, 31)
        # 12 months total, 12 months suspended = 1 (minimum)
        assert effective_months(start, end) >= 1

    def test_partial_covid_overlap(self):
        """Period partially overlaps COVID suspension."""
        start = date(2019, 4, 1)
        end = date(2021, 3, 31)
        # 24 months total, minus 12 months suspended (Apr 2020 - Mar 2021)
        result = effective_months(start, end)
        assert result == 12


class TestAdjustedUtilizationRate:
    def test_cumulative_data_used(self):
        """When cumulative data is available, use it."""
        fund = MPLADSFund(
            released=100.0,
            expended=80.0,
            cumulative_released=500.0,
            cumulative_expended=450.0,
        )
        rate = adjusted_utilization_rate(fund)
        assert rate == 90.0  # 450/500 * 100

    def test_falls_back_to_standard(self):
        """When no cumulative data, fall back to standard utilization_rate."""
        fund = MPLADSFund(
            released=200.0,
            expended=160.0,
        )
        rate = adjusted_utilization_rate(fund)
        assert rate == 80.0  # 160/200 * 100

    def test_no_data(self):
        """When no data at all, return None."""
        fund = MPLADSFund()
        rate = adjusted_utilization_rate(fund)
        assert rate is None


class TestMultiYearSummary:
    def test_aggregates_periods(self):
        periods = [
            MPLADSFundPeriod(fiscal_year="2022-23", entitled=500.0, released=400.0, expended=350.0),
            MPLADSFundPeriod(fiscal_year="2023-24", entitled=500.0, released=450.0, expended=400.0),
        ]
        summary = multi_year_utilization_summary(periods)

        assert summary["total_entitled"] == 1000.0
        assert summary["total_released"] == 850.0
        assert summary["total_expended"] == 750.0
        assert abs(summary["utilization_rate"] - 88.24) < 0.1
        assert summary["covid_affected_years"] == []

    def test_identifies_covid_years(self):
        periods = [
            MPLADSFundPeriod(fiscal_year="2020-21", entitled=500.0, released=0.0, expended=0.0),
            MPLADSFundPeriod(fiscal_year="2021-22", entitled=500.0, released=250.0, expended=200.0),
        ]
        summary = multi_year_utilization_summary(periods)

        assert "2020-21" in summary["covid_affected_years"]
        assert "2021-22" in summary["covid_affected_years"]

    def test_empty_periods(self):
        summary = multi_year_utilization_summary([])
        assert summary["total_entitled"] == 0.0
        assert summary["utilization_rate"] is None
