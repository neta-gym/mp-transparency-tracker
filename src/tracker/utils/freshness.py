"""Data freshness report — shows how stale each source is per MP."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from ..models.schemas import ResearchFindings
from ..utils.logger import get_logger

log = get_logger(__name__)


def freshness_report(state: str, data_dir: str) -> list[dict]:
    """Scan cached JSON files for a state and report freshness per MP.

    Returns a list of dicts sorted by stalest data first:
        [{mp_name, source, fetched_at, age_days, grade}, ...]
    """
    state_slug = state.replace(" ", "-").lower()
    raw_dir = os.path.join(data_dir, state_slug, "raw")

    if not os.path.isdir(raw_dir):
        return []

    now = datetime.now(timezone.utc)
    rows = []

    for filename in sorted(os.listdir(raw_dir)):
        if not filename.endswith(".json") or "_validated" in filename:
            continue

        filepath = os.path.join(raw_dir, filename)
        try:
            with open(filepath) as f:
                findings = ResearchFindings.model_validate_json(f.read())
        except Exception as e:
            log.warning("Failed to parse %s: %s", filename, e)
            continue

        mp_name = findings.mp.name
        collected_at = findings.collected_at

        # Overall collection date
        if collected_at:
            age = (now - collected_at.replace(tzinfo=timezone.utc) if collected_at.tzinfo is None else now - collected_at)
            age_days = age.days
        else:
            age_days = -1

        # Per-source freshness from evidence summary
        for dim, grade in findings.evidence_summary.items():
            rows.append({
                "mp_name": mp_name,
                "source": dim,
                "fetched_at": collected_at.isoformat() if collected_at else "unknown",
                "age_days": age_days,
                "grade": grade,
            })

        # If no evidence summary, add a single row
        if not findings.evidence_summary:
            rows.append({
                "mp_name": mp_name,
                "source": "all",
                "fetched_at": collected_at.isoformat() if collected_at else "unknown",
                "age_days": age_days,
                "grade": "E",
            })

    # Sort by stalest first
    rows.sort(key=lambda r: -r["age_days"])
    return rows
