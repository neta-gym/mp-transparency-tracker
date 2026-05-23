"""Budget cross-check — Union Budget MPLADS allocation verification."""

from __future__ import annotations

import re
from typing import Optional

from ..config import settings
from ..models.schemas import DataSource, EvidenceGrade
from ..utils.logger import get_logger
from .scraper import AsyncScraper

log = get_logger(__name__)


# Known MPLADS budget allocations from Union Budget documents
# These are national-level figures from Notes on Demands for Grants (MoSPI)
_KNOWN_ALLOCATIONS: dict[str, float] = {
    "2024-25": 3960.0,    # Rs 3,960 crore (Interim Budget + Full Budget)
    "2023-24": 3960.0,    # Rs 3,960 crore
    "2022-23": 3960.0,    # Rs 3,960 crore
    "2019-20": 3950.0,    # Rs 3,950 crore (pre-COVID)
    "2018-19": 3950.0,    # Rs 3,950 crore
}

# Per-MP entitlement
_PER_MP_ANNUAL_ENTITLEMENT = 5.0  # Rs 5 crore per year per MP

# Total MPs (LS + RS)
_TOTAL_MPS = 543 + 245  # 788


class BudgetFetcher:
    """Fetches and caches Union Budget MPLADS allocation data.

    Provides national-level sanity check: sum of all MPs' entitled amounts
    should approximately equal the Union Budget allocation (with tolerance
    for multi-year carryover).
    """

    def __init__(self, scraper: AsyncScraper) -> None:
        self.scraper = scraper
        self._cached_allocation: Optional[float] = None
        self._fiscal_year: str = ""

    async def get_national_allocation(self, fiscal_year: str = "2024-25") -> Optional[float]:
        """Get the national MPLADS allocation for a fiscal year (in crore).

        First checks known allocations, then tries to fetch from indiabudget.gov.in.
        """
        if fiscal_year in _KNOWN_ALLOCATIONS:
            self._cached_allocation = _KNOWN_ALLOCATIONS[fiscal_year]
            self._fiscal_year = fiscal_year
            return self._cached_allocation

        # Try fetching from budget website
        try:
            allocation = await self._fetch_from_website(fiscal_year)
            if allocation:
                self._cached_allocation = allocation
                self._fiscal_year = fiscal_year
                return allocation
        except Exception as e:
            log.warning("Budget fetch failed for %s: %s", fiscal_year, e)

        return None

    def get_expected_per_mp_entitlement(self) -> float:
        """Return the expected per-MP annual entitlement (Rs crore)."""
        return _PER_MP_ANNUAL_ENTITLEMENT

    def validate_national_total(
        self, sum_entitled_crore: float, fiscal_year: str = "2024-25", tolerance: float = 0.20
    ) -> dict:
        """Validate if sum of all MPs' entitled amounts matches budget allocation.

        Args:
            sum_entitled_crore: Sum of all MPs' entitled amounts (in crore)
            fiscal_year: Budget fiscal year to check against
            tolerance: Acceptable deviation (default 20% for multi-year carryover)

        Returns:
            dict with: matches (bool), allocation, difference, deviation_pct, notes
        """
        allocation = _KNOWN_ALLOCATIONS.get(fiscal_year)
        if not allocation:
            return {
                "matches": None,
                "allocation": None,
                "notes": f"Budget allocation for {fiscal_year} not available",
            }

        diff = sum_entitled_crore - allocation
        deviation = abs(diff / allocation) if allocation > 0 else 0

        return {
            "matches": deviation <= tolerance,
            "allocation": allocation,
            "sum_entitled": sum_entitled_crore,
            "difference": diff,
            "deviation_pct": deviation * 100,
            "fiscal_year": fiscal_year,
            "notes": (
                f"Budget allocation: Rs {allocation} Cr. "
                f"Sum of MP entitlements: Rs {sum_entitled_crore:.1f} Cr. "
                f"Deviation: {deviation * 100:.1f}% "
                f"({'within' if deviation <= tolerance else 'exceeds'} {tolerance*100:.0f}% tolerance)"
            ),
            "source": DataSource(
                url=f"{settings.urls.india_budget}",
                source_name="union_budget",
                grade=EvidenceGrade.A,
                notes=f"Union Budget {fiscal_year} — Notes on Demands for Grants, MoSPI",
            ),
        }

    async def _fetch_from_website(self, fiscal_year: str) -> Optional[float]:
        """Try to fetch MPLADS allocation from indiabudget.gov.in."""
        try:
            # This is a best-effort attempt — budget website structure varies
            url = f"{settings.urls.india_budget}/doc/Budget_at_Glance/{fiscal_year}/bag.pdf"
            text = await self.scraper.fetch(url)

            # Look for MPLADS line item
            patterns = [
                r"MPLADS[^0-9]*(\d[\d,.]+)\s*(?:crore|cr)",
                r"Members of Parliament.*?(\d[\d,.]+)\s*(?:crore|cr)",
            ]
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    val = match.group(1).replace(",", "")
                    return float(val)

        except Exception:
            pass

        return None
