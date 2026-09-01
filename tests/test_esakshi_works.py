"""Tests for the eSAKSHI work-level client (hermetic; no network)."""

from __future__ import annotations

import pytest

from tracker.models.schemas import DataSource, EvidenceGrade
from tracker.tools.esakshi_works import (
    ESAKSHIWorksClient,
    ResolvedMP,
    map_work_status,
    merge_work_lifecycle,
)

SRC = DataSource(
    url="https://mplads.mospi.gov.in/digigov/dashboard.html",
    source_name="esakshi",
    grade=EvidenceGrade.A,
)

RECOMMENDED = [
    {
        "WORK_RECOMMENDATION_DTL_ID": 268560,
        "WORK_DESCRIPTION": "Establishment of Open Gym at High School, Village Rasalpura",
        "RECOMMENDATION_DATE": "15-Feb-2026",
        "RECOMMENDED_AMOUNT": 925000.00,
        "SANCTION_AMOUNT": 925000.00,
        "WORK_STAGE": "Pending for Sanction",
        "LETTER_NO": "LN/MP419/2025-2026/31",
        "IDA_NAME": "SARAN(DISTRICT PLANNING OFFICE SARAN CHAPRA_IDA)",
        "CONSTITUENCY": "SARAN",
        "FLAG": 1,
    }
]

SANCTIONED = [
    {
        "WORK_RECOMMENDATION_DTL_ID": 268560,
        "SANCTION_AMOUNT": 900000.00,
        "SANCTION_DATE": "01-Mar-2026",
        "WORK_STAGE": "Work In Progress",
        "FLAG": 2,
    }
]

COMPLETED = [
    {
        "WORK_RECOMMENDATION_DTL_ID": 1216,
        "WORK_ID": 626,
        "WORK_DESCRIPTION": "P.C.C road in village",
        "ACTUAL_AMOUNT": 1486089.0,
        "ACTUAL_END_DATE": "23-Sep-2023",
        "AVERAGE_RATING": 4.2,
        "FLAG": 3,
        "CONSTITUENCY": "PATNA",
    }
]


def test_map_work_status():
    assert map_work_status("Pending for Sanction", 1) == "recommended"
    assert map_work_status("Work In Progress", 2) == "in_progress"
    assert map_work_status("Work Completed", 3) == "completed"
    assert map_work_status(None, 1) == "recommended"
    assert map_work_status(None, 3) == "completed"
    assert map_work_status(None, None) == "unknown"
    assert map_work_status("Some New Stage", 2) == "in_progress"


def test_merge_full_lifecycle():
    works = merge_work_lifecycle(RECOMMENDED, SANCTIONED, [], SRC)
    assert len(works) == 1
    w = works[0]
    assert w.work_id == "268560"
    assert w.sector == "education"  # "school" wins over "gym" in keyword order
    assert w.recommended_amount == pytest.approx(925000.0)
    assert w.sanctioned_amount == pytest.approx(900000.0)
    assert w.recommendation_date == "15-Feb-2026"
    assert w.sanction_date == "01-Mar-2026"
    assert w.status == "in_progress"
    assert w.executing_agency and "SARAN" in w.executing_agency
    assert w.letter_no == "LN/MP419/2025-2026/31"


def test_merge_completed_work():
    works = merge_work_lifecycle([], [], COMPLETED, SRC)
    assert len(works) == 1
    w = works[0]
    assert w.status == "completed"
    assert w.expended_amount == pytest.approx(1486089.0)
    assert w.completion_date == "23-Sep-2023"
    assert w.average_rating == pytest.approx(4.2)
    assert w.sector == "infrastructure"


def test_merge_joins_across_reports():
    works = merge_work_lifecycle(RECOMMENDED, SANCTIONED, COMPLETED, SRC)
    assert len(works) == 2  # 268560 joined; 1216 completed-only
    by_id = {w.work_id: w for w in works}
    assert by_id["268560"].status == "in_progress"
    assert by_id["1216"].status == "completed"


def test_merge_empty():
    assert merge_work_lifecycle([], [], [], SRC) == []


def test_zero_rating_treated_as_unrated():
    rec = dict(COMPLETED[0], AVERAGE_RATING=0.0)
    works = merge_work_lifecycle([], [], [rec], SRC)
    assert works[0].average_rating is None


