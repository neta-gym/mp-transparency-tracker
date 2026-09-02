#!/usr/bin/env python3
"""Full 8-dimension rescore: state-by-state --update run, resumable.

Loops over all states, runs scripts/run.py --state <s> --update for each,
records completion in data/_meta/full_rescore_progress.json so a relaunch
skips finished states. GLM key is optional (keyword fallback in glm.py).

Usage: PYTHONPATH=src nohup python scripts/full_rescore.py [--states a,b] &
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROGRESS = ROOT / "data" / "_meta" / "full_rescore_progress.json"

ALL_STATES = [
    "andhra-pradesh", "arunachal-pradesh", "assam", "bihar", "chhattisgarh", "delhi", "goa",
    "gujarat", "haryana", "himachal-pradesh", "jammu-and-kashmir", "jharkhand", "karnataka",
    "kerala", "madhya-pradesh", "maharashtra", "manipur", "meghalaya", "mizoram", "nagaland",
    "odisha", "punjab", "rajasthan", "sikkim", "tamil-nadu", "telangana", "tripura",
    "uttar-pradesh", "uttarakhand", "west-bengal",
    "andaman-and-nicobar-islands", "chandigarh", "dadra-and-nagar-haveli-and-daman-and-diu",
    "ladakh", "lakshadweep", "puducherry",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--states", help="comma-separated override")
    args = ap.parse_args()
    states = args.states.split(",") if args.states else ALL_STATES

    progress = json.loads(PROGRESS.read_text()) if PROGRESS.exists() else {"done": [], "failed": {}}
    started = time.time()
    for state in states:
        if state in progress["done"]:
            print(f"skip {state} (done)", flush=True)
            continue
        print(f"[{datetime.now(timezone.utc).isoformat()}] state {state} starting", flush=True)
        t0 = time.time()
        r = subprocess.run(
            [sys.executable, "scripts/run.py", "--state", state, "--update"],
            cwd=ROOT, capture_output=True, text=True, timeout=7200,
            env={"PYTHONPATH": "src", "PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": "/home/sandbox"},
        )
        ok = r.returncode == 0
        print(f"state {state}: rc={r.returncode} in {time.time()-t0:.0f}s", flush=True)
        if not ok:
            progress["failed"][state] = (r.stderr or r.stdout)[-2000:]
        else:
            progress["done"].append(state)
            progress["failed"].pop(state, None)
        PROGRESS.write_text(json.dumps(progress, indent=1) + "\n")
    print(f"ALL DONE in {(time.time()-started)/3600:.1f}h; failed: {list(progress['failed'])}", flush=True)
    return 0 if not progress["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
