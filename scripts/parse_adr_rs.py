#!/usr/bin/env python3
"""Parse ADR's 'Analysis of Sitting Rajya Sabha MPs' PDF into per-MP records.

Extracts:
- asset appendix (movable, immovable, total=mov+imm, age, party) - all analysed MPs
- criminal appendix (total cases, serious IPC+BNS, pending count, convicted count)

Matches ADR names to data/_meta/rs_roster.json (state-verified fuzzy).
Output: data/_meta/rs_adr.json keyed by roster slug.

Usage: PYTHONPATH=src python scripts/parse_adr_rs.py /downloads/adr_rs_june2026.pdf
"""
from __future__ import annotations

import difflib
import json
import re
import subprocess
import sys
from pathlib import Path

from tracker.utils.name_match import name_matches

DATA = Path(__file__).resolve().parent.parent / "data"

ROW_RE = re.compile(
    r"^\s*(\d+)\s{2,}(.+?)\s{2,}([A-Z][A-Z &.'()/-]+?)\s{2,}"
    r"\((\d{4}\s*-\s*\d{4})\)\s{2,}([A-Za-z][A-Za-z .&()/-]*?)\s{2,}"
    r"(\d{2})\s{2,}([\d,]+)\s{2,}([\d,]+)\s{2,}(Y|N)\s*$"
)
NAME_RE = re.compile(r"^\s*\d*\s*Name\s*:\s*(.+?)\s*$")
def _name_only(raw: str) -> str:
    return re.split(r"\s{4,}", raw)[0].strip()

FIELD_RE = re.compile(r"^\s*(Total Cases|Serious IPC|Serious BNS|Other IPC|Other BNS)\s*:\s*(\d+)")
STATE_RE = re.compile(r"^\s*State/UT\s*:\s*(.+?)\s*$")
PENDING_RE = re.compile(r"Cases \(Pending\)")
CONVICTED_RE = re.compile(r"Cases \(Convicted\)")
NOCASES_RE = re.compile(r"No Cases")
ITEM_RE = re.compile(r"^\s*\d+\.\s+IPC Sections")



FLEX2_RE = re.compile(
    r"^\s*(\d+)\s{2,}(.*?)\s*\((\d{4}\s*-\s*\d{4})\)\s{2,}(.*?)"
    r"\s{2,}(\d{2})\s{2,}([\d,]+)\*?\s{2,}([\d,]+)\*?\s+(Y|N)\s*$"
)

STATE_WORDS = [
    "ANDHRA PRADESH", "ARUNACHAL PRADESH", "ASSAM", "BIHAR", "CHHATTISGARH", "CHATTISGARH", "GOA",
    "GUJARAT", "HARYANA", "HIMACHAL PRADESH", "JAMMU & KASHMIR", "JAMMU AND KASHMIR",
    "JHARKHAND", "KARNATAKA", "KERALA", "KERALAM", "MADHYA PRADESH", "MAHARASHTRA",
    "MANIPUR", "MEGHALAYA", "MIZORAM", "NAGALAND", "NCT OF DELHI",
    "NATIONAL CAPITAL TERRITORY OF DELHI", "ODISHA", "PUDUCHERRY", "PUNJAB",
    "RAJASTHAN", "SIKKIM", "TAMIL NADU", "TELANGANA", "TRIPURA", "UTTAR PRADESH",
    "UTTARAKHAND", "WEST BENGAL",
]


def split_name_state(text: str, states: list[str]) -> tuple[str, str]:
    t = " ".join(text.split())
    up = t.upper()
    for s in sorted(states, key=len, reverse=True):
        if up.endswith(s):
            name = t[: -len(s)].strip(" -")
            return name, s
    return t, ""

def num(s: str) -> float:
    return float(s.replace(",", ""))


