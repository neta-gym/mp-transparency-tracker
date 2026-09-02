#!/usr/bin/env python3
"""Backfill MPLADS works for Rajya Sabha members from eSAKSHI.

RS members have no Lok Sabha constituency; eSAKSHI keys them by
(state_id, const=0, mp_id, house=1, tenure=1). Output:
data/_meta/rs_works.json keyed by roster slug. Resumable.

Usage: PYTHONPATH=src python scripts/backfill_rs_works.py [--state bihar] [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import difflib
import json
import logging
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tracker.tools.esakshi_works import ESAKSHIWorksClient, ResolvedMP  # noqa: E402
from tracker.utils.name_match import name_matches  # noqa: E402

log = logging.getLogger("backfill_rs_works")
DATA = Path(__file__).resolve().parent.parent / "data"
OUT = DATA / "_meta" / "rs_works.json"

RS_HOUSE = 1
RS_TENURE_SITTING = 1

TERM_RE = re.compile(r"\s*\(\d{4}-\d{2,4}\)\s*$")
HON_RE = re.compile(r"^(Shri|Smt|Dr|Prof|Kumari|Ms|Mr)\.?\s+", re.I)


def clean_caption(caption: str) -> str:
    name = TERM_RE.sub("", caption).strip()
    return HON_RE.sub("", name).strip()


def match_roster(caption_name: str, members: list[dict]) -> dict | None:
    exact = [m for m in members if name_matches(m["name"], caption_name)]
    if len(exact) == 1:
        return exact[0]
    names = {re.sub(r"[^a-z0-9]", "", m["name"].lower()): m for m in members}
    key = re.sub(r"[^a-z0-9]", "", caption_name.lower())
    if key in names:
        return names[key]
    close = difflib.get_close_matches(key, list(names), n=1, cutoff=0.85)
    if close:
        return names[close[0]]
    return None


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", help="only this state slug")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    roster = json.loads((DATA / "_meta" / "rs_roster.json").read_text())["members"]
    by_state: dict[str, list[dict]] = {}
    for m in roster:
        by_state.setdefault(m["state_slug"], []).append(m)

    results: dict[str, dict] = json.loads(OUT.read_text()) if OUT.exists() else {}
    started = time.time()
    totals = {"mps": 0, "works": 0, "skipped": [], "errors": []}

    async with ESAKSHIWorksClient(request_delay=0.3) as client:
        for state_slug in sorted(by_state):
            if args.state and state_slug != args.state:
                continue
            if state_slug == "nominated":
                totals["skipped"].append("nominated: no state MPLADS context on eSAKSHI")
                continue
            members = by_state[state_slug]
            if all(m["slug"] in results and "works" in results[m["slug"]] for m in members):
                log.info("%s: already done", state_slug)
                continue
            state_id = await client.resolve_state_id(state_slug.replace("-", " "))
            if state_id is None:
                totals["errors"].append(f"{state_slug}: state id not found")
                continue
            try:
                esakshi_mps = await asyncio.wait_for(
                    client._post("getMpNamesData", {"state_combo": f"{state_id},{RS_HOUSE},{RS_TENURE_SITTING}"}),
                    timeout=120,
                )
            except Exception as e:  # noqa: BLE001
                totals["errors"].append(f"{state_slug}: mp list failed: {e}")
                continue
            if not isinstance(esakshi_mps, list):
                totals["errors"].append(f"{state_slug}: bad mp list")
                continue
            log.info("%s: %d roster, %d on eSAKSHI", state_slug, len(members), len(esakshi_mps))

            nominated = by_state.get("nominated", [])
            # verified caption aliases (name changes / portal variants)
            CAPTION_ALIAS = {"Alka Singh": "Alka Gurjar"}
            for rec in esakshi_mps:
                caption = rec.get("CAPTION", "")
                cname = clean_caption(caption)
                cname = CAPTION_ALIAS.get(cname, cname)
                roster_mp = match_roster(cname, members)
                if roster_mp is None and nominated:
                    # nominated RS members execute MPLADS in a chosen state; eSAKSHI
                    # files them under that state instead of "Nominated"
                    roster_mp = match_roster(cname, nominated)
                if roster_mp is None:
                    totals["skipped"].append(f"{state_slug}: '{cname}' not in roster")
                    continue
                slug = roster_mp["slug"]
                if slug in results and "works" in results[slug]:
                    continue
                resolved = ResolvedMP(
                    state_id=state_id,
                    constituency_id=0,
                    mp_id=int(rec["ID"]),
                    house=RS_HOUSE,
                    tenure_id=RS_TENURE_SITTING,
                    mp_caption=caption,
                )
                try:
                    works = await asyncio.wait_for(client.fetch_works(resolved), timeout=240)
                except asyncio.CancelledError:
                    totals["errors"].append(f"{state_slug}/{cname}: timed out")
                    continue
                except Exception as e:  # noqa: BLE001
                    totals["errors"].append(f"{state_slug}/{cname}: {e}")
                    continue
                results[slug] = {
                    "name": roster_mp["name"],
                    "esakshi_caption": caption,
                    "works": [w.model_dump(mode="json") for w in works],
                    "works_count": len(works),
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                }
                totals["mps"] += 1
                totals["works"] += len(works)
                if totals["mps"] % 10 == 0:
                    OUT.write_text(json.dumps(results, indent=1, ensure_ascii=False))
                    log.info("checkpoint: %d MPs, %d works", totals["mps"], totals["works"])
            OUT.write_text(json.dumps(results, indent=1, ensure_ascii=False) + "\n")

    OUT.write_text(json.dumps(results, indent=1, ensure_ascii=False) + "\n")
    report = {
        "started_at": datetime.fromtimestamp(started, timezone.utc).isoformat(),
        "elapsed_seconds": round(time.time() - started, 1),
        **totals,
        "mps_with_works": sum(1 for r in results.values() if r.get("works_count", 0) > 0),
        "mps_total_fetched": len(results),
    }
    (DATA / "_meta" / "rs_works_backfill_report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    log.info("DONE: %s", json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in report.items()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
