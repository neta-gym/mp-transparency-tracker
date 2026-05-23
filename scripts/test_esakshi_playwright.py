#!/usr/bin/env python3
"""Standalone test script for eSAKSHI Playwright-based scraper.

Usage:
    python scripts/test_esakshi_playwright.py           # headless
    python scripts/test_esakshi_playwright.py --headed   # visible browser for debugging
    python scripts/test_esakshi_playwright.py --mp "Bansuri Swaraj" --constituency "New Delhi"
    python scripts/test_esakshi_playwright.py --all-delhi  # test all 7 Delhi LS MPs
"""

from __future__ import annotations

import argparse
import asyncio
import sys

# Ensure the project root is on sys.path
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tracker.models.schemas import MPProfile, House  # noqa: E402
from tracker.tools.browser import PlaywrightBrowser  # noqa: E402
from tracker.tools.esakshi import ESAKSHIFetcher  # noqa: E402
from tracker.tools.scraper import AsyncScraper  # noqa: E402


DELHI_MPS = [
    MPProfile(name="Harsh Malhotra", constituency="East Delhi", state="delhi", party="BJP", house=House.LOK_SABHA),
    MPProfile(name="Kamaljeet Sehrawat", constituency="West Delhi", state="delhi", party="BJP", house=House.LOK_SABHA),
    MPProfile(name="Praveen Khandelwal", constituency="Chandni Chowk", state="delhi", party="BJP", house=House.LOK_SABHA),
    MPProfile(name="Ramvir Singh Bidhuri", constituency="South Delhi", state="delhi", party="BJP", house=House.LOK_SABHA),
    MPProfile(name="Manoj Tiwari", constituency="North East Delhi", state="delhi", party="BJP", house=House.LOK_SABHA),
    MPProfile(name="Yogender Chandoliya", constituency="North West Delhi", state="delhi", party="BJP", house=House.LOK_SABHA),
    MPProfile(name="Bansuri Swaraj", constituency="New Delhi", state="delhi", party="BJP", house=House.LOK_SABHA),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test eSAKSHI Playwright scraper")
    parser.add_argument(
        "--headed", action="store_true",
        help="Run browser in headed (visible) mode for visual debugging",
    )
    parser.add_argument("--mp", default="Manoj Tiwari", help="MP name to look up")
    parser.add_argument("--constituency", default="North East Delhi", help="Constituency")
    parser.add_argument("--state", default="delhi", help="State")
    parser.add_argument("--party", default="BJP", help="Party")
    parser.add_argument(
        "--all-delhi", action="store_true",
        help="Test all 7 Delhi Lok Sabha MPs",
    )
    return parser.parse_args()


def print_fund(mp_name: str, fund) -> bool:
    """Print fund data. Returns True if data was found."""
    print(f"\n{'='*50}")
    print(f"MP: {mp_name}")
    print(f"  Confidence:       {fund.confidence}")
    print(f"  Entitled:         {fund.entitled}")
    print(f"  Released:         {fund.released}")
    print(f"  Sanctioned:       {fund.sanctioned}")
    print(f"  Expended:         {fund.expended}")
    print(f"  Utilization Rate: {fund.utilization_rate}")
    print(f"  Works Count:      {fund.works_count}")
    print(f"  Source:           {fund.source}")
    if fund.sources:
        for src in fund.sources:
            print(f"    - {src.source_name} (Grade {src.grade.value}): {src.notes}")
    return fund.confidence > 0


async def main() -> int:
    args = parse_args()

    if args.all_delhi:
        mps = DELHI_MPS
    else:
        mps = [MPProfile(
            name=args.mp,
            constituency=args.constituency,
            state=args.state,
            party=args.party,
            house=House.LOK_SABHA,
        )]

    print(f"\n--- eSAKSHI Playwright Test ---")
    print(f"MPs to test:   {len(mps)}")
    print(f"Headed mode:   {args.headed}")
    print()

    browser = PlaywrightBrowser(headless=not args.headed)
    scraper = AsyncScraper()

    try:
        print("Starting Playwright browser...")
        await browser.start()
        print("Browser started successfully.\n")

        fetcher = ESAKSHIFetcher(scraper, browser=browser)

        success = 0
        fail = 0

        for mp in mps:
            print(f"\nFetching fund data for {mp.name} ({mp.constituency})...")
            fund = await fetcher.fetch_fund_data(mp)
            if print_fund(mp.name, fund):
                success += 1
            else:
                fail += 1

        print(f"\n{'='*50}")
        print(f"Results: {success} OK, {fail} failed out of {len(mps)} MPs")

        if fail > 0:
            print("\n[FAIL] Some MPs had confidence 0.0")
            return 1
        else:
            print("\n[OK] All MPs have data")
            return 0

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        await browser.close()
        await scraper.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