def alnum(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


by_slug_global: dict[str, dict] = {}

# Verified affidavit-name -> roster-name divergences (same person, different name form)
MANUAL_NAMES = {
    ("mohdimarankhan", "maharashtra"): "Imran Pratapgarhi",  # affidavit name Mohammed Imran Khan
    ("kesharidevsinh", "gujarat"): "Kesridevsinh Jhala",
    ("narayansakrishnasa", "karnataka"): "Narayanasa K. Bhandage",
}
MANUAL_MAP: dict[tuple[str, str], dict] = {}


def match_roster(name: str, state: str, roster: list[dict]) -> dict | None:
    state_key = state.strip().lower()
    pool = [m for m in roster if alnum(m["state_caption"]) == alnum(state_key) or alnum(m["state_slug"]) == alnum(state_key.replace(" ", "-"))]
    if not pool:
        pool = roster
    exact = [m for m in pool if name_matches(m["name"], name) or name_matches(name, m["name"])]
    if len(exact) == 1:
        return exact[0]
    names = {alnum(m["name"]): m for m in pool}
    key = alnum(name)
    if key in names:
        return names[key]
    close = difflib.get_close_matches(key, list(names), n=1, cutoff=0.82)
    if close:
        return names[close[0]]
    # concatenated-token fallback: ADR "Bandi Partha Saradhi" vs roster "B. Parthasaradhi Reddy"
    # score each candidate by total matched-token length; require a unique best
    scored: list[tuple[int, dict]] = []
    for m in pool:
        score = sum(len(tok) for tok in re.findall(r"[a-z]{5,}", m["name"].lower()) if tok in key)
        if score:
            scored.append((score, m))
    if scored:
        scored.sort(key=lambda t: -t[0])
        if len(scored) == 1 or scored[0][0] > scored[1][0] * 1.5:
            return scored[0][1]
    return MANUAL_MAP.get((alnum(name), alnum(state)))


def main() -> int:
    pdf = sys.argv[1]
    txt = subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True, check=True).stdout
    lines = txt.splitlines()

    roster = json.loads((DATA / "_meta" / "rs_roster.json").read_text())["members"]
    by_slug = {m["slug"]: m for m in roster}
    by_slug_global.update(by_slug)
    for (nkey, skey), rname in MANUAL_NAMES.items():
        cand = [m for m in roster if m["name"] == rname and alnum(m["state_slug"]) == alnum(skey.replace(" ", "-"))]
        if cand:
            MANUAL_MAP[(nkey, skey)] = cand[0]
    out: dict[str, dict] = {}
    unmatched: list[str] = []

    # --- asset appendix rows ---
    WRAP_RE = re.compile(
        r"^\s*(\d+)\s{2,}([A-Z][A-Z &.'()/-]+?)\s{2,}"
        r"\((\d{4}\s*-\s*\d{4})\)\s{2,}([A-Za-z][A-Za-z .&()/-]*?)\s{2,}"
        r"(\d{2})\s{2,}([\d,]+)\s{2,}([\d,]+)\s{2,}(Y|N)\s*$"
    )
    FRAG_RE = re.compile(r"^\s{1,15}([A-Za-z][A-Za-z .&'()-]{3,}?)(?:\s{2,}[\d,]{6,})?\s*$")
    asset_rows = 0
    for idx, ln in enumerate(lines):
        m = ROW_RE.match(ln)
        if m:
            _, name, state, term, party, age, movable, immovable, pan = m.groups()
            if not name.strip():
                m = None
        if m:
            pass
        else:
            w = WRAP_RE.match(ln)
            if w and idx > 0:
                _, state, term, party, age, movable, immovable, pan = w.groups()
                prev = FRAG_RE.match(lines[idx - 1])
                if prev:
                    name = prev.group(1)
                    if idx + 1 < len(lines):
                        nxt = FRAG_RE.match(lines[idx + 1])
                        if nxt and "Crore" not in lines[idx + 1] and not re.search(r"[\d,]{5,}", nxt.group(1)):
                            name = name + " " + nxt.group(1)
                else:
                    f = FLEX2_RE.match(ln)
                    if not f:
                        continue
                    _, namestate, term, party, age, movable, immovable, pan = f.groups()
                    name, state = split_name_state(namestate, STATE_WORDS)
            else:
                f = FLEX2_RE.match(ln)
                if not f:
                    continue
                _, namestate, term, party, age, movable, immovable, pan = f.groups()
                name, state = split_name_state(namestate, STATE_WORDS)
                if not name.strip() and idx > 0:
                    prev = FRAG_RE.match(lines[idx - 1])
                    if prev:
                        name = prev.group(1)
            # name may continue on the line after the row
            if idx + 1 < len(lines):
                nxt = FRAG_RE.match(lines[idx + 1])
                if nxt and "Crore" not in lines[idx + 1] and not re.search(r"[\d,]{5,}", nxt.group(1)):
                    name = name + " " + nxt.group(1)
        m = m if m else True
        r = match_roster(name, state, roster)
        if r is None:
            unmatched.append(f"asset: {name} ({state})")
            continue
        e = out.setdefault(r["slug"], {"name": r["name"]})
        e["assets"] = {
            "movable_assets": num(movable),
            "immovable_assets": num(immovable),
            "total_assets": num(movable) + num(immovable),
            "pan_given": pan == "Y",
            "age": int(age),
            "party_adr": party.strip(),
            "term": term,
            "source": "adr_rs_june2026",
        }
        asset_rows += 1

    # --- criminal appendix blocks ---
    i = 0
    crim_rows = 0
    while i < len(lines):
        nm = NAME_RE.match(lines[i])
        if not nm:
            i += 1
            continue
        name = _name_only(nm.group(1))
        block: dict = {"total_cases": 0, "serious_ipc": 0, "serious_bns": 0, "other_ipc": 0, "other_bns": 0, "pending_items": 0, "convicted_items": 0}
        state = ""
        section = None
        j = i + 1
        while j < len(lines) and j < i + 120:
            ln = lines[j]
            if NAME_RE.match(ln):
                break
            sm = STATE_RE.match(ln)
            if sm:
                state = _name_only(sm.group(1))
            fm = FIELD_RE.match(ln)
            if fm:
                block[fm.group(1).lower().replace(" ", "_")] = int(fm.group(2))
            if PENDING_RE.search(ln):
                section = "pending"
            elif CONVICTED_RE.search(ln):
                section = "convicted"
            elif NOCASES_RE.search(ln):
                pass
            elif section and ITEM_RE.match(ln):
                block[f"{section}_items"] += 1
            j += 1
        r = match_roster(name, state, roster)
        if r is None:
            unmatched.append(f"criminal: {name} ({state})")
        else:
            e = out.setdefault(r["slug"], {"name": r["name"]})
            e["criminal"] = {
                "total_cases": block["total_cases"],
                "serious_cases": block["serious_ipc"] + block["serious_bns"],
                "pending_cases": block["total_cases"] if block["convicted_items"] == 0 else max(block["total_cases"] - block["convicted_items"], 0),
                "convictions": block["convicted_items"],
                "disposed_cases": 0,
                "source": "adr_rs_june2026",
            }
            crim_rows += 1
        i = j

    # MPs analysed but absent from criminal appendix => 0 declared cases
    zero = 0
    for slug, e in out.items():
        if "assets" in e and "criminal" not in e:
            e["criminal"] = {"total_cases": 0, "serious_cases": 0, "pending_cases": 0, "convictions": 0, "disposed_cases": 0, "source": "adr_rs_june2026"}
            zero += 1

    (DATA / "_meta" / "rs_adr.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"assets matched: {asset_rows}; criminal blocks: {crim_rows}; zero-case inferred: {zero}; total entries: {len(out)}")
    print(f"unmatched: {len(unmatched)}")
    for u in unmatched[:20]:
        print("  ", u)
    no_data = [m["name"] for m in roster if m["slug"] not in out]
    print(f"roster MPs with no ADR data: {len(no_data)}")
    for n in no_data[:15]:
        print("   no-data:", n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
