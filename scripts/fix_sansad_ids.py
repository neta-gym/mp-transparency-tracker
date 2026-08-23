#!/usr/bin/env python3
"""Repair stale sansad_member_id values in cached MP records.

Cross-checks every cached Lok Sabha record against the official Digital
Sansad member list (same API as src/tracker/tools/sansad.py). When the
stored member ID belongs to a different MP (name/constituency disagree),
the record is corrected to the sitting member that actually matches the
record's name and constituency.

Rule-based and source-backed: every correction is derived from the live
official member list, never guessed. Run before scripts/rescore_offline.py
so regenerated leaderboards pick up the fixed identities.
"""

import glob
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tracker.config import settings
from tracker.utils.name_match import normalize_name

LS_API = settings.urls.sansad_ls_api


def fetch_official_members() -> dict[int, dict]:
    req = urllib.request.Request(LS_API, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    members = data if isinstance(data, list) else data.get("membersDtoList", [])
    return {
        int(m["mpsno"]): m
        for m in members
        if m.get("mpsno")
        and str(m.get("status", "")).strip().lower() == "sitting"
        and str(m.get("lastLoksabha", "")).strip() == "18"
    }


def official_name(member: dict) -> str:
    first = member.get("firstName", "")
    last = member.get("lastName", "")
    return f"{first} {last}".strip()


def tokens(name: str) -> set[str]:
    return set(normalize_name(name).split())


def constituency_of(member: dict) -> str:
    return normalize_name(str(member.get("constName", "") or ""))


def consts_agree(ours: str, official: str) -> bool:
    if not ours or not official:
        return True
    return ours == official or ours in official or official in ours


def find_correct_member(mp_name: str, constituency: str, members: dict[int, dict]) -> int | None:
    """Exact-name match with agreeing constituency, else unique name-token match."""
    name_toks = tokens(mp_name)
    const_norm = normalize_name(constituency)

    exact = []
    for mid, m in members.items():
        if normalize_name(official_name(m)) == normalize_name(mp_name) and consts_agree(
            const_norm, constituency_of(m)
        ):
            exact.append(mid)
    if len(exact) == 1:
        return exact[0]

    # Same surname + full token overlap fallback (unique only)
    fallback = []
    for mid, m in members.items():
        off_toks = tokens(official_name(m))
        if off_toks == name_toks and consts_agree(const_norm, constituency_of(m)):
            fallback.append(mid)
    if len(fallback) == 1:
        return fallback[0]
    return None


def repair_file(path: str, members: dict[int, dict]) -> str | None:
    """Repair sansad_member_id in one findings JSON. Returns a description or None."""
    with open(path) as f:
        payload = json.load(f)

    mp = payload["mp"]
    if mp.get("house") not in (None, "", "lok_sabha"):
        return None

    sid = mp.get("sansad_member_id")
    official = members.get(sid) if sid else None

    if official is not None:
        if tokens(official_name(official)) & tokens(mp["name"]) and consts_agree(
            normalize_name(mp.get("constituency", "")), constituency_of(official)
        ):
            return None  # stored ID is consistent

    correct = find_correct_member(mp["name"], mp.get("constituency", ""), members)
    if correct is None or correct == sid:
        print(f"  !! could not resolve {mp['name']} ({mp.get('constituency')}) currently id={sid}")
        return None

    wrong_name = official_name(members[sid]) if sid in members else "unknown"
    right = members[correct]
    print(
        f"  fix {mp['name']} ({mp.get('constituency')}): "
        f"{sid} [{wrong_name}] -> {correct} [{official_name(right)}]"
    )
    mp["sansad_member_id"] = correct
    if right.get("photoUrl") and not mp.get("profile_url"):
        pass  # profile_url stays as-is; photo resolution handles images
    with open(path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return mp["slug"]


def main() -> None:
    print("Fetching official Lok Sabha member list...")
    members = fetch_official_members()
    print(f"  {len(members)} sitting 18th Lok Sabha members")

    fixed = 0
    checked = 0
    for path in sorted(glob.glob(os.path.join(settings.data_dir, "*", "raw", "*.json"))):
        if os.path.basename(path).endswith("_validated.json"):
            continue
        checked += 1
        if repair_file(path, members):
            fixed += 1

    print(f"\nChecked {checked} records; corrected {fixed} mismatched sansad_member_id(s)")


if __name__ == "__main__":
    main()
