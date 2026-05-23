"""eSAKSHI (mplads.mospi.gov.in) — Official MoSPI MPLADS dashboard scraper (Grade A).

Primary strategy: Playwright loads the dashboard page (establishes session),
then calls the internal REST API endpoints via page.evaluate() with jQuery.

The eSAKSHI portal uses Select2 dropdowns and jQuery DataTables, with REST
endpoints at /rest/PreLoginDashboardData/* that require a valid session cookie.

API format discovered by inspecting preLoginDashboard.js:
  - getTilesData:        POST {uname: "state_id,const_id,mp_id,house,tenure_id"}
  - getTilesReportData:  POST {uname: "state_id,const_id,mp_id,house,tenure_id"}
  - getConstituencyData: POST {id: "state_id"}
  - getMpNamesData:      POST {state_combo: "state_id,house,tenure_id"}
  - getStateData:        POST {}

Fallbacks: Direct REST API probe, HTML scraping.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Optional

from ..config import settings
from ..models.schemas import (
    MPProfile,
    MPLADSFund,
    MPLADSWork,
    DataSource,
    EvidenceGrade,
)
from ..utils.logger import get_logger
from ..utils.name_match import normalize_state, name_matches
from .scraper import AsyncScraper

log = get_logger(__name__)

# eSAKSHI coverage starts from 1 Apr 2023 (17th LS / current term)
ESAKSHI_COVERAGE_START = "2023-04-01"

# eSAKSHI dashboard entry point
ESAKSHI_DASHBOARD_URL = "https://mplads.mospi.gov.in/digigov/dashboard.html"

# REST API base (used from within the browser page context)
_REST_BASE = "/rest/PreLoginDashboardData"

# eSAKSHI state name → state_id mapping (discovered from getStateData API)
_ESAKSHI_STATE_IDS: dict[str, int] = {
    "andaman and nicobar islands": 35,
    "andhra pradesh": 2,
    "arunachal pradesh": 3,
    "assam": 5,
    "bihar": 6,
    "chandigarh": 7,
    "chhattisgarh": 8,
    "delhi": 11,
    "goa": 12,
    "gujarat": 27,
    "haryana": 14,
    "himachal pradesh": 15,
    "jammu and kashmir": 16,
    "jharkhand": 17,
    "karnataka": 18,
    "kerala": 19,
    "ladakh": 37,
    "lakshadweep": 36,
    "madhya pradesh": 20,
    "maharashtra": 21,
    "manipur": 22,
    "meghalaya": 23,
    "mizoram": 24,
    "nagaland": 25,
    "odisha": 26,
    "puducherry": 34,
    "punjab": 28,
    "rajasthan": 29,
    "sikkim": 30,
    "tamil nadu": 31,
    "telangana": 13,
    "tripura": 32,
    "uttar pradesh": 9,
    "uttarakhand": 33,
    "west bengal": 4,
    "dadra and nagar haveli and daman and diu": 10,
}

# Tenure IDs
_TENURE_18TH_LS = 7
_HOUSE_LOK_SABHA = 2

# Known constituency name variants (our name -> eSAKSHI name, lowercased)
_CONSTITUENCY_ALIASES: dict[str, str] = {
    "chandni chowk": "chandini chowk",
    "chandi chowk": "chandini chowk",
    "chandani chowk": "chandini chowk",
}


def _parse_amount(val: str | None) -> Optional[float]:
    """Parse a monetary amount string from eSAKSHI (may include ₹, commas, nbsp)."""
    if not val:
        return None
    cleaned = re.sub(r"[^\d.]", "", str(val).strip())
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def _parse_crore_amount(val: str | None) -> Optional[float]:
    """Parse an amount like '5,512.56 Cr' or '55,12,55,78,307.11' into crores."""
    if not val:
        return None
    val = str(val).strip()
    # If already labelled as Cr, parse the number
    if "cr" in val.lower():
        return _parse_amount(val)
    # Otherwise it's in raw rupees — convert to crores
    raw = _parse_amount(val)
    if raw is not None:
        return round(raw / 1_00_00_000, 2)  # Indian crore = 10^7
    return None


def _classify_sector(description: str) -> str:
    """Classify a work description into a sector category."""
    desc = description.lower()
    sector_keywords = {
        "education": ["school", "education", "college", "library", "anganwadi", "classroom"],
        "health": ["hospital", "health", "dispensary", "phc", "chc", "medical", "ambulance"],
        "infrastructure": ["road", "bridge", "culvert", "drain", "pathway", "street light", "solar"],
        "water": ["water", "boring", "handpump", "pipeline", "tank", "sewage", "toilet"],
        "community": ["community hall", "bhawan", "crematorium", "boundary wall", "park", "playground"],
        "sports": ["stadium", "sports", "gym", "court"],
    }
    for sector, keywords in sector_keywords.items():
        if any(kw in desc for kw in keywords):
            return sector
    return "other"


class ESAKSHIFetcher:
    """Fetches MPLADS data from the official eSAKSHI portal (Grade A).

    Primary strategy: Playwright loads the dashboard (establishes session cookie),
    then calls internal REST APIs via page.evaluate() to extract per-constituency
    fund data. No UI interaction with Select2 dropdowns needed.

    Fallbacks: Direct REST API probe, HTML scraping (retained from original).
    """

    def __init__(self, scraper: AsyncScraper, browser=None) -> None:
        self.scraper = scraper
        self._browser = browser  # PlaywrightBrowser instance (optional)
        self._api_base = settings.urls.esakshi_api
        self._dashboard_url = settings.urls.esakshi_dashboard

        # Constituency-based cache to avoid re-scraping
        self._cache: dict[str, MPLADSFund] = {}

        # Limit concurrent Playwright page interactions
        self._page_semaphore = asyncio.Semaphore(1)

        # Shared page for REST API calls (reused across MPs in same state)
        self._session_page = None
        self._session_lock = asyncio.Lock()

        # Cache constituency ID lookups
        self._constituency_ids: dict[str, dict[str, int]] = {}  # state_id -> {name: id}

        # Global rate-limit tracking: when a getTilesData call returns empty,
        # record the time so subsequent callers wait for cooldown to expire
        # before making their first attempt. This prevents retry-hammering
        # from extending the rate-limit window.
        self._rate_limit_until: float = 0  # monotonic timestamp
        _RATE_LIMIT_COOLDOWN = 30  # seconds of silence needed after rate-limit

    async def fetch_fund_data(self, mp: MPProfile) -> MPLADSFund:
        """Fetch aggregate MPLADS fund data for an MP from eSAKSHI (Grade A)."""
        log.info("eSAKSHI: Fetching fund data for %s (%s)", mp.name, mp.constituency)

        # Check cache by constituency
        cache_key = f"{normalize_state(mp.state)}:{mp.constituency.lower()}"
        if cache_key in self._cache:
            log.info("eSAKSHI: Cache hit for %s", cache_key)
            return self._cache[cache_key]

        try:
            if self._browser:
                # Primary: Playwright REST API
                fund = await self._fetch_via_playwright_rest(mp)
                if fund and fund.confidence > 0:
                    self._cache[cache_key] = fund
                    return fund
                # When Playwright is available, skip aiohttp fallbacks —
                # the portal rate-limits direct HTTP connections.
            else:
                # No browser: try aiohttp-based strategies
                fund = await self._fetch_via_api(mp)
                if fund and fund.confidence > 0:
                    self._cache[cache_key] = fund
                    return fund

                fund = await self._fetch_via_html(mp)
                if fund and fund.confidence > 0:
                    self._cache[cache_key] = fund
                    return fund

        except Exception as e:
            log.warning("eSAKSHI fetch failed for %s: %s", mp.name, e)

        note = (
            "eSAKSHI constituency-level MPLADS data not available from the automated "
            "open-data fetchers; no fund amounts are estimated. Use RTI/official district "
            "records for constituency-level verification."
        )
        return MPLADSFund(
            confidence=0.0,
            sources=[DataSource(
                url=self._dashboard_url,
                source_name="esakshi",
                grade=EvidenceGrade.A,
                notes=note,
            )],
            data_period_note=note,
        )

    async def fetch_works(self, mp: MPProfile) -> list[MPLADSWork]:
        """Fetch individual work-level details from eSAKSHI."""
        log.info("eSAKSHI: Fetching works for %s (%s)", mp.name, mp.constituency)
        try:
            works = await self._fetch_works_via_api(mp)
            if works:
                return works
        except Exception as e:
            log.warning("eSAKSHI works fetch failed for %s: %s", mp.name, e)
        return []

    # ------------------------------------------------------------------
    # Strategy 1: Playwright + REST API (primary)
    # ------------------------------------------------------------------

    async def _ensure_session_page(self):
        """Navigate to dashboard once to establish a session cookie."""
        async with self._session_lock:
            if self._session_page is not None:
                # Check if page is still usable
                try:
                    await self._session_page.evaluate("() => true")
                    return
                except Exception:
                    self._session_page = None

            log.info("eSAKSHI: Loading dashboard to establish session...")
            self._session_page = await self._browser.new_page()
            await self._session_page.goto(
                ESAKSHI_DASHBOARD_URL,
                wait_until="networkidle",
                timeout=90000,
            )
            # Wait for page JS to initialize and initial API calls to complete.
            # The page makes POST calls to getTilesData, getStateData, etc. on
            # load. We must wait for these to finish before making our own calls,
            # otherwise the server rate-limits us.
            await self._session_page.wait_for_timeout(5000)

            # Warm up: the server rate-limits API calls made too soon after
            # the initial page load. We progressively retry until the session
            # is ready for our calls.
            for attempt in range(5):
                states = await self._call_rest_api(self._session_page, "getStateData", {})
                if states and isinstance(states, list) and len(states) > 5:
                    break
                log.debug("eSAKSHI: Session warmup attempt %d — waiting...", attempt + 1)
                await self._session_page.wait_for_timeout(3000)

            log.info("eSAKSHI: Session established")

    async def _fetch_via_playwright_rest(self, mp: MPProfile) -> Optional[MPLADSFund]:
        """Call eSAKSHI REST APIs from within the browser page context."""
        async with self._page_semaphore:
            try:
                await self._ensure_session_page()
                page = self._session_page

                # Resolve state ID
                state_norm = normalize_state(mp.state)
                state_id = _ESAKSHI_STATE_IDS.get(state_norm)
                if state_id is None:
                    state_id = await self._resolve_state_id(page, state_norm)
                if state_id is None:
                    log.warning("eSAKSHI: Unknown state: %s", mp.state)
                    return None

                # Resolve constituency ID (with retry on transient failure)
                const_id = await self._resolve_constituency_id(
                    page, str(state_id), mp.constituency
                )
                if not const_id:
                    # Server may still be warming up — wait and retry once
                    log.debug("eSAKSHI: Constituency resolution failed, retrying after delay...")
                    await asyncio.sleep(5)
                    # Clear cache to force re-fetch
                    self._constituency_ids.pop(str(state_id), None)
                    const_id = await self._resolve_constituency_id(
                        page, str(state_id), mp.constituency
                    )

                if const_id:
                    log.info("eSAKSHI: Resolved constituency '%s' -> ID %d", mp.constituency, const_id)
                else:
                    log.warning("eSAKSHI: Could not resolve constituency '%s' — trying table fallback", mp.constituency)

                # Strategy A: constituency-specific API call (with retry on rate-limit)
                #
                # eSAKSHI rate-limits aggressively (~3 calls per 30s window).
                # Key insight: failed retries EXTEND the rate-limit window, so
                # we use a global cooldown to enforce silence periods instead of
                # hammering with short-interval retries.
                if const_id:
                    uname = f"{state_id},{const_id},0,{_HOUSE_LOK_SABHA},{_TENURE_18TH_LS}"
                    _COOLDOWN = 60  # seconds of silence to let rate-limit window drain

                    for attempt in range(4):
                        # Honor global rate-limit cooldown before calling
                        cooldown_remaining = self._rate_limit_until - time.monotonic()
                        if cooldown_remaining > 0:
                            log.info("eSAKSHI: Rate-limit cooldown active, waiting %.0fs...", cooldown_remaining)
                            await asyncio.sleep(cooldown_remaining)

                        log.info("eSAKSHI REST: Calling getTilesData with uname=%s (attempt %d/4)", uname, attempt + 1)
                        tiles_data = await self._call_rest_api(page, "getTilesData", {"uname": uname})

                        if tiles_data:
                            fund = self._parse_tiles_data(tiles_data)
                            if fund and fund.confidence > 0:
                                log.info("eSAKSHI REST: Extracted fund data — entitled=%.2f Cr, expended=%s Cr",
                                         fund.entitled or 0, fund.expended)
                                # Reset rate-limit state on success; pause before
                                # releasing semaphore to give server breathing room
                                self._rate_limit_until = 0
                                await asyncio.sleep(15)
                                return fund
                            else:
                                log.warning("eSAKSHI REST: getTilesData returned data but parse failed (attempt %d): %s",
                                            attempt + 1, str(tiles_data)[:300])
                        else:
                            log.warning("eSAKSHI REST: getTilesData returned empty (attempt %d/4) — rate-limited",
                                        attempt + 1)

                        # Set global cooldown — all callers (including this retry)
                        # must wait for the full cooldown before the next call
                        self._rate_limit_until = time.monotonic() + _COOLDOWN
                        log.info("eSAKSHI: Global cooldown set — next call in %ds", _COOLDOWN)

                # Strategy B: search the default DataTable for this MP
                fund = await self._search_datatable(page, mp)
                if fund and fund.confidence > 0:
                    log.info("eSAKSHI: Extracted fund data from DataTable search")
                    return fund

                # Strategy C: extract from DOM (global page stats)
                fund = await self._extract_from_dom(page)
                if fund and fund.confidence > 0:
                    log.info("eSAKSHI: Extracted fund data from DOM fallback")
                    return fund

                return None

            except Exception as e:
                log.warning("eSAKSHI Playwright REST failed for %s: %s", mp.name, e)
                if self._session_page:
                    try:
                        await self._session_page.close()
                    except Exception:
                        pass
                    self._session_page = None
                return None

    async def _call_rest_api(self, page, endpoint: str, payload: dict) -> Optional[dict | list]:
        """Call an eSAKSHI REST API endpoint from within the page context."""
        try:
            result = await page.evaluate("""async (args) => {
                const [endpoint, payload] = args;
                try {
                    const r = await fetch('/rest/PreLoginDashboardData/' + endpoint, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json; charset=utf-8'},
                        body: JSON.stringify(payload),
                    });
                    if (!r.ok) return {_error: r.status};
                    const text = await r.text();
                    if (!text || text.trim().length === 0) return null;
                    try { return JSON.parse(text); }
                    catch(e) { return {_raw: text.substring(0, 500)}; }
                } catch(e) {
                    return {_error: e.message};
                }
            }""", [endpoint, payload])

            if result is None:
                return None
            if isinstance(result, dict) and "_error" in result:
                log.debug("eSAKSHI REST %s error: %s", endpoint, result["_error"])
                return None
            return result

        except Exception as e:
            log.debug("eSAKSHI REST %s evaluate failed: %s", endpoint, e)
            return None

    async def _resolve_state_id(self, page, state_norm: str) -> Optional[int]:
        """Look up state ID from the eSAKSHI state list."""
        states = await self._call_rest_api(page, "getStateData", {})
        if not states or not isinstance(states, list):
            return None
        for s in states:
            name = str(s.get("STATE_NAME", "")).lower().strip()
            if name == state_norm or normalize_state(name) == state_norm:
                sid = s.get("STATE_ID")
                if sid is not None:
                    _ESAKSHI_STATE_IDS[state_norm] = int(sid)
                    return int(sid)
        return None

    async def _resolve_constituency_id(
        self, page, state_id: str, constituency: str
    ) -> Optional[int]:
        """Look up constituency ID from the eSAKSHI constituency list."""
        if state_id in self._constituency_ids:
            const_map = self._constituency_ids[state_id]
        else:
            # Fetch with one retry (API can be flaky on first call)
            data = await self._call_rest_api(page, "getConstituencyData", {"id": state_id})
            if not data or not isinstance(data, list):
                await asyncio.sleep(2)
                data = await self._call_rest_api(page, "getConstituencyData", {"id": state_id})
            if not data or not isinstance(data, list):
                log.warning("eSAKSHI: getConstituencyData failed for state %s", state_id)
                return None
            const_map = {}
            for item in data:
                caption = str(item.get("CAPTION", "")).strip()
                cid = item.get("ID")
                if caption and cid is not None:
                    const_map[caption.lower()] = int(cid)
            self._constituency_ids[state_id] = const_map

        # Exact match
        key = constituency.lower().strip()
        if key in const_map:
            return const_map[key]

        # Check known aliases
        alias = _CONSTITUENCY_ALIASES.get(key)
        if alias and alias in const_map:
            return const_map[alias]

        # Substring match (e.g., "chandni chowk" in "chandni chowk (sc)")
        for name, cid in const_map.items():
            if key in name or name in key:
                return cid

        # Fuzzy match via token overlap
        for name, cid in const_map.items():
            if name_matches(constituency, name):
                return cid

        # Normalize: strip parenthetical suffixes like "(SC)", hyphens, etc.
        key_clean = re.sub(r"\s*\(.*?\)", "", key).strip()
        key_clean = re.sub(r"[-_]", " ", key_clean).strip()
        for name, cid in const_map.items():
            name_clean = re.sub(r"\s*\(.*?\)", "", name).strip()
            name_clean = re.sub(r"[-_]", " ", name_clean).strip()
            if key_clean == name_clean:
                return cid

        # Token-substring match: each token in key is a substring of some token
        # in name (handles "chandni" ⊂ "chandini", variant spellings)
        key_tokens = key_clean.split()
        for name, cid in const_map.items():
            name_clean = re.sub(r"\s*\(.*?\)", "", name).strip()
            name_tokens = name_clean.split()
            if not key_tokens or not name_tokens:
                continue
            matched = 0
            for kt in key_tokens:
                if any(kt in nt or nt in kt for nt in name_tokens):
                    matched += 1
            if matched >= len(key_tokens):
                return cid

        log.warning(
            "eSAKSHI: Constituency '%s' not found in state %s (available: %s)",
            constituency, state_id, list(const_map.keys()),
        )
        return None

    async def _search_datatable(self, page, mp: MPProfile) -> Optional[MPLADSFund]:
        """Search the DataTable (#tablepag) for this MP's Allocated Amount.

        The page loads a jQuery DataTable with columns:
        Sr. No. | State Name | MP Name | Constituency | Allocated Amount (₹)

        The table is paginated, so we use the DataTable API search() to find
        the MP across all pages, not just the visible rows.
        """
        try:
            result = await page.evaluate("""(args) => {
                const [mpName, constituency] = args;
                const mpLower = mpName.toLowerCase();
                const constLower = constituency.toLowerCase();

                // Split MP name into tokens for matching
                const mpTokens = mpLower.split(/\s+/).filter(t => t.length > 2);

                // Strategy 1: Use jQuery DataTable API to search all rows (not just visible page)
                try {
                    const dt = jQuery('#tablepag').DataTable();
                    const allData = [];
                    dt.rows().every(function() {
                        const d = this.data();
                        if (d && d.length >= 5) {
                            allData.push({
                                mp_name: (d[2] || '').trim(),
                                constituency: (d[3] || '').trim(),
                                allocated: (d[4] || '').trim(),
                                state: (d[1] || '').trim(),
                            });
                        }
                    });

                    // Match by constituency first (most reliable)
                    for (const row of allData) {
                        if (!row.mp_name || !row.constituency) continue;
                        if (row.constituency.toLowerCase() === constLower) {
                            return row;
                        }
                    }

                    // Fuzzy constituency match
                    for (const row of allData) {
                        if (!row.mp_name || !row.constituency) continue;
                        const rc = row.constituency.toLowerCase();
                        if (rc.includes(constLower) || constLower.includes(rc)) {
                            return row;
                        }
                    }

                    // Match by MP name (token overlap)
                    for (const row of allData) {
                        if (!row.mp_name) continue;
                        const rowTokens = row.mp_name.toLowerCase().split(/\s+/);
                        const overlap = mpTokens.filter(t => rowTokens.some(rt => rt.includes(t) || t.includes(rt)));
                        if (overlap.length >= 2 || (mpTokens.length === 1 && overlap.length >= 1)) {
                            return row;
                        }
                    }

                    return {error: 'not found via DataTable API', totalRows: allData.length};
                } catch(e) {
                    // DataTable API not available, fall through to DOM search
                }

                // Strategy 2: DOM-based search on visible rows only
                const table = document.getElementById('tablepag');
                if (!table) return {error: 'no table element'};

                for (let i = 1; i < table.rows.length; i++) {
                    const row = table.rows[i];
                    if (row.cells.length < 5) continue;

                    const rowMpName = (row.cells[2].textContent || '').trim();
                    const rowConst = (row.cells[3].textContent || '').trim();
                    const rowAllocated = (row.cells[4].textContent || '').trim();

                    if (!rowMpName || !rowConst) continue;

                    if (rowConst.toLowerCase() === constLower) {
                        return {mp_name: rowMpName, constituency: rowConst, allocated: rowAllocated};
                    }
                }

                return {error: 'not found via DOM', rowCount: table.rows.length};
            }""", [mp.name, mp.constituency])

            if not result or result.get("error"):
                log.debug("eSAKSHI DataTable: %s", result)
                return None

            # Validate the match
            found_mp = result.get("mp_name", "")
            found_const = result.get("constituency", "")
            if not found_mp or not found_const:
                return None

            allocated_raw = result.get("allocated", "")
            allocated = _parse_crore_amount(allocated_raw)
            if allocated is None or allocated <= 0:
                return None

            log.info(
                "eSAKSHI DataTable: Found %s (%s) — Allocated: %s",
                found_mp, found_const, allocated_raw,
            )

            return MPLADSFund(
                entitled=allocated,
                released=allocated,
                source="esakshi",
                confidence=0.85,
                sources=[DataSource(
                    url=ESAKSHI_DASHBOARD_URL,
                    source_name="esakshi",
                    grade=EvidenceGrade.A,
                    notes=f"From eSAKSHI DataTable — MP: {found_mp}, Allocated: {allocated_raw}",
                )],
                esakshi_coverage_start=ESAKSHI_COVERAGE_START,
            )

        except Exception as e:
            log.debug("eSAKSHI DataTable search failed: %s", e)
            return None

    def _parse_tiles_data(self, data: dict) -> Optional[MPLADSFund]:
        """Parse the getTilesData response into MPLADSFund.

        Response format (from inspection):
        {
            "Allocated Limit for": [" 55,12,55,78,307.11", " 5,512.56 Cr"],
            "Expenditure on Completed and On-going Works as on Date": [" 16,76,62,87,296.45", " 1,676.63 Cr"],
            "Works Recommended": ["80604", " 43,28,68,68,194.09", " 4,328.69 Cr"],
            "Works Sanctioned": ["57602", " 30,15,32,90,862.82", " 3,015.33 Cr"],
            "Works Completed": ["15824", " 7,63,15,79,780.62", " 763.16 Cr"],
            ...
        }
        """
        if not isinstance(data, dict):
            return None

        # Extract values — tiles data uses specific key names
        entitled = None
        expended = None
        sanctioned = None
        works_recommended_count = 0
        works_sanctioned_count = 0
        works_completed_count = 0
        works_recommended_amt = None
        works_sanctioned_amt = None

        for key, values in data.items():
            if not isinstance(values, list):
                continue
            k = key.lower()

            if "allocated" in k or "limit" in k:
                # Allocated Limit = Entitled
                # Values: [raw_amount, "X Cr"]
                entitled = self._extract_crore_value(values)

            elif "expenditure" in k or "expended" in k:
                expended = self._extract_crore_value(values)

            elif "recommended" in k:
                if len(values) >= 1:
                    try:
                        works_recommended_count = int(re.sub(r"[^\d]", "", str(values[0])))
                    except (ValueError, TypeError):
                        pass
                works_recommended_amt = self._extract_crore_value(values)

            elif "sanctioned" in k:
                if len(values) >= 1:
                    try:
                        works_sanctioned_count = int(re.sub(r"[^\d]", "", str(values[0])))
                    except (ValueError, TypeError):
                        pass
                works_sanctioned_amt = self._extract_crore_value(values)

            elif "completed" in k:
                if len(values) >= 1:
                    try:
                        works_completed_count = int(re.sub(r"[^\d]", "", str(values[0])))
                    except (ValueError, TypeError):
                        pass

        # Map eSAKSHI fields to our model:
        # entitled = Allocated Limit
        # released = same as entitled (no separate "released" field)
        # sanctioned = Works Sanctioned amount
        # expended = Expenditure on works
        has_data = entitled is not None or expended is not None
        if not has_data:
            return None

        log.info(
            "eSAKSHI tiles parsed: entitled=%.2f Cr, expended=%s Cr, works=%d recommended / %d sanctioned / %d completed",
            entitled or 0, expended, works_recommended_count, works_sanctioned_count, works_completed_count,
        )

        return MPLADSFund(
            entitled=entitled,
            released=entitled,  # eSAKSHI doesn't distinguish entitled vs released
            sanctioned=works_sanctioned_amt,
            expended=expended,
            source="esakshi",
            confidence=0.9,
            works_count=works_recommended_count,
            sources=[DataSource(
                url=ESAKSHI_DASHBOARD_URL,
                source_name="esakshi",
                grade=EvidenceGrade.A,
                notes=(
                    f"Official eSAKSHI REST API — "
                    f"Works: {works_recommended_count} recommended, "
                    f"{works_sanctioned_count} sanctioned, "
                    f"{works_completed_count} completed"
                ),
            )],
            esakshi_coverage_start=ESAKSHI_COVERAGE_START,
        )

    def _extract_crore_value(self, values: list) -> Optional[float]:
        """Extract a crore value from a tiles data array like ['80604', '43,28,...', '4,328.69 Cr']."""
        # Prefer the Cr-labelled value (last element usually)
        for v in reversed(values):
            s = str(v).strip()
            if "cr" in s.lower():
                return _parse_amount(s)
        # Otherwise parse the raw amount and convert
        for v in values:
            s = str(v).strip()
            raw = _parse_amount(s)
            if raw is not None and raw > 1000:  # Likely raw rupees, not a count
                return round(raw / 1_00_00_000, 2)
        return None

    def _parse_report_data(self, data, mp: MPProfile) -> Optional[MPLADSFund]:
        """Parse getTilesReportData (per-MP table data)."""
        if not data:
            return None

        # The report data might be a list of MP records
        if isinstance(data, list):
            for record in data:
                if not isinstance(record, dict):
                    continue
                # Match by constituency or MP name
                for field in ["CONSTITUENCY", "Constituency", "constituency"]:
                    if field in record:
                        if name_matches(mp.constituency, str(record[field])):
                            return self._parse_report_record(record)
                for field in ["MP_NAME", "Hon'ble Member Of Parliament", "mp_name"]:
                    if field in record:
                        if name_matches(mp.name, str(record[field])):
                            return self._parse_report_record(record)

        # Single record dict
        if isinstance(data, dict) and not data.get("_error"):
            return self._parse_report_record(data)

        return None

    def _parse_report_record(self, record: dict) -> Optional[MPLADSFund]:
        """Parse a single MP record from the report data."""
        allocated = None
        for k in ["Allocated Amount ( ₹ )", "ALLOCATED_AMOUNT", "allocated", "Allocated Amount"]:
            if k in record:
                allocated = _parse_crore_amount(str(record[k]))
                break

        if allocated is None:
            return None

        return MPLADSFund(
            entitled=allocated,
            released=allocated,
            source="esakshi",
            confidence=0.85,
            sources=[DataSource(
                url=ESAKSHI_DASHBOARD_URL,
                source_name="esakshi",
                grade=EvidenceGrade.A,
                notes="From eSAKSHI report table data",
            )],
            esakshi_coverage_start=ESAKSHI_COVERAGE_START,
        )

    async def _extract_from_dom(self, page) -> Optional[MPLADSFund]:
        """Extract fund data from the rendered DOM of the eSAKSHI dashboard."""
        try:
            fund_data = await page.evaluate("""() => {
                const result = {};
                const allText = document.body.innerText || '';

                // Extract from eSAKSHI dashboard cards/tiles
                const labels = document.querySelectorAll('label, .z-label, span, h5');
                for (const el of labels) {
                    const text = (el.textContent || '').trim().toLowerCase();
                    const nextEl = el.nextElementSibling;
                    const value = nextEl ? nextEl.textContent.trim() : '';

                    if (text.includes('allocated') && text.includes('limit'))
                        result.entitled = value;
                    else if (text.includes('expenditure'))
                        result.expended = value;
                    else if (text.includes('works recommended'))
                        result.works_recommended = value;
                    else if (text.includes('works sanctioned'))
                        result.works_sanctioned = value;
                    else if (text.includes('works completed'))
                        result.works_completed = value;
                }

                // Regex extraction from full page text
                const patterns = {
                    entitled: /Allocated Limit[^\\d]*(\\d[\\d,\\.]+\\s*Cr)/i,
                    expended: /Expenditure[^\\d]*(\\d[\\d,\\.]+\\s*Cr)/i,
                    sanctioned: /Works Sanctioned[^\\d]*(\\d[\\d,\\.]+)[^\\d]*(\\d[\\d,\\.]+\\s*Cr)/i,
                    works_count: /Works Recommended[^\\d]*(\\d[\\d,]+)/i,
                };
                for (const [key, pat] of Object.entries(patterns)) {
                    if (!result[key]) {
                        const m = allText.match(pat);
                        if (m) result[key] = key === 'sanctioned' ? m[2] : m[1];
                    }
                }

                // Also grab table data if present
                const table = document.getElementById('tablepag');
                if (table && table.rows.length > 1) {
                    result.tableHeaders = Array.from(table.rows[0].cells).map(c => c.textContent.trim());
                    result.tableRowCount = table.rows.length - 1;
                }

                return result;
            }""")

            entitled = _parse_amount(fund_data.get("entitled"))
            expended = _parse_amount(fund_data.get("expended"))
            sanctioned = _parse_amount(fund_data.get("sanctioned"))

            works_count = 0
            wc = fund_data.get("works_count")
            if wc:
                try:
                    works_count = int(re.sub(r"[^\d]", "", str(wc)))
                except (ValueError, TypeError):
                    pass

            has_data = entitled is not None or expended is not None
            if not has_data:
                return None

            # Sanity check: reject national/state aggregates.
            # A single MP's entitlement is typically ~5 Cr/year, max ~25 Cr total.
            # Values above 100 Cr are almost certainly national/state totals.
            if entitled is not None and entitled > 100:
                log.warning(
                    "eSAKSHI DOM: Entitled=%.2f Cr looks like an aggregate — "
                    "rejecting (expected <25 Cr per constituency)",
                    entitled,
                )
                return None

            return MPLADSFund(
                entitled=entitled,
                released=entitled,
                sanctioned=sanctioned,
                expended=expended,
                source="esakshi",
                confidence=0.85,
                works_count=works_count,
                sources=[DataSource(
                    url=ESAKSHI_DASHBOARD_URL,
                    source_name="esakshi",
                    grade=EvidenceGrade.A,
                    notes="Extracted from eSAKSHI rendered DOM via Playwright",
                )],
                esakshi_coverage_start=ESAKSHI_COVERAGE_START,
            )

        except Exception as e:
            log.warning("eSAKSHI DOM extraction failed: %s", e)
            return None

    # ------------------------------------------------------------------
    # Strategy 2: REST API via aiohttp (fallback — usually 403)
    # ------------------------------------------------------------------

    async def _fetch_via_api(self, mp: MPProfile) -> Optional[MPLADSFund]:
        """Try fetching from eSAKSHI's underlying REST API directly."""
        state = normalize_state(mp.state)

        api_url = f"{self._api_base}/fund-status"
        params = {
            "constituency": mp.constituency,
            "state": state,
        }

        try:
            url = f"{api_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
            text = await self.scraper.fetch(url)
            data = json.loads(text)

            if isinstance(data, dict) and ("released" in data or "expended" in data):
                return self._parse_api_response(data)

            if isinstance(data, list):
                for item in data:
                    mp_name = item.get("mp_name", "") or item.get("member_name", "")
                    if name_matches(mp.name, mp_name):
                        return self._parse_api_response(item)

        except Exception:
            pass

        return None

    # ------------------------------------------------------------------
    # Strategy 3: HTML scraping (fallback)
    # ------------------------------------------------------------------

    async def _fetch_via_html(self, mp: MPProfile) -> Optional[MPLADSFund]:
        """Fallback: scrape eSAKSHI dashboard HTML for fund data."""
        try:
            url = f"{self._dashboard_url}/constituency/{mp.constituency.lower().replace(' ', '-')}"
            html = await self.scraper.fetch(url)
            if not html or len(html) < 100:
                return None
            return self._parse_dashboard_html(html, mp)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Works
    # ------------------------------------------------------------------

    async def _fetch_works_via_api(self, mp: MPProfile) -> list[MPLADSWork]:
        """Fetch work-level details from eSAKSHI API."""
        try:
            url = f"{self._api_base}/works?constituency={mp.constituency}&state={normalize_state(mp.state)}"
            text = await self.scraper.fetch(url)
            data = json.loads(text)

            works = []
            items = data if isinstance(data, list) else data.get("works", [])
            for item in items:
                work = MPLADSWork(
                    work_id=str(item.get("work_id", "") or item.get("id", "")),
                    description=item.get("description", "") or item.get("work_name", ""),
                    sector=_classify_sector(item.get("description", "") or item.get("work_name", "")),
                    recommended_amount=_parse_amount(str(item.get("recommended_amount", ""))),
                    sanctioned_amount=_parse_amount(str(item.get("sanctioned_amount", ""))),
                    expended_amount=_parse_amount(str(item.get("expended_amount", ""))),
                    status=item.get("status", ""),
                    district=item.get("district", ""),
                    completion_date=item.get("completion_date"),
                    source=DataSource(
                        url=self._dashboard_url,
                        source_name="esakshi",
                        grade=EvidenceGrade.A,
                        notes="Work detail from eSAKSHI portal",
                    ),
                )
                works.append(work)
            return works
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _parse_api_response(self, data: dict) -> MPLADSFund:
        """Parse eSAKSHI API JSON response into MPLADSFund."""
        entitled = _parse_amount(str(data.get("entitled", "") or data.get("total_entitled", "")))
        released = _parse_amount(str(data.get("released", "") or data.get("total_released", "")))
        sanctioned = _parse_amount(str(data.get("sanctioned", "") or data.get("total_sanctioned", "")))
        expended = _parse_amount(str(data.get("expended", "") or data.get("total_expended", "")))

        has_data = released is not None or expended is not None
        return MPLADSFund(
            entitled=entitled,
            released=released,
            sanctioned=sanctioned,
            expended=expended,
            source="esakshi",
            confidence=0.9 if has_data else 0.0,
            sources=[DataSource(
                url=self._dashboard_url,
                source_name="esakshi",
                grade=EvidenceGrade.A,
                notes="Official MoSPI eSAKSHI dashboard — Grade A authoritative source",
            )],
            esakshi_coverage_start=ESAKSHI_COVERAGE_START,
        )

    def _parse_dashboard_html(self, html: str, mp: MPProfile) -> Optional[MPLADSFund]:
        """Parse eSAKSHI dashboard HTML for fund utilization data."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return None

        soup = BeautifulSoup(html, "html.parser")

        entitled = None
        released = None
        sanctioned = None
        expended = None

        for row in soup.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True).lower()
                value = cells[-1].get_text(strip=True)

                if "entitled" in label or "entitlement" in label:
                    entitled = _parse_amount(value)
                elif "released" in label or "release" in label:
                    released = _parse_amount(value)
                elif "sanctioned" in label or "sanction" in label:
                    sanctioned = _parse_amount(value)
                elif "expended" in label or "expenditure" in label:
                    expended = _parse_amount(value)

        for elem in soup.find_all(attrs={"data-field": True}):
            field = elem.get("data-field", "").lower()
            value = elem.get_text(strip=True)
            if "entitled" in field:
                entitled = _parse_amount(value)
            elif "released" in field:
                released = _parse_amount(value)
            elif "sanctioned" in field:
                sanctioned = _parse_amount(value)
            elif "expended" in field:
                expended = _parse_amount(value)

        has_data = released is not None or expended is not None
        if not has_data:
            return None

        return MPLADSFund(
            entitled=entitled,
            released=released,
            sanctioned=sanctioned,
            expended=expended,
            source="esakshi",
            confidence=0.85 if has_data else 0.0,
            sources=[DataSource(
                url=self._dashboard_url,
                source_name="esakshi",
                grade=EvidenceGrade.A,
                notes="Parsed from eSAKSHI dashboard HTML",
            )],
            esakshi_coverage_start=ESAKSHI_COVERAGE_START,
        )
