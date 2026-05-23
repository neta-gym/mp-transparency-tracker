"""data.gov.in MPLADS API fetcher (Grade B)."""

from __future__ import annotations

import re
from typing import Optional

from ..config import settings
from ..models.schemas import (
    MPProfile,
    MPLADSFund,
    DataSource,
    EvidenceGrade,
)
from ..utils.logger import get_logger
from ..utils.name_match import normalize_state, name_matches
from .scraper import AsyncScraper

log = get_logger(__name__)


def _parse_float(val: str | None) -> Optional[float]:
    if not val:
        return None
    cleaned = re.sub(r"[^\d.]", "", str(val).strip())
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


# Mapping of state names to data.gov.in filter values
_STATE_FILTER_MAP: dict[str, str] = {
    "delhi": "NCT OF DELHI",
    "andhra pradesh": "ANDHRA PRADESH",
    "arunachal pradesh": "ARUNACHAL PRADESH",
    "assam": "ASSAM",
    "bihar": "BIHAR",
    "chhattisgarh": "CHHATTISGARH",
    "goa": "GOA",
    "gujarat": "GUJARAT",
    "haryana": "HARYANA",
    "himachal pradesh": "HIMACHAL PRADESH",
    "jammu and kashmir": "JAMMU & KASHMIR",
    "jharkhand": "JHARKHAND",
    "karnataka": "KARNATAKA",
    "kerala": "KERALA",
    "madhya pradesh": "MADHYA PRADESH",
    "maharashtra": "MAHARASHTRA",
    "manipur": "MANIPUR",
    "meghalaya": "MEGHALAYA",
    "mizoram": "MIZORAM",
    "nagaland": "NAGALAND",
    "odisha": "ODISHA",
    "punjab": "PUNJAB",
    "rajasthan": "RAJASTHAN",
    "sikkim": "SIKKIM",
    "tamil nadu": "TAMIL NADU",
    "telangana": "TELANGANA",
    "tripura": "TRIPURA",
    "uttar pradesh": "UTTAR PRADESH",
    "uttarakhand": "UTTARAKHAND",
    "west bengal": "WEST BENGAL",
    "andaman and nicobar islands": "ANDAMAN & NICOBAR ISLANDS",
    "chandigarh": "CHANDIGARH",
    "dadra and nagar haveli and daman and diu": "DADRA & NAGAR HAVELI AND DAMAN & DIU",
    "lakshadweep": "LAKSHADWEEP",
    "puducherry": "PUDUCHERRY",
    "ladakh": "LADAKH",
}


class DataGovMPLADSFetcher:
    """Fetches MPLADS fund data from data.gov.in (Grade B).

    Uses the Open Government Data Platform India API.
    API pattern: https://api.data.gov.in/resource/<RESOURCE_ID>?api-key=<KEY>&format=json&limit=100&filters[State]=<STATE>
    """

    def __init__(self, scraper: AsyncScraper) -> None:
        self.scraper = scraper
        self._cached_data: dict[str, list[dict]] | None = None

    async def fetch_fund_data(self, mp: MPProfile) -> MPLADSFund:
        """Fetch MPLADS fund utilization for an MP from data.gov.in.

        NOTE: The MPLADS dataset resource ID (9e0e3220-...) is no longer valid
        on data.gov.in — the API returns "Meta not found". This fetcher is
        disabled until a replacement resource ID is found.
        """
        log.info(
            "data.gov.in: MPLADS dataset resource ID no longer valid — "
            "skipping fetch for %s (%s)", mp.name, mp.state,
        )
        return self._empty_result(
            "MPLADS dataset resource ID no longer valid on data.gov.in (returns 'Meta not found')"
        )

    async def _fetch_state_data(self, state: str) -> list[dict]:
        """Fetch all MPLADS records for a state from data.gov.in."""
        normalized = normalize_state(state)

        # Check cache
        if self._cached_data and normalized in self._cached_data:
            return self._cached_data[normalized]

        state_filter = _STATE_FILTER_MAP.get(normalized, normalized.upper())
        api_key = settings.datagov_api_key or "579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b"

        url = (
            f"{settings.urls.mplads_datagov_api}"
            f"?api-key={api_key}"
            f"&format=json"
            f"&limit=500"
            f"&filters[State]={state_filter}"
        )

        try:
            import json
            text = await self.scraper.fetch(url)
            data = json.loads(text)

            records = data.get("records", [])
            log.info("data.gov.in: Loaded %d records for %s", len(records), state)

            # Cache
            if self._cached_data is None:
                self._cached_data = {}
            self._cached_data[normalized] = records

            return records

        except Exception as e:
            log.warning("data.gov.in: Failed to fetch for state %s: %s", state, e)
            return []

    def _find_mp_record(self, mp: MPProfile, records: list[dict]) -> Optional[dict]:
        """Find the matching record for an MP in data.gov.in results."""
        name_variants = [mp.name]
        if mp.canonical_name and mp.canonical_name != mp.name:
            name_variants.append(mp.canonical_name)
        name_variants.extend(mp.name_aliases)

        # Try name match first
        for record in records:
            r_name = ""
            for key in ["mp_name", "MP Name", "Name", "member_name"]:
                if key in record and record[key]:
                    r_name = str(record[key])
                    break

            for variant in name_variants:
                if name_matches(variant, r_name):
                    return record

        # Constituency fallback
        for record in records:
            r_const = ""
            for key in ["constituency", "Constituency", "Seat"]:
                if key in record and record[key]:
                    r_const = str(record[key])
                    break

            if mp.constituency and r_const:
                if normalize_state(mp.constituency) == normalize_state(r_const):
                    return record

        return None

    def _parse_record(self, record: dict) -> MPLADSFund:
        """Parse a data.gov.in record into MPLADSFund."""
        entitled = None
        released = None
        sanctioned = None
        expended = None

        for keys, field in [
            (["entitled", "Entitled", "Total Entitled", "total_entitled"], "entitled"),
            (["released", "Released", "Total Released", "total_released", "funds_released"], "released"),
            (["sanctioned", "Sanctioned", "Total Sanctioned", "total_sanctioned"], "sanctioned"),
            (["expended", "Expended", "Total Expended", "total_expended", "expenditure"], "expended"),
        ]:
            for k in keys:
                if k in record and record[k]:
                    val = _parse_float(str(record[k]))
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

        has_data = released is not None or expended is not None
        return MPLADSFund(
            entitled=entitled,
            released=released,
            sanctioned=sanctioned,
            expended=expended,
            source="data.gov.in",
            confidence=0.85 if has_data else 0.0,
            sources=[DataSource(
                url=settings.urls.mplads_datagov_api,
                source_name="data.gov.in",
                grade=EvidenceGrade.B,
                notes="MPLADS fund data from Open Government Data Platform India",
            )],
        )

    def _empty_result(self, notes: str) -> MPLADSFund:
        return MPLADSFund(
            confidence=0.0,
            sources=[DataSource(
                url=settings.urls.mplads_datagov_api,
                source_name="data.gov.in",
                grade=EvidenceGrade.B,
                notes=notes,
            )],
            data_period_note=f"MPLADS data.gov.in unavailable: {notes}. No constituency-level fund amounts are estimated.",
        )
