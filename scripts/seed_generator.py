#!/usr/bin/env python3
"""Seed generator — uses PRS India CSV to populate seed_mps.json.

The PRS GitHub CSV contains all 543+ Lok Sabha MPs with name, constituency,
state, and party. This script generates seed data for the pipeline's fallback
discovery mechanism.

Usage:
    # Generate seed data for specific states
    python scripts/seed_generator.py --states "uttar pradesh,maharashtra,bihar"

    # Generate for all states
    python scripts/seed_generator.py --all

    # Dry run (print to stdout, don't write file)
    python scripts/seed_generator.py --states delhi --dry-run

    # List all available states
    python scripts/seed_generator.py --list-states

    # Also try to find MyNeta candidate IDs (slower, scrapes MyNeta)
    python scripts/seed_generator.py --states delhi --enrich-myneta
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import io
import json
import os
import re
import sys

import aiohttp

PRS_CSV_URL = "https://raw.githubusercontent.com/Vonter/india-representatives-activity/main/csv/Lok%20Sabha/18th.csv"
SEED_FILE = os.path.join(os.path.dirname(__file__), "..", "src", "tracker", "data", "seed_mps.json")

# Party name normalization
PARTY_SHORT: dict[str, str] = {
    "Bharatiya Janata Party": "BJP",
    "Indian National Congress": "INC",
    "All India Trinamool Congress": "AITC",
    "Dravida Munnetra Kazhagam": "DMK",
    "Samajwadi Party": "SP",
    "Rashtriya Janata Dal": "RJD",
    "Janata Dal (United)": "JDU",
    "YSR Congress Party": "YSRCP",
    "Telugu Desam Party": "TDP",
    "Shiv Sena": "SHS",
    "Nationalist Congress Party - Sharadchandra Pawar": "NCP-SP",
    "Nationalist Congress Party": "NCP",
    "Communist Party of India (Marxist)": "CPI(M)",
    "Communist Party of India": "CPI",
    "Aam Aadmi Party": "AAP",
    "Bahujan Samaj Party": "BSP",
    "Lok Janshakti Party (Ram Vilas)": "LJPRV",
    "Janata Dal (Secular)": "JDS",
    "Jharkhand Mukti Morcha": "JMM",
    "All India Anna Dravida Munnetra Kazhagam": "AIADMK",
    "Biju Janata Dal": "BJD",
    "Shiv Sena (Uddhav Balasaheb Thackeray)": "SHS-UBT",
    "Indian Union Muslim League": "IUML",
    "Rashtriya Lok Dal": "RLD",
    "Apna Dal (Soneylal)": "AD(S)",
    "Nishad Party": "NISHAD",
    "Hindustani Awam Morcha": "HAM",
}

STATE_NORM: dict[str, str] = {
    "jammu & kashmir": "jammu and kashmir",
    "jammu and kashmir": "jammu and kashmir",
    "nct of delhi": "delhi",
    "andaman & nicobar islands": "andaman and nicobar islands",
    "d&n haveli and daman & diu": "dadra and nagar haveli and daman and diu",
}


def normalize_state(name: str) -> str:
    """Normalize state name."""
    norm = name.strip().lower()
    norm = re.sub(r"\s+", " ", norm)
    return STATE_NORM.get(norm, norm)


def short_party(party: str) -> str:
    """Return short party name if available."""
    return PARTY_SHORT.get(party.strip(), party.strip())


async def fetch_prs_csv() -> list[dict]:
    """Fetch and parse the PRS India CSV with all Lok Sabha MPs."""
    headers = {"User-Agent": "MP-Transparency-Tracker/1.0"}

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(PRS_CSV_URL) as resp:
            resp.raise_for_status()
            text = await resp.text()

    # Auto-detect delimiter (PRS uses semicolons)
    delimiter = ";"
    if ";" not in text[:500] and "," in text[:500]:
        delimiter = ","

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)

    # Sanity check: if we got 0-1 columns, try the other delimiter
    if rows and len(rows[0]) <= 2:
        alt = "," if delimiter == ";" else ";"
        reader = csv.DictReader(io.StringIO(text), delimiter=alt)
        rows = list(reader)

    print(f"Loaded {len(rows)} MPs from PRS CSV", file=sys.stderr)
    return rows


async def enrich_with_myneta(entries: list[dict], state: str) -> None:
    """Try to find MyNeta candidate IDs by scraping constituency pages.

    This is optional and slower — scrapes MyNeta for each state.
    """
    # MyNeta state IDs
    state_ids = {
        "andhra pradesh": 1, "arunachal pradesh": 2, "assam": 3, "bihar": 4,
        "chhattisgarh": 5, "goa": 6, "gujarat": 7, "haryana": 8, "delhi": 9,
        "himachal pradesh": 10, "jammu and kashmir": 11, "jharkhand": 12,
        "karnataka": 13, "kerala": 14, "madhya pradesh": 15, "maharashtra": 16,
        "manipur": 17, "meghalaya": 18, "mizoram": 19, "nagaland": 20,
        "odisha": 21, "punjab": 22, "rajasthan": 23, "sikkim": 24,
        "tamil nadu": 25, "telangana": 26, "tripura": 27, "uttar pradesh": 28,
        "uttarakhand": 29, "west bengal": 30,
    }

    state_id = state_ids.get(state)
    if not state_id:
        return

    url = f"https://myneta.info/LokSabha2024/index.php?action=show_constituencies&state_id={state_id}"
    headers = {"User-Agent": "MP-Transparency-Tracker/1.0"}

    try:
        from bs4 import BeautifulSoup

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as resp:
                html = await resp.text()

        soup = BeautifulSoup(html, "lxml")
        # Build map: candidate_name -> candidate_id
        myneta_map: dict[str, int] = {}
        for link in soup.find_all("a", href=re.compile(r"candidate\.php\?candidate_id=\d+")):
            href = link.get("href", "")
            cid_match = re.search(r"candidate_id=(\d+)", href)
            if cid_match:
                name = link.get_text(strip=True).lower()
                myneta_map[name] = int(cid_match.group(1))

        if not myneta_map:
            print(f"  No MyNeta candidates found for {state}", file=sys.stderr)
            return

        # Match entries to MyNeta candidates
        matched = 0
        for entry in entries:
            mp_name = entry["name"].lower()
            # Direct match
            if mp_name in myneta_map:
                entry["myneta_candidate_id"] = myneta_map[mp_name]
                matched += 1
                continue
            # Try last-name match
            mp_parts = mp_name.split()
            if len(mp_parts) >= 2:
                for mn_name, mn_id in myneta_map.items():
                    mn_parts = mn_name.split()
                    if len(mn_parts) >= 2 and mp_parts[-1] == mn_parts[-1]:
                        # Last name matches, check first name initial
                        if mp_parts[0][0] == mn_parts[0][0]:
                            entry["myneta_candidate_id"] = mn_id
                            matched += 1
                            break

        print(f"  MyNeta enrichment for {state}: {matched}/{len(entries)} matched", file=sys.stderr)

    except Exception as e:
        print(f"  MyNeta enrichment failed for {state}: {e}", file=sys.stderr)


def group_by_state(rows: list[dict]) -> dict[str, list[dict]]:
    """Group PRS CSV rows into seed_mps.json format by state."""
    by_state: dict[str, list[dict]] = {}

    for row in rows:
        state = normalize_state(row.get("State", ""))
        if not state:
            continue

        name = row.get("Name", "").strip()
        constituency = row.get("Constituency", "").strip()
        party = short_party(row.get("Party", "Unknown"))

        if not name or not constituency:
            continue

        if state not in by_state:
            by_state[state] = []

        by_state[state].append({
            "name": name,
            "constituency": constituency,
            "party": party,
        })

    return by_state


def merge_seed_data(existing: dict, new_entries: dict[str, list[dict]], states: list[str]) -> dict:
    """Merge new seed data into existing, only for specified states.

    Preserves existing MyNeta IDs and RS entries.
    """
    result = dict(existing)

    for state in states:
        state_norm = normalize_state(state)
        if state_norm not in new_entries:
            print(f"  WARNING: No PRS data found for '{state_norm}'", file=sys.stderr)
            continue

        new_ls = new_entries[state_norm]

        # Preserve existing RS entries and MyNeta IDs
        existing_state = result.get(state_norm, {})
        existing_rs = existing_state.get("rajya_sabha", [])
        existing_ls = existing_state.get("lok_sabha", [])

        # Build map of existing MyNeta IDs by name
        existing_ids = {}
        for e in existing_ls:
            if e.get("myneta_candidate_id"):
                existing_ids[e["name"].lower()] = e["myneta_candidate_id"]

        # Merge MyNeta IDs into new entries
        for entry in new_ls:
            eid = existing_ids.get(entry["name"].lower())
            if eid:
                entry["myneta_candidate_id"] = eid

        result[state_norm] = {"lok_sabha": new_ls}
        if existing_rs:
            result[state_norm]["rajya_sabha"] = existing_rs

        count = len(new_ls)
        ids_count = sum(1 for e in new_ls if e.get("myneta_candidate_id"))
        print(f"  {state_norm}: {count} LS MPs ({ids_count} with MyNeta IDs)", file=sys.stderr)

    return result


async def main():
    parser = argparse.ArgumentParser(description="Generate seed MP data from PRS India CSV")
    parser.add_argument("--states", type=str, help="Comma-separated states (e.g., 'bihar,maharashtra')")
    parser.add_argument("--all", action="store_true", help="Generate for all states")
    parser.add_argument("--dry-run", action="store_true", help="Print to stdout instead of writing file")
    parser.add_argument("--list-states", action="store_true", help="List all available states from PRS data")
    parser.add_argument("--enrich-myneta", action="store_true", help="Also scrape MyNeta for candidate IDs (slower)")
    args = parser.parse_args()

    if not args.states and not args.all and not args.list_states:
        parser.print_help()
        print("\nExamples:")
        print("  python scripts/seed_generator.py --states 'uttar pradesh,maharashtra'")
        print("  python scripts/seed_generator.py --all --enrich-myneta")
        print("  python scripts/seed_generator.py --list-states")
        sys.exit(1)

    print("Fetching PRS India CSV data...", file=sys.stderr)
    rows = await fetch_prs_csv()

    if not rows:
        print("ERROR: No data fetched from PRS CSV.", file=sys.stderr)
        sys.exit(1)

    by_state = group_by_state(rows)

    if args.list_states:
        print("\nStates found in PRS CSV:")
        for state in sorted(by_state.keys()):
            print(f"  {state}: {len(by_state[state])} LS MPs")
        print(f"\nTotal: {sum(len(v) for v in by_state.values())} MPs across {len(by_state)} states")
        return

    # Determine target states
    if args.all:
        target_states = sorted(by_state.keys())
    else:
        target_states = [s.strip().lower() for s in args.states.split(",") if s.strip()]

    # Optionally enrich with MyNeta IDs
    if args.enrich_myneta:
        print("Enriching with MyNeta candidate IDs...", file=sys.stderr)
        for state in target_states:
            state_norm = normalize_state(state)
            if state_norm in by_state:
                await enrich_with_myneta(by_state[state_norm], state_norm)
                await asyncio.sleep(1)  # Rate-limit MyNeta requests

    # Load existing seed data
    existing: dict = {}
    if os.path.exists(SEED_FILE):
        with open(SEED_FILE) as f:
            existing = json.load(f)

    # Merge
    print("\nMerging seed data:", file=sys.stderr)
    merged = merge_seed_data(existing, by_state, target_states)

    # Sort states for consistent output
    merged = dict(sorted(merged.items()))

    # Output
    output = json.dumps(merged, indent=2, ensure_ascii=False)

    if args.dry_run:
        print(output)
    else:
        with open(SEED_FILE, "w") as f:
            f.write(output + "\n")
        total_states = len(merged)
        total_mps = sum(
            len(houses.get("lok_sabha", [])) + len(houses.get("rajya_sabha", []))
            for houses in merged.values()
        )
        print(f"\nSeed data written to {SEED_FILE}", file=sys.stderr)
        print(f"  States: {total_states}, Total MPs: {total_mps}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
