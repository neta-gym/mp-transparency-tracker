"""SAGY (Sansad Adarsh Gram Yojana) village adoption data fetcher.

Shows MP engagement with model village development.
Informational only — not used in scoring.
"""

from __future__ import annotations

from ..config import settings
from ..models.schemas import (
    MPProfile,
    SAGYAdoption,
    DataSource,
    EvidenceGrade,
)
from ..utils.logger import get_logger
from ..utils.name_match import name_matches
from .scraper import AsyncScraper

log = get_logger(__name__)


class SAGYFetcher:
    """Fetches SAGY (Sansad Adarsh Gram Yojana) village adoption data.

    Scrapes the SAGY portal (saanjhi.gov.in) for village adoption records.
    """

    def __init__(self, scraper: AsyncScraper) -> None:
        self.scraper = scraper
        self._cached_data: list[dict] | None = None

    async def fetch_adoptions(self, mp: MPProfile) -> list[SAGYAdoption]:
        """Fetch SAGY village adoption data for an MP."""
        log.info("SAGY: Fetching data for %s", mp.name)

        try:
            data = await self._fetch_data()
            if not data:
                return []

            return self._find_mp_adoptions(mp, data)

        except Exception as e:
            log.warning("SAGY fetch failed for %s: %s", mp.name, e)
            return []

    async def _fetch_data(self) -> list[dict]:
        """Fetch and cache SAGY portal data."""
        if self._cached_data is not None:
            return self._cached_data

        try:
            # Try the SAGY portal API
            url = f"{settings.urls.sagy_portal}/api/villages"
            text = await self.scraper.fetch(url)

            import json
            data = json.loads(text)
            self._cached_data = data if isinstance(data, list) else data.get("data", [])
            log.info("SAGY: Loaded %d records", len(self._cached_data))
            return self._cached_data

        except Exception as e:
            log.warning("SAGY API fetch failed: %s — trying HTML fallback", e)

        try:
            # Fallback: scrape the HTML listing
            html = await self.scraper.fetch(settings.urls.sagy_portal)
            self._cached_data = self._parse_html(html)
            return self._cached_data
        except Exception as e:
            log.warning("SAGY HTML fallback failed: %s", e)
            self._cached_data = []
            return self._cached_data

    def _find_mp_adoptions(self, mp: MPProfile, data: list[dict]) -> list[SAGYAdoption]:
        """Find SAGY adoptions for a specific MP."""
        results = []

        name_variants = [mp.name]
        if mp.canonical_name and mp.canonical_name != mp.name:
            name_variants.append(mp.canonical_name)
        name_variants.extend(mp.name_aliases)

        for record in data:
            mp_name = str(record.get("mp_name", "") or record.get("member_name", ""))

            matched = False
            for variant in name_variants:
                if name_matches(variant, mp_name):
                    matched = True
                    break

            if not matched:
                # Constituency fallback
                constituency = str(record.get("constituency", ""))
                if mp.constituency and constituency:
                    from ..utils.name_match import normalize_state
                    if normalize_state(mp.constituency) == normalize_state(constituency):
                        matched = True

            if matched:
                results.append(SAGYAdoption(
                    village_name=record.get("village_name", "") or record.get("gram_panchayat", ""),
                    district=record.get("district", ""),
                    state=record.get("state", mp.state),
                    adopted_year=self._parse_year(record.get("year", "") or record.get("adopted_year", "")),
                    phase=record.get("phase", ""),
                    source=DataSource(
                        url=settings.urls.sagy_portal,
                        source_name="sagy",
                        grade=EvidenceGrade.B,
                        notes="SAGY village adoption from saanjhi.gov.in",
                    ),
                ))

        log.info("SAGY: Found %d adoptions for %s", len(results), mp.name)
        return results

    def _parse_year(self, val) -> int | None:
        try:
            return int(str(val).strip()[:4])
        except (ValueError, IndexError):
            return None

    def _parse_html(self, html: str) -> list[dict]:
        """Parse SAGY portal HTML for village adoption data."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            records = []
            for row in soup.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) >= 4:
                    records.append({
                        "mp_name": cells[0].get_text(strip=True),
                        "constituency": cells[1].get_text(strip=True) if len(cells) > 1 else "",
                        "village_name": cells[2].get_text(strip=True) if len(cells) > 2 else "",
                        "district": cells[3].get_text(strip=True) if len(cells) > 3 else "",
                        "state": cells[4].get_text(strip=True) if len(cells) > 4 else "",
                        "phase": cells[5].get_text(strip=True) if len(cells) > 5 else "",
                    })
            return records
        except Exception:
            return []
