"""DoJ MP/MLA Special Courts dashboard scraper — state-level case context (Grade D)."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..config import settings
from ..models.schemas import DataSource, EvidenceGrade
from ..utils.logger import get_logger
from ..utils.name_match import normalize_state
from .scraper import AsyncScraper

log = get_logger(__name__)


class DoJFetcher:
    """Scrapes DoJ MP/MLA Special Courts dashboard for state-level aggregate stats."""

    def __init__(self, scraper: AsyncScraper) -> None:
        self.scraper = scraper
        self._cached: dict[str, dict] | None = None

    async def fetch_state_stats(self, state: str) -> dict:
        """Fetch state-level aggregate stats from DoJ dashboard.

        Returns dict with keys: total_pending, total_disposed, functional_courts,
        source (DataSource), or empty dict on failure.
        """
        state_norm = normalize_state(state)

        try:
            html = await self.scraper.fetch(settings.urls.doj_mp_mla_dashboard)
            soup = BeautifulSoup(html, "lxml")
            return self._parse_state(soup, state_norm)
        except Exception as e:
            log.warning("Failed to fetch DoJ dashboard: %s", e)
            return {}

    def _parse_state(self, soup: BeautifulSoup, state_norm: str) -> dict:
        """Parse DoJ dashboard HTML for a specific state's stats."""
        result: dict = {
            "total_pending": 0,
            "total_disposed": 0,
            "functional_courts": 0,
            "source": DataSource(
                url=settings.urls.doj_mp_mla_dashboard,
                source_name="doj_dashboard",
                grade=EvidenceGrade.D,
                notes="State-level aggregate from DoJ MP/MLA Special Courts dashboard",
            ),
        }

        # DoJ dashboard typically has a table with state-wise data
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) < 3:
                    continue

                cell_text = cells[0].get_text(strip=True).lower()
                if normalize_state(cell_text) == state_norm:
                    # Try to extract numeric values from subsequent cells
                    for i, cell in enumerate(cells[1:], 1):
                        val = re.sub(r"[^\d]", "", cell.get_text(strip=True))
                        if val:
                            num = int(val)
                            if i == 1:
                                result["total_pending"] = num
                            elif i == 2:
                                result["total_disposed"] = num
                            elif i == 3:
                                result["functional_courts"] = num
                    break

        return result
