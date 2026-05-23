"""MPLADS calculation utilities — COVID awareness and multi-year reconciliation.

MPLADS was suspended from April 2020 to November 2021 (20 months) due to COVID-19.
During this period, MPs' MPLADS funds were redirected to the Consolidated Fund of India.
MPLADS funds are non-lapsable — expenditure can exceed single-year release due to
prior-year balances and interest earned.

This module provides adjusted utilization calculations that account for these factors.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from ..models.schemas import MPLADSFund, MPLADSFundPeriod


# COVID suspension period: April 2020 - November 2021
COVID_SUSPENSION_START = date(2020, 4, 1)
COVID_SUSPENSION_END = date(2021, 11, 30)
COVID_SUSPENSION_MONTHS = 20


def is_covid_period(fiscal_year: str) -> bool:
    """Check if a fiscal year overlaps with the COVID MPLADS suspension.

    Args:
        fiscal_year: e.g. "2020-21", "2021-22"
    """
    try:
        start_year = int(fiscal_year.split("-")[0])
    except (ValueError, IndexError):
        return False

    # FY 2020-21: Apr 2020 - Mar 2021 (fully within suspension)
    # FY 2021-22: Apr 2021 - Mar 2022 (partially within suspension, ends Nov 2021)
    return start_year in (2020, 2021)


def effective_months(start_date: date, end_date: date) -> int:
    """Calculate effective working months excluding the COVID suspension period.

    Returns the number of months between start_date and end_date,
    minus any months that fall within the COVID suspension.
    """
    total_months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month) + 1

    # Calculate overlap with COVID suspension
    overlap_start = max(start_date, COVID_SUSPENSION_START)
    overlap_end = min(end_date, COVID_SUSPENSION_END)

    if overlap_start <= overlap_end:
        suspended_months = (overlap_end.year - overlap_start.year) * 12 + (overlap_end.month - overlap_start.month) + 1
    else:
        suspended_months = 0

    return max(1, total_months - suspended_months)


def adjusted_utilization_rate(fund: MPLADSFund) -> Optional[float]:
    """Calculate utilization rate with multi-year and COVID adjustments.

    When cumulative data is available, uses cumulative_expended / cumulative_released.
    This accounts for:
    - Non-lapsable nature of MPLADS funds (carry-forward)
    - Interest earned on unspent balances
    - COVID suspension period (no fresh releases)

    Falls back to standard utilization_rate when cumulative data is not available.
    """
    # If cumulative data is available, use it for more accurate rate
    if fund.cumulative_released and fund.cumulative_released > 0 and fund.cumulative_expended is not None:
        return (fund.cumulative_expended / fund.cumulative_released) * 100

    # Fall back to standard calculation
    return fund.utilization_rate


def multi_year_utilization_summary(periods: list[MPLADSFundPeriod]) -> dict:
    """Summarize multi-year MPLADS data.

    Returns dict with:
    - total_entitled: Sum of entitled across all periods
    - total_released: Sum of released across all periods
    - total_expended: Sum of expended across all periods
    - utilization_rate: Overall utilization rate
    - covid_affected_years: List of fiscal years affected by COVID
    - effective_period_months: Total months excluding COVID suspension
    """
    total_entitled = 0.0
    total_released = 0.0
    total_expended = 0.0
    covid_years = []

    for period in periods:
        if period.entitled:
            total_entitled += period.entitled
        if period.released:
            total_released += period.released
        if period.expended:
            total_expended += period.expended
        if is_covid_period(period.fiscal_year):
            covid_years.append(period.fiscal_year)

    rate = (total_expended / total_released * 100) if total_released > 0 else None

    return {
        "total_entitled": total_entitled,
        "total_released": total_released,
        "total_expended": total_expended,
        "utilization_rate": rate,
        "covid_affected_years": covid_years,
    }
