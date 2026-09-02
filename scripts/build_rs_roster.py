#!/usr/bin/env python3
"""Build the Rajya Sabha roster from the official Digital Sansad RS API.

Fetches all sitting RS members (https://sansad.in/api_rs/member/sitting-members),
normalizes names/states to repo conventions, and writes data/_meta/rs_roster.json.

Usage: PYTHONPATH=src python scripts/build_rs_roster.py
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

SANSAD_RS_API = "https://sansad.in/api_rs/member/sitting-members?mpFlag=1&page=1&size=300"

# Digital Sansad state caption -> repo state slug
STATE_MAP = {
    "keralam": "kerala",  # Sansad uses the 2023 official name
    "jammu & kashmir": "jammu-and-kashmir",
    "jammu and kashmir": "jammu-and-kashmir",
    "national capital territory of delhi": "delhi",
    "odisha": "odisha",
    "puducherry": "puducherry",
    "nominated": "nominated",  # 12 nominated members have no state
}


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def state_slug(caption: str) -> str:
    key = caption.strip().lower()
    return STATE_MAP.get(key, slugify(key))


def clean_name(raw: str) -> str:
    """'Abdul Wahab, Shri ' -> 'Shri Abdul Wahab' -> strip honorific."""
    name = raw.strip()
    m = re.match(r"^(.*?),\s*((?:Shri|Smt|Dr|Prof|Kumari|Ms|Mr)\.?)\s+(.*)$", name, re.I)
    if m:
        name = f"{m.group(2)} {m.group(3)} {m.group(1)}"
    else:
        m = re.match(r"^(.*?),\s*(Shri|Smt|Dr|Prof|Kumari|Ms|Mr)\.?$", name, re.I)
        if m:
            name = f"{m.group(2)} {m.group(1)}"
    # drop honorific for the canonical display name (matches LS convention)
    name = re.sub(r"^(Shri|Smt|Dr|Prof|Kumari|Ms|Mr)\.?\s+", "", name, flags=re.I).strip()
    name = re.sub(r"\s+", " ", name)
    return name


def main() -> int:
    req = urllib.request.Request(
        SANSAD_RS_API,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh) Chrome/126.0",
            "Referer": "https://sansad.in/rs/members",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.load(resp)
    records = payload.get("records", [])
    if len(records) < 200:
        print(f"unexpectedly small roster: {len(records)}", file=sys.stderr)
        return 1

    roster = []
    seen_slugs: dict[str, int] = {}
    for r in records:
        name = clean_name(r.get("name", ""))
        state = r.get("state", "").strip()
        slug = state_slug(state)
        base = slugify(name)
        mp_slug = base
        # disambiguate duplicate names within the roster
        key = f"{slug}/{base}"
        if key in seen_slugs:
            seen_slugs[key] += 1
            mp_slug = f"{base}-{seen_slugs[key]}"
        else:
            seen_slugs[key] = 1
        roster.append(
            {
                "name": name,
                "slug": mp_slug,
                "sansad_rs_mpsno": r.get("mpsno"),
                "party": (r.get("party") or "").strip(),
                "party_code": (r.get("partyCode") or "").strip(),
                "state_caption": state,
                "state_slug": slug,
                "house": "rajya_sabha",
                "term": (r.get("term") or "").strip(),
                "term_count": r.get("termCount"),
                "is_minister": bool(r.get("currentMinister")),
                "email": (r.get("emailID") or "").replace("[dot]", ".").replace("[at]", "@"),
                "phone_local": (r.get("localTele") or "").strip() or None,
                "address_delhi": (r.get("localAdd") or "").strip() or None,
                "address_permanent": (r.get("permanentAdd") or "").strip() or None,
                "photo_url": (r.get("imageUrl") or "").strip() or None,
                "age": r.get("age"),
                "gender": (r.get("gender") or "").strip() or None,
            }
        )

    out = DATA / "_meta" / "rs_roster.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"count": len(roster), "members": roster}, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {out} with {len(roster)} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
