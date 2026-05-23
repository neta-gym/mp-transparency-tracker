"""MP salary and allowances — static data from MPA 2018 / notifications.

This module provides factual, publicly notified compensation data for MPs.
It is informational only and NOT used in transparency scoring.

Sources:
- The Salary, Allowances and Pension of Members of Parliament Act, 1954
  (as amended by Members of Parliament (Amendment) Act, 2018)
- Gazette notifications for subsequent revisions
"""

from __future__ import annotations

from ..models.schemas import MPCompensation


# Current compensation structure (effective from Apr 2018 / latest notification)
# All amounts in INR per month unless noted
_CURRENT_RATES = {
    "salary_per_month": 100_000,  # Rs 1,00,000/month (MPA 2018)
    "constituency_allowance_per_month": 70_000,  # Rs 70,000/month
    "office_expense_allowance_per_month": 60_000,  # Rs 60,000/month
    "sumptuary_allowance_per_month": 15_000,  # Rs 15,000/month (LS members)
    "effective_from": "2018-04-01",
    "source_notification": (
        "Members of Parliament (Amendment) Act, 2018; "
        "The Salary, Allowances and Pension of Members of Parliament Act, 1954 "
        "(as amended). Gazette of India, Extraordinary, Part II, Section 1."
    ),
}

# Sumptuary allowance varies by role
_SUMPTUARY_ALLOWANCE = {
    "mp": 15_000,
    "leader_of_opposition": 30_000,
    "whip": 15_000,
    "minister_of_state": 12_000,  # Different structure
    "cabinet_minister": 12_000,
}

# Additional perks not counted as cash compensation:
# - Free rail travel (AC First Class) for MP + companion
# - 34 air journeys per year
# - Office space in Parliament House Estate
# - Medical facilities
# - Pension after one term: Rs 29,000/month base + Rs 1,500 per additional year
_NOTES = (
    "In addition to cash compensation, MPs receive non-cash perks including: "
    "free AC First Class rail travel, 34 annual air journeys, "
    "furnished office space, medical facilities at government hospitals, "
    "and housing or HRA (Rs 2,00,000/month if no government accommodation). "
    "Post-retirement pension: Rs 29,000/month (base) + Rs 1,500 per additional year served."
)


def get_mp_compensation(is_rajya_sabha: bool = False) -> MPCompensation:
    """Return current MP compensation data.

    Args:
        is_rajya_sabha: If True, uses Rajya Sabha sumptuary allowance rate.

    Returns:
        MPCompensation with all fields populated from latest notification.
    """
    salary = _CURRENT_RATES["salary_per_month"]
    constituency = _CURRENT_RATES["constituency_allowance_per_month"]
    office = _CURRENT_RATES["office_expense_allowance_per_month"]
    sumptuary = _CURRENT_RATES.get("sumptuary_allowance_per_month", 15_000)

    total_monthly = salary + constituency + office + sumptuary
    total_annual = total_monthly * 12

    return MPCompensation(
        salary_per_month=salary,
        constituency_allowance_per_month=constituency,
        office_expense_allowance_per_month=office,
        sumptuary_allowance_per_month=sumptuary,
        total_monthly=total_monthly,
        total_annual=total_annual,
        effective_from=_CURRENT_RATES["effective_from"],
        source_notification=_CURRENT_RATES["source_notification"],
        notes=_NOTES,
    )
