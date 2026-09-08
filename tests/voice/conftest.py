"""Fixture dataset for voice tests: two states, four MPs, realistic shape."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def _mp(name, slug, state, constituency, party, house="lok_sabha",
        attendance=88.0, questions=12, debates=5, cases=0, serious=0,
        assets=2.5e7, entitled=10.0, expended=7.5, util=75.0):
    return {
        "mp": {"name": name, "canonical_name": name, "slug": slug,
               "state": state, "constituency": constituency, "party": party,
               "house": house, "photo_url": f"/mp-photos/{slug}.jpg",
               "name_aliases": []},
        "parliament_activity": {"attendance_percentage": attendance,
                                "questions_asked": questions,
                                "debates_participated": debates},
        "criminal_record": {"total_cases": cases, "serious_cases": serious},
        "assets": {"total_assets": assets},
        "mplads": {"entitled": entitled, "expended": expended,
                   "utilization_rate": util},
        "sources_consulted": ["sansad.in", "myneta.info"],
    }


def _score(name, slug, state, score):
    return {"mp": {"name": name, "slug": slug, "state": state},
            "composite_score": score, "data_confidence": 0.8}


MPS = [
    ("test-pradesh", _mp("Asha Verma", "asha-verma", "test-pradesh",
                         "Rampur", "Test Party A"),
     _score("Asha Verma", "asha-verma", "test-pradesh", 81.5)),
    ("test-pradesh", _mp("Bhuvan Singh", "bhuvan-singh", "test-pradesh",
                         "Sitapur", "Test Party B", attendance=41.0,
                         questions=2, cases=3, serious=1, assets=8.2e7,
                         expended=2.0, util=20.0),
     _score("Bhuvan Singh", "bhuvan-singh", "test-pradesh", 33.0)),
    ("other-state", _mp("Chitra Rao", "chitra-rao", "other-state",
                        "Coastal City", "Test Party A", house="rajya_sabha",
                        attendance=None, questions=None),
     _score("Chitra Rao", "chitra-rao", "other-state", 62.0)),
    ("other-state", _mp("Dev Patel", "dev-patel", "other-state",
                        "Hill Town", "Test Party C"),
     _score("Dev Patel", "dev-patel", "other-state", 70.0)),
]


@pytest.fixture()
def data_dir(tmp_path: Path) -> Path:
    entries = []
    for i, (state, raw, score) in enumerate(MPS):
        (tmp_path / state / "raw").mkdir(parents=True, exist_ok=True)
        (tmp_path / state / "scores").mkdir(parents=True, exist_ok=True)
        slug = raw["mp"]["slug"]
        (tmp_path / state / "raw" / f"{slug}.json").write_text(json.dumps(raw))
        (tmp_path / state / "scores" / f"{slug}.json").write_text(json.dumps(score))
        entries.append({"rank": i + 1, "mp_name": raw["mp"]["name"],
                        "constituency": raw["mp"]["constituency"],
                        "party": raw["mp"]["party"], "state": state,
                        "composite_score": score["composite_score"]})
    (tmp_path / "national" / "leaderboard").mkdir(parents=True)
    (tmp_path / "national" / "leaderboard" / "latest.json").write_text(json.dumps(
        {"generated_at": "2026-09-08T00:00:00Z", "methodology_version": "3.2",
         "total_mps": len(MPS), "states_included": ["test-pradesh", "other-state"],
         "top_n": len(MPS), "entries": entries}))
    return tmp_path


@pytest.fixture()
def index(data_dir):
    from voice.data_index import MPDataIndex
    return MPDataIndex(data_dir)
