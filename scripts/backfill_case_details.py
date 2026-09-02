"""Re-scrape MyNeta candidate pages and extract per-case criminal detail
(FIR no., case no., court, IPC sections, other acts, charges, appeal,
punishment) for every LS MP. Writes side output to case_details/<state>/<slug>.json
- raw MP files are NOT touched here; the output is merged into raw data
at final assembly (before rescore_offline regenerates validated files).

Usage: PYTHONPATH=src python scripts/backfill_case_details.py [--states a,b] [--out DIR]
"""
import argparse
import asyncio
import json
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, "src")

from bs4 import BeautifulSoup  # noqa: E402

from tracker.config import MYNETA_STATE_IDS, settings  # noqa: E402
from tracker.tools.myneta import MyNetaParser  # noqa: E402
from tracker.tools.scraper import AsyncScraper  # noqa: E402
from tracker.utils.name_match import name_matches  # noqa: E402
from tracker.utils.name_match import normalize_state  # noqa: E402

log = logging.getLogger("backfill_cases")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

ALL_STATES = [
    "andhra-pradesh", "arunachal-pradesh", "assam", "bihar", "chhattisgarh", "delhi", "goa",
    "gujarat", "haryana", "himachal-pradesh", "jammu-and-kashmir", "jharkhand", "karnataka",
    "kerala", "madhya-pradesh", "maharashtra", "manipur", "meghalaya", "mizoram", "nagaland",
    "odisha", "punjab", "rajasthan", "sikkim", "tamil-nadu", "telangana", "tripura",
    "uttar-pradesh", "uttarakhand", "west-bengal",
    "andaman-and-nicobar-islands", "chandigarh", "dadra-and-nagar-haveli-and-daman-and-diu",
    "ladakh", "lakshadweep", "puducherry",
]

SEM = asyncio.Semaphore(4)


async def fetch_state_candidates(scraper, state_slug: str) -> list[dict]:
    """Candidate id map from the state's MyNeta constituencies page (same
    approach as mp_discovery._enrich_myneta_ids)."""
    state_norm = state_slug.replace("-", " ")
    state_id = MYNETA_STATE_IDS.get(state_norm)
    if not state_id:
        return []
    url = settings.urls.myneta_state_constituencies.format(state_id=state_id)
    html = await scraper.fetch(url)
    soup = BeautifulSoup(html, "lxml")
    out = []
    for link in soup.find_all("a", href=re.compile(r"candidate\.php\?candidate_id=\d+")):
        m = re.search(r"candidate_id=(\d+)", str(link.get("href") or ""))
        if not m:
            continue
        constituency = ""
        row = link.find_parent("tr")
        if row:
            for cell in row.find_all("td"):
                if cell.find("a", href=re.compile(r"candidate\.php")) is None:
                    t = cell.get_text(strip=True)
                    if t and len(t) > 2 and not t.isdigit():
                        constituency = t
                        break
        out.append({"name": link.get_text(strip=True), "id": int(m.group(1)), "constituency": constituency})
    return out


async def process_mp(scraper, parser, state: str, path: Path, candidates: list[dict], outdir: Path) -> str:
    d = json.load(open(path))
    mp = d.get("mp", {})
    if mp.get("house") == "rajya_sabha":
        return "rs-skip"
    cid = mp.get("myneta_candidate_id")
    if not cid:
        for mc in candidates:
            if name_matches(mp.get("name", ""), mc["name"]) or (
                mc["constituency"]
                and mp.get("constituency")
                and normalize_state(mc["constituency"]) == normalize_state(mp["constituency"])
                and name_matches(mp.get("name", ""), mc["name"], min_confidence=0.4)
            ):
                cid = mc["id"]
                break
    if not cid:
        return "no-id"
    async with SEM:
        try:
            cr, _, _ = await parser.fetch_candidate(int(cid))
        except Exception as e:
            log.warning("fetch failed %s (%s): %s", mp.get("name"), cid, e)
            return "fetch-fail"
    out = {
        "state": state,
        "slug": mp.get("slug") or path.stem,
        "name": mp.get("name"),
        "myneta_candidate_id": int(cid),
        "criminal_record": json.loads(cr.model_dump_json()),
    }
    (outdir / state).mkdir(parents=True, exist_ok=True)
    json.dump(out, open(outdir / state / f"{out['slug']}.json", "w"), indent=2)
    return "ok"


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--states", default=None)
    ap.add_argument("--out", default="/home/sandbox/work/case_details")
    args = ap.parse_args()
    states = args.states.split(",") if args.states else ALL_STATES
    outdir = Path(args.out)
    scraper = AsyncScraper()
    parser = MyNetaParser(scraper)
    stats = {}
    for state in states:
        raw = sorted(Path(f"data/{state}/raw").glob("*.json"))
        raw = [p for p in raw if not p.name.endswith("_validated.json")]
        if not raw:
            log.warning("no raw files for %s", state)
            continue
        try:
            candidates = await fetch_state_candidates(scraper, state)
        except Exception as e:
            log.warning("candidate map failed for %s: %s", state, e)
            candidates = []
        results = await asyncio.gather(*[process_mp(scraper, parser, state, p, candidates, outdir) for p in raw])
        from collections import Counter
        c = Counter(results)
        stats[state] = dict(c)
        log.info("%s: %s", state, dict(c))
        await asyncio.sleep(0.5)
    log.info("SUMMARY %s", json.dumps(stats))
    await scraper.close()


if __name__ == "__main__":
    asyncio.run(main())
