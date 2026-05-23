"""MPLADS fund utilization data fetcher."""

from __future__ import annotations

import csv
import io
import re
from urllib.parse import urljoin

from ..config import settings
from ..models.schemas import MPProfile, MPLADSFund, DataSource, EvidenceGrade
from ..utils.logger import get_logger
from ..utils.name_match import normalize_state, name_matches
from .scraper import AsyncScraper

log = get_logger(__name__)


def _parse_float(val: str) -> float | None:
    if not val:
        return None
    cleaned = re.sub(r"[^\d.]", "", val.strip())
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def _is_html(text: str) -> bool:
    """Check if the response text is HTML rather than CSV."""
    stripped = text.strip()[:500].lower()
    return stripped.startswith("<!") or stripped.startswith("<html") or "<head" in stripped


def _extract_csv_link(html: str, base_url: str) -> str | None:
    """Parse HTML page to find a downloadable CSV link."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return None

    soup = BeautifulSoup(html, "html.parser")
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        link_text = a_tag.get_text(strip=True).lower()
        if href.endswith(".csv") or "csv" in link_text or "download" in link_text:
            return urljoin(base_url, href)
    return None


class MPLADSFetcher:
    """Fetches MPLADS fund utilization data."""

    def __init__(self, scraper: AsyncScraper) -> None:
        self.scraper = scraper
        self._cached_data: list[dict] | None = None
        self._data_available: bool = True

    async def _load_data(self) -> list[dict]:
        """Load and cache the MPLADS CSV data.

        Detects HTML responses (landing pages) and tries to find actual CSV links.
        """
        if self._cached_data is not None:
            return self._cached_data

        try:
            text = await self.scraper.fetch(settings.urls.mplads_csv)

            # Check if the response is HTML instead of CSV
            if _is_html(text):
                log.warning(
                    "MPLADS URL returned HTML instead of CSV: %s — "
                    "attempting to find CSV download link",
                    settings.urls.mplads_csv,
                )
                csv_link = _extract_csv_link(text, settings.urls.mplads_csv)
                if csv_link:
                    log.info("Found CSV link in HTML page: %s", csv_link)
                    text = await self.scraper.fetch(csv_link)
                    # Verify the follow-up is actually CSV
                    if _is_html(text):
                        log.error(
                            "CSV link also returned HTML — MPLADS data unavailable"
                        )
                        self._data_available = False
                        self._cached_data = []
                        return self._cached_data
                else:
                    log.error(
                        "MPLADS URL returned HTML with no CSV download link — "
                        "dataset may have moved or requires manual download"
                    )
                    self._data_available = False
                    self._cached_data = []
                    return self._cached_data

            reader = csv.DictReader(io.StringIO(text))
            self._cached_data = list(reader)
            log.info("Loaded %d MPLADS records", len(self._cached_data))
        except Exception as e:
            log.warning("Failed to load MPLADS CSV data: %s", e)
            self._cached_data = []

        return self._cached_data

    async def fetch_fund_data(self, mp: MPProfile) -> MPLADSFund:
        """Fetch MPLADS fund utilization for a specific MP.

        Tries matching against mp.name, mp.canonical_name, and mp.name_aliases,
        with constituency-based fallback within the same state.
        """
        records = await self._load_data()

        if not records:
            if not self._data_available:
                log.info(
                    "MPLADS data not available for %s — dataset covers "
                    "12th-16th Lok Sabha only; 18th Lok Sabha data not yet published",
                    mp.name,
                )
            else:
                log.warning("No MPLADS records loaded for %s", mp.name)
            note = "MPLADS data unavailable — legacy CSV dataset covers 12th-16th Lok Sabha only; 18th Lok Sabha constituency-level figures are not estimated"
            return MPLADSFund(
                confidence=0.0,
                sources=[DataSource(
                    url=settings.urls.mplads_csv,
                    source_name="mplads_csv",
                    grade=EvidenceGrade.E,
                    notes=note,
                )],
                data_period_note=note,
            )

        mp_state = normalize_state(mp.state)

        # Build list of names to try
        name_variants = [mp.name]
        if mp.canonical_name and mp.canonical_name != mp.name:
            name_variants.append(mp.canonical_name)
        name_variants.extend(mp.name_aliases)

        # Try matching by name variants, then by constituency
        match = None
        for record in records:
            r_name = ""
            for key in ["MP Name", "mp_name", "Name", "name", "Member"]:
                if key in record and record[key]:
                    r_name = record[key]
                    break

            r_constituency = ""
            for key in ["Constituency", "constituency", "Seat"]:
                if key in record and record[key]:
                    r_constituency = record[key]
                    break

            r_state = ""
            for key in ["State", "state"]:
                if key in record and record[key]:
                    r_state = record[key]
                    break

            # Filter by state first if available (using normalize_state for alias handling)
            if r_state and normalize_state(r_state) != mp_state:
                continue

            # Try all name variants
            for variant in name_variants:
                if name_matches(variant, r_name):
                    match = record
                    break
            if match:
                break

            # Constituency-based fallback
            if mp.constituency and r_constituency:
                if normalize_state(mp.constituency) == normalize_state(r_constituency):
                    match = record
                    break

        if not match:
            log.warning("MP not found in MPLADS data: %s", mp.name)
            return MPLADSFund(
                confidence=0.0,
                sources=[DataSource(
                    url=settings.urls.mplads_csv,
                    source_name="mplads_csv",
                    grade=EvidenceGrade.E,
                    notes="MP not found in MPLADS dataset",
                )],
            )

        return self._parse_record(match)

    def _parse_record(self, record: dict) -> MPLADSFund:
        """Parse an MPLADS CSV row into MPLADSFund."""
        entitled = None
        released = None
        sanctioned = None
        expended = None

        for key, field in [
            (["Entitled", "entitled", "Total Entitled"], "entitled"),
            (["Released", "released", "Total Released", "Funds Released"], "released"),
            (["Sanctioned", "sanctioned", "Total Sanctioned"], "sanctioned"),
            (["Expended", "expended", "Total Expended", "Expenditure", "Total Expenditure"], "expended"),
        ]:
            for k in key:
                if k in record and record[k]:
                    val = _parse_float(record[k])
                    if val is not None:
                        if field == "entitled":
                            entitled = val
                        elif field == "released":
                            released = val
                        elif field == "sanctioned":
                            sanctioned = val
                        elif field == "expended":
                            expended = val
                        break

        return MPLADSFund(
            entitled=entitled,
            released=released,
            sanctioned=sanctioned,
            expended=expended,
            source="mplads",
            confidence=0.8 if released is not None and expended is not None else 0.3,
            sources=[DataSource(
                url=settings.urls.mplads_csv,
                source_name="mplads_csv",
                grade=EvidenceGrade.C,
                notes="MPLADS fund utilization CSV from dataful.in",
            )],
        )