class _FakeClient(ESAKSHIWorksClient):
    def __init__(self, responses):
        self.responses = responses
        self.request_delay = 0
        self.max_retries = 1
        self._session = None
        self._state_cache = {}
        self._const_cache = {}
        self._tenure_cache = {}

    async def _post(self, endpoint, payload):  # noqa: ANN001
        return self.responses[endpoint]


@pytest.mark.asyncio
async def test_resolution_chain_caches():
    client = _FakeClient(
        {
            "getStateData": [{"STATE_NAME": "Bihar", "STATE_ID": 6}],
            "getTenureData": [{"ID": 7, "CAPTION": "18th Lok Sabha"}],
            "getConstituencyData": [{"ID": 75, "CAPTION": "SARAN"}],
            "getMpAndConstCombo": [{"ID": 3018356, "CAPTION": "Rajiv Pratap Rudy"}],
        }
    )
    assert await client.resolve_state_id("bihar") == 6
    assert await client.resolve_tenure_id(2, "18th Lok Sabha") == 7
    assert await client.resolve_constituency_id(6, "Saran") == 75
    mp = await client.resolve_mp(6, 75, 2, 7)
    assert mp is not None and mp.mp_id == 3018356
    # cache hit: second call works even with responses emptied
    client.responses.clear()
    assert await client.resolve_state_id("bihar") == 6


@pytest.mark.asyncio
async def test_fetch_works_end_to_end():
    import json as _json

    client = _FakeClient(
        {
            "getTilesReportData": {
                "Total Works Recommended": _json.dumps(RECOMMENDED),
            }
        }
    )

    # vary response per key
    async def _post(endpoint, payload):
        key = payload["key"]
        body = {
            "Works Recommended": RECOMMENDED,
            "Works Sanctioned": SANCTIONED,
            "Works Completed": COMPLETED,
        }[key]
        return {f"Total {key}": _json.dumps(body)}

    client._post = _post  # type: ignore[method-assign]
    mp = ResolvedMP(state_id=6, constituency_id=75, mp_id=3018356, house=2, tenure_id=7)
    works = await client.fetch_works(mp, SRC)
    assert len(works) == 2
    by_id = {w.work_id: w for w in works}
    assert by_id["268560"].sanction_date == "01-Mar-2026"
    assert by_id["1216"].average_rating == pytest.approx(4.2)


@pytest.mark.asyncio
async def test_report_handles_aggregate_only():
    client = _FakeClient({"getTilesReportData": {"Total Works Recommended": '[{"Total_Amt":0.0}]'}})
    rows = await client._report("6,75,0,2,7", "Works Recommended")
    assert rows == []


@pytest.mark.asyncio
async def test_fuzzy_constituency_resolution_with_reservation_tag():
    client = _FakeClient(
        {"getConstituencyData": [{"ID": 90, "CAPTION": "TIRUPATI (SC)"}, {"ID": 91, "CAPTION": "NELLORE"}]}
    )
    assert await client.resolve_constituency_id(2, "Tirupati") == 90
    # exact match wins over fuzzy
    client2 = _FakeClient({"getConstituencyData": [{"ID": 1, "CAPTION": "ARIYALUR"}, {"ID": 2, "CAPTION": "ARI"}]})
    assert await client2.resolve_constituency_id(4, "Ari") == 2
    # ambiguous prefix -> None
    client3 = _FakeClient({"getConstituencyData": [{"ID": 1, "CAPTION": "ARIYALUR"}, {"ID": 2, "CAPTION": "ARANI"}]})
    assert await client3.resolve_constituency_id(4, "Ar") is None


@pytest.mark.asyncio
async def test_fuzzy_state_resolution_union_territory():
    client = _FakeClient(
        {
            "getStateData": [
                {"STATE_NAME": "Dadra and Nagar Haveli", "STATE_ID": 9},
                {"STATE_NAME": "Bihar", "STATE_ID": 6},
            ]
        }
    )
    assert await client.resolve_state_id("dadra and nagar haveli and daman and diu") == 9
    assert await client.resolve_state_id("nonexistent-place") is None
