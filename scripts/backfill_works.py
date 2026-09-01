#!/usr/bin/env python3
"""Backfill transaction-level MPLADS works into validated findings JSONs.

For every MP in data/<state>/leaderboard/latest.json, resolves the MP on the
official eSAKSHI portal (mplads.mospi.gov.in), pulls the Works
Recommended/Sanctioned/Completed reports, merges them into per-work lifecycle
records, and patches data/<state>/raw/<mp_slug>_validated.json in place
(findings.mplads.works / works_count / source note).

Usage:
    PYTHONPATH=src python scripts/backfill_works.py [--state bihar] [--limit N]
        [--delay 0.25] [--dry-run]

Writes a run summary to data/_meta/works_backfill_report.json.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tracker.models.schemas import DataSource, EvidenceGrade  # noqa: E402
from tracker.tools.esakshi_works import (  # noqa: E402
    HOUSE_LOK_SABHA,
    ESAKSHIWorksClient,
)

log = logging.getLogger("backfill_works")
DATA = Path(__file__).resolve().parent.parent / "data"

# 18th Lok Sabha tenure id on eSAKSHI (17th = 5, 18th = 7; RS Sitting = 1)
CURRENT_LS_TENURE_CAPTION = "18th Lok Sabha"


def state_dirs() -> list[Path]:
    return sorted(
        p
        for p in DATA.iterdir()
        if p.is_dir() and p.name != "national" and (p / "leaderboard" / "latest.json").exists()
    )


def _leaderboard_entries(state_dir: Path) -> list[dict]:
    doc = json.loads((state_dir / "leaderboard" / "latest.json").read_text())
    return doc.get("entries", [])


def _validated_path(state_dir: Path, mp_name: str) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "-", mp_name.lower()).strip("-")
    return state_dir / "raw" / f"{slug}_validated.json"


async def backfill_state(
    client: ESAKSHIWorksClient,
    state_dir: Path,
    limit: int | None,
    dry_run: bool,
    force: bool = False,
) -> dict:
    state = state_dir.name
    entries = _leaderboard_entries(state_dir)
    stats = {"state": state, "mps": 0, "works": 0, "skipped": [], "errors": []}

    state_id = await client.resolve_state_id(state.replace("-", " "))
    if state_id is None:
        stats["errors"].append(f"state id not found for {state}")
        return stats
    tenure_id = await client.resolve_tenure_id(HOUSE_LOK_SABHA, CURRENT_LS_TENURE_CAPTION)
    if tenure_id is None:
        stats["errors"].append("18th Lok Sabha tenure id not found")
        return stats

    for entry in entries[: limit or None]:
        name = entry.get("mp_name", "")
        constituency = entry.get("constituency", "")
        path = _validated_path(state_dir, name)
        if not path.exists():
            stats["skipped"].append(f"{name}: no validated json")
            continue
        if not force and "Work-level backfill" in path.read_text():
            stats["skipped"].append(f"{name}: already backfilled")
            continue
        try:
            const_id = await asyncio.wait_for(client.resolve_constituency_id(state_id, constituency), timeout=180)
            if const_id is None:
                stats["skipped"].append(f"{name}: constituency '{constituency}' unresolved")
                continue
            resolved = await asyncio.wait_for(
                client.resolve_mp(state_id, const_id, HOUSE_LOK_SABHA, tenure_id), timeout=180
            )
            if resolved is None:
                stats["skipped"].append(f"{name}: mp unresolved on eSAKSHI")
                continue
            works = await asyncio.wait_for(client.fetch_works(resolved), timeout=240)
        except Exception as e:  # noqa: BLE001 - record and continue
            stats["errors"].append(f"{name}: {e}")
            log.warning("%s/%s failed: %s", state, name, e)
            continue

        stats["mps"] += 1
        stats["works"] += len(works)
        if dry_run:
            log.info("[dry-run] %s/%s: %d works", state, name, len(works))
            continue

        doc = json.loads(path.read_text())
        mplads = doc.setdefault("findings", {}).setdefault("mplads", {})
        mplads["works"] = [w.model_dump(mode="json") for w in works]
        mplads["works_count"] = len(works)
        sources = mplads.setdefault("sources", [])
        sources.append(
            DataSource(
                url="https://mplads.mospi.gov.in/digigov/dashboard.html",
                source_name="esakshi",
                grade=EvidenceGrade.A,
                fetched_at=datetime.now(timezone.utc).isoformat(),
                notes=f"Work-level backfill: {len(works)} works (recommended/sanctioned/completed lifecycle)",
            ).model_dump(mode="json")
        )
        path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")

    return stats


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", help="only this state slug")
    ap.add_argument("--limit", type=int, default=None, help="max MPs per state")
    ap.add_argument("--delay", type=float, default=0.25, help="seconds between requests")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="redo MPs already backfilled")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    dirs = state_dirs()
    if args.state:
        dirs = [d for d in dirs if d.name == args.state]
        if not dirs:
            log.error("state not found: %s", args.state)
            return 2

    started = time.time()
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "states": []}
    async with ESAKSHIWorksClient(request_delay=args.delay) as client:
        for state_dir in dirs:
            log.info("state: %s", state_dir.name)
            stats = await backfill_state(client, state_dir, args.limit, args.dry_run, args.force)
            report["states"].append(stats)
            log.info(
                "%s done: %d MPs, %d works, %d skipped, %d errors",
                state_dir.name,
                stats["mps"],
                stats["works"],
                len(stats["skipped"]),
                len(stats["errors"]),
            )

    report["elapsed_seconds"] = round(time.time() - started, 1)
    meta = DATA / "_meta"
    meta.mkdir(exist_ok=True)
    out = meta / "works_backfill_report.json"
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    log.info("report written: %s", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
