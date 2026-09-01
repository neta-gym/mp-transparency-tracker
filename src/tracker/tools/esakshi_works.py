"""eSAKSHI work-level (transaction-level) MPLADS client.

Fetches per-work lifecycle records from the official MoSPI MPLADS portal
(mplads.mospi.gov.in) via its public pre-login REST endpoints. No Playwright
required: a plain aiohttp session with cookies suffices.

Endpoint chain (discovered from the portal's dashboard JS, Sep 2026):
  1. GET  /digigov/dashboard.html                  -> session cookies
  2. POST /rest/PreLoginDashboardData/getStateData        {}            -> states
  3. POST /rest/PreLoginDashboardData/getTenureData       {uname: "0,0,0,<house>"}
  4. POST /rest/PreLoginDashboardData/getConstituencyData {id: state_id}
  5. POST /rest/PreLoginDashboardData/getMpAndConstCombo  {const_combo: "const_id,house,tenure_id"}
  6. POST /rest/PreLoginDashboardData/getTilesData        {uname: "state,const,mp,house,tenure"}
  7. POST /rest/PreLoginDashboardData/getTilesReportData  {combo: <same>, key: <report name>}

Report keys: "Works Recommended", "Works Sanctioned", "Works Completed".
Records join on WORK_RECOMMENDATION_DTL_ID to form the full lifecycle:
recommended -> sanctioned -> completed (with dates and amounts per stage).
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import aiohttp

from ..models.schemas import DataSource, EvidenceGrade, MPLADSWork
from .esakshi import _classify_sector as classify_sector

log = logging.getLogger(__name__)

BASE = "https://mplads.mospi.gov.in"
DASHBOARD_PAGE = f"{BASE}/digigov/dashboard.html"
REST = f"{BASE}/rest/PreLoginDashboardData"

HOUSE_LOK_SABHA = 2
HOUSE_RAJYA_SABHA = 1

REPORT_KEYS = ("Works Recommended", "Works Sanctioned", "Works Completed")

_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=45)
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
}


def _norm(text: str) -> str:
    """Normalize a name for matching (casefold, collapse non-alphanumerics)."""
    return re.sub(r"[^a-z0-9]+", "", (text or "").casefold())


def _to_crore(amount: float | None) -> float | None:
    if amount is None:
        return None
    return round(amount / 10_000_000, 6)


_STATUS_MAP = {
    "pending for sanction": "recommended",
    "recommended": "recommended",
    "sanctioned": "sanctioned",
    "work in progress": "in_progress",
    "in progress": "in_progress",
    "work completed": "completed",
    "completed": "completed",
    "work abandoned": "abandoned",
    "work cancelled": "cancelled",
}


def map_work_status(stage: str | None, flag: int | None = None) -> str:
    """Map an eSAKSHI WORK_STAGE string to our status vocabulary."""
    if stage:
        mapped = _STATUS_MAP.get(stage.strip().casefold())
        if mapped:
            return mapped
    # FLAG: 1 = recommended, 2 = sanctioned/in progress, 3 = completed
    return {1: "recommended", 2: "in_progress", 3: "completed"}.get(flag or 0, "unknown")


def merge_work_lifecycle(
    recommended: list[dict[str, Any]],
    sanctioned: list[dict[str, Any]],
    completed: list[dict[str, Any]],
    source: DataSource,
) -> list[MPLADSWork]:
    """Join the three report record lists into per-work lifecycle entries.

    Join key: WORK_RECOMMENDATION_DTL_ID. Amounts are stored in crore to
    match MPLADSWork conventions elsewhere in the pipeline.
    """
    works: dict[Any, MPLADSWork] = {}

    def _get(rec: dict[str, Any]) -> MPLADSWork:
        key = rec.get("WORK_RECOMMENDATION_DTL_ID") or rec.get("WORK_ID") or id(rec)
        if key not in works:
            desc = (rec.get("WORK_DESCRIPTION") or "").strip()
            works[key] = MPLADSWork(
                work_id=str(key),
                description=desc,
                sector=classify_sector(desc),
                district=(rec.get("CONSTITUENCY") or "").strip().title(),
                source=source,
            )
        return works[key]

    for rec in recommended:
        w = _get(rec)
        w.recommended_amount = _to_crore(rec.get("RECOMMENDED_AMOUNT"))
        w.recommendation_date = (rec.get("RECOMMENDATION_DATE") or "").strip() or None
        w.executing_agency = (rec.get("IDA_NAME") or "").strip() or None
        w.letter_no = (rec.get("LETTER_NO") or "").strip() or None
        w.status = map_work_status(rec.get("WORK_STAGE"), rec.get("FLAG"))
        if w.sanctioned_amount is None:
            w.sanctioned_amount = _to_crore(rec.get("SANCTION_AMOUNT"))

    for rec in sanctioned:
        w = _get(rec)
        w.sanctioned_amount = _to_crore(rec.get("SANCTION_AMOUNT"))
        w.sanction_date = (rec.get("SANCTION_DATE") or "").strip() or None
        w.executing_agency = w.executing_agency or (rec.get("IDA_NAME") or "").strip() or None
        if w.status in ("unknown", "recommended"):
            w.status = map_work_status(rec.get("WORK_STAGE"), rec.get("FLAG")) or "sanctioned"

    for rec in completed:
        w = _get(rec)
        w.expended_amount = _to_crore(rec.get("ACTUAL_AMOUNT"))
        w.completion_date = (rec.get("ACTUAL_END_DATE") or "").strip() or None
        rating = rec.get("AVERAGE_RATING")
        w.average_rating = float(rating) if isinstance(rating, (int, float)) and rating else None
        w.status = "completed"

    return sorted(
        works.values(),
        key=lambda w: (w.recommendation_date or "", w.work_id),
        reverse=True,
    )


@dataclass
class ResolvedMP:
    state_id: int
    constituency_id: int
    mp_id: int
    house: int
    tenure_id: int
    mp_caption: str = ""


@dataclass
class ESAKSHIWorksClient:
    """Session-based client for eSAKSHI work-level reports."""

    request_delay: float = 0.25
    max_retries: int = 3
    _session: aiohttp.ClientSession | None = field(default=None, init=False, repr=False)
    _state_cache: dict[str, int] = field(default_factory=dict, init=False)
    _const_cache: dict[tuple[int, str], int] = field(default_factory=dict, init=False)
    _tenure_cache: dict[tuple[int, str], int] = field(default_factory=dict, init=False)

    async def __aenter__(self) -> ESAKSHIWorksClient:
        await self._ensure_session()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session and not self._session.closed:
            return self._session
        self._session = aiohttp.ClientSession(
            headers=_HEADERS,
            timeout=_REQUEST_TIMEOUT,
            cookie_jar=aiohttp.CookieJar(),
        )
        # Prime the session: the portal issues required cookies on page load.
        async with self._session.get(DASHBOARD_PAGE) as resp:
            resp.raise_for_status()
            await resp.read()
        return self._session

    async def _post(self, endpoint: str, payload: dict[str, Any]) -> Any:
        session = await self._ensure_session()
        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                await asyncio.sleep(self.request_delay)
                async with session.post(f"{REST}/{endpoint}", json=payload) as resp:
                    if resp.status in (403, 500, 502, 503):
                        raise aiohttp.ClientResponseError(resp.request_info, resp.history, status=resp.status)
                    resp.raise_for_status()
                    return await resp.json(content_type=None)
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_err = e
                log.debug("eSAKSHI %s attempt %d failed: %s", endpoint, attempt + 1, e)
                if attempt + 1 < self.max_retries:
                    # Re-prime the session in case cookies expired.
                    await self.close()
                    await self._ensure_session()
                    await asyncio.sleep(self.request_delay * (attempt + 2))
        raise RuntimeError(f"eSAKSHI {endpoint} failed after {self.max_retries} attempts: {last_err}")

    # -- resolution chain -------------------------------------------------

    async def resolve_state_id(self, state_name: str) -> int | None:
        key = _norm(state_name)
        if key in self._state_cache:
            return self._state_cache[key]
        data = await self._post("getStateData", {})
        for row in data or []:
            self._state_cache[_norm(row.get("STATE_NAME", ""))] = int(row["STATE_ID"])
        return self._state_cache.get(key)

    async def resolve_tenure_id(self, house: int, caption_fragment: str) -> int | None:
        key = (house, _norm(caption_fragment))
        if key in self._tenure_cache:
            return self._tenure_cache[key]
        data = await self._post("getTenureData", {"uname": f"0,0,0,{house}"})
        for row in data or []:
            self._tenure_cache[(house, _norm(row.get("CAPTION", "")))] = int(row["ID"])
        return self._tenure_cache.get(key)

    async def resolve_constituency_id(self, state_id: int, constituency: str) -> int | None:
        key = (state_id, _norm(constituency))
        if key in self._const_cache:
            return self._const_cache[key]
        data = await self._post("getConstituencyData", {"id": str(state_id)})
        for row in data or []:
            self._const_cache[(state_id, _norm(row.get("CAPTION", "")))] = int(row["ID"])
        return self._const_cache.get(key)

    async def resolve_mp(
        self,
        state_id: int,
        constituency_id: int,
        house: int,
        tenure_id: int,
    ) -> ResolvedMP | None:
        combo = f"{constituency_id},{house},{tenure_id}"
        data = await self._post("getMpAndConstCombo", {"const_combo": combo})
        if not data:
            return None
        row = data[0]
        return ResolvedMP(
            state_id=state_id,
            constituency_id=constituency_id,
            mp_id=int(row["ID"]),
            house=house,
            tenure_id=tenure_id,
            mp_caption=row.get("CAPTION", ""),
        )

    # -- reports ------------------------------------------------------------

    async def _report(self, combo: str, key: str) -> list[dict[str, Any]]:
        data = await self._post("getTilesReportData", {"combo": combo, "key": key})
        if not isinstance(data, dict) or not data:
            return []
        raw = next(iter(data.values()))
        if isinstance(raw, str):
            import json

            try:
                parsed = json.loads(raw)
            except (ValueError, TypeError):
                return []
        else:
            parsed = raw
        if not isinstance(parsed, list):
            return []
        # Aggregate-only responses ({"Total_Amt": ...}) carry no work rows.
        return [r for r in parsed if isinstance(r, dict) and "WORK_RECOMMENDATION_DTL_ID" in r]

    async def fetch_works(self, mp: ResolvedMP, source: DataSource | None = None) -> list[MPLADSWork]:
        combo = f"{mp.state_id},{mp.constituency_id},{mp.mp_id},{mp.house},{mp.tenure_id}"
        recommended, sanctioned, completed = await asyncio.gather(
            self._report(combo, "Works Recommended"),
            self._report(combo, "Works Sanctioned"),
            self._report(combo, "Works Completed"),
        )
        src = source or DataSource(
            url=DASHBOARD_PAGE,
            source_name="esakshi",
            grade=EvidenceGrade.A,
            notes="Official eSAKSHI REST API - work-level reports",
        )
        return merge_work_lifecycle(recommended, sanctioned, completed, src)
