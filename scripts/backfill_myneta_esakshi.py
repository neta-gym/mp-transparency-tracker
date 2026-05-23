#!/usr/bin/env python3
"""Backfill MyNeta declarations and eSAKSHI MPLADS figures for generated MP data.

Open-data only: MyNeta/ADR public HTML pages and official MoSPI eSAKSHI portal.
This updates generated raw/validated/score JSON artifacts and rebuilds state/national
leaderboards. It is resumable and safe to re-run.
"""

from __future__ import annotations

import argparse
import asyncio
import glob
import json
import os
import re
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from tracker.agents.assessor import calc_asset_score, calc_criminal_score, calc_mplads_score  # noqa: E402
from tracker.config import MYNETA_STATE_IDS, settings  # noqa: E402
from tracker.models.schemas import House, MPProfile  # noqa: E402
from tracker.tools.browser import PlaywrightBrowser  # noqa: E402
from tracker.tools.esakshi import ESAKSHIFetcher  # noqa: E402
from tracker.tools.myneta import MyNetaParser  # noqa: E402
from tracker.tools.scraper import AsyncScraper  # noqa: E402
from tracker.utils.name_match import name_matches, normalize_state  # noqa: E402
from tracker.utils.mplads_calc import adjusted_utilization_rate  # noqa: E402

DATA_DIR = ROOT / "data"
MYNETA_BASE = "https://myneta.info/LokSabha2024/"
MYNETA_UA = {"User-Agent": "Mozilla/5.0"}
MYNETA_CACHE = DATA_DIR / "enrichment" / "myneta_loksabha2024_candidates.json"

# Direct MyNeta candidate-page overrides for elected MPs whose names differ
# enough from Sansad/seed data that summary-page fuzzy matching is unsafe, or
# whose records are absent from the cached state summary pages (notably
# by-election candidates). Keys are normalized state + constituency names.
MYNETA_DIRECT_OVERRIDES: dict[tuple[str, str], int] = {
    ("andhra pradesh", "narasaraopet"): 5116,  # Lavu Srikrishna Devarayalu
    ("haryana", "hisar"): 8547,  # Jai Parkash (J P) S/O Harikesh
    ("kerala", "wayanad"): 9673,  # Priyanka Gandhi Vadra (by-election)
    ("maharashtra", "nanded"): 1782,  # Vasantrao Balwantrao Chavan
    ("maharashtra", "satara"): 4320,  # Udayanraje Pratapsinhamaharaj Bhonsle
    ("tamil nadu", "salem"): 176,  # Selvaganapathi T M
    ("tamil nadu", "vellore"): 216,  # Dm Kathir Anand
    ("uttar pradesh", "robertsganj"): 9098,  # Chhotelal
    ("uttar pradesh", "bareilly"): 3486,  # Chhatra Pal Singh Gangwar
    ("uttar pradesh", "rampur"): 902,  # Mohibbullah
}


def parse_amount(text: str | None) -> float | None:
    if not text:
        return None
    cleaned = text.replace("\xa0", " ").replace("&nbsp;", " ")
    match = re.search(r"Rs\.?\s*([\d,]+)", cleaned, re.IGNORECASE)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


@dataclass
class MyNetaCandidate:
    state: str
    candidate_id: int
    name: str
    party: str
    criminal_cases: int
    education: str
    age: int | None
    total_assets: float | None
    liabilities: float | None

    @property
    def norm_name(self) -> str:
        return normalize_person_name(self.name)


def normalize_person_name(name: str | None) -> str:
    s = (name or "").lower()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"\b(?:dr|prof|adv|captain|capt|shri|smt|kumari|alias)\b\.?", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def fetch_url(url: str) -> str:
    req = urllib.request.Request(url, headers=MYNETA_UA)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_myneta_state_page(state: str, state_id: int, page: int = 1) -> tuple[list[MyNetaCandidate], int]:
    url = f"{MYNETA_BASE}index.php?action=show_constituencies&state_id={state_id}"
    if page > 1:
        url += f"&page={page}"
    html = fetch_url(url)
    soup = BeautifulSoup(html, "lxml")

    last_page = page
    for link in soup.find_all("a", href=True):
        m = re.search(r"page=(\d+)", link["href"])
        if m:
            last_page = max(last_page, int(m.group(1)))

    out: list[MyNetaCandidate] = []
    for tr in soup.find_all("tr"):
        link = tr.find("a", href=re.compile(r"candidate\.php\?candidate_id=\d+"))
        cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if not link or len(cells) < 8:
            continue
        cid_match = re.search(r"candidate_id=(\d+)", link.get("href", ""))
        if not cid_match:
            continue
        try:
            cases = int(re.sub(r"\D+", "", cells[3]) or "0")
        except ValueError:
            cases = 0
        try:
            age = int(cells[5]) if cells[5].isdigit() else None
        except ValueError:
            age = None
        out.append(MyNetaCandidate(
            state=state,
            candidate_id=int(cid_match.group(1)),
            name=cells[1],
            party=cells[2],
            criminal_cases=cases,
            education=cells[4],
            age=age,
            total_assets=parse_amount(cells[6]),
            liabilities=parse_amount(cells[7]),
        ))
    return out, last_page


def scrape_myneta_candidates(use_cache: bool = True) -> dict[str, list[dict[str, Any]]]:
    MYNETA_CACHE.parent.mkdir(parents=True, exist_ok=True)
    if use_cache and MYNETA_CACHE.exists():
        return json.loads(MYNETA_CACHE.read_text())

    by_state: dict[str, list[dict[str, Any]]] = {}
    for state, state_id in MYNETA_STATE_IDS.items():
        candidates: list[MyNetaCandidate] = []
        page1, last_page = parse_myneta_state_page(state, state_id, 1)
        candidates.extend(page1)
        for page in range(2, last_page + 1):
            try:
                page_candidates, _ = parse_myneta_state_page(state, state_id, page)
                candidates.extend(page_candidates)
                time.sleep(0.15)
            except Exception as exc:
                print(f"WARN: MyNeta page failed for {state} page {page}: {exc}")
        by_state[state] = [c.__dict__ for c in candidates]
        print(f"MyNeta {state}: {len(candidates)} candidates across {last_page} page(s)")

    MYNETA_CACHE.write_text(json.dumps(by_state, indent=2, ensure_ascii=False))
    return by_state


def myneta_direct_candidate(candidate_id: int) -> dict[str, Any] | None:
    """Fetch a specific MyNeta candidate page and convert it to summary shape."""
    try:
        html = fetch_url(f"{MYNETA_BASE}candidate.php?candidate_id={candidate_id}")
        criminal, assets, extras = MyNetaParser(None)._parse(html)
        return {
            "candidate_id": candidate_id,
            "name": extras.get("name") or "",
            "party": "",
            "criminal_cases": criminal.total_cases,
            "education": extras.get("education") or "",
            "age": extras.get("age"),
            "total_assets": assets.total_assets,
            "liabilities": assets.liabilities,
        }
    except Exception as exc:
        print(f"WARN: direct MyNeta candidate {candidate_id} failed: {exc}")
        return None


def best_myneta_match(mp: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    state_key = normalize_state(mp.get("state") or "")
    constituency_key = (mp.get("constituency") or "").lower().strip()
    override_id = MYNETA_DIRECT_OVERRIDES.get((state_key, constituency_key))
    if override_id:
        direct = myneta_direct_candidate(override_id)
        if direct:
            return direct

    name = mp.get("name") or ""
    if not name.strip():
        return None
    norm_mp = normalize_person_name(name)
    scored: list[tuple[float, dict[str, Any]]] = []
    for cand in candidates:
        cand_name = cand.get("name", "")
        norm_c = normalize_person_name(cand_name)
        score = 0.0
        if norm_mp and norm_mp == norm_c:
            score = 1.0
        elif name_matches(name, cand_name, min_confidence=0.78):
            score = 0.88
        else:
            mp_tokens = set(norm_mp.split())
            c_tokens = set(norm_c.split())
            if mp_tokens and c_tokens:
                overlap = len(mp_tokens & c_tokens) / max(len(mp_tokens), len(c_tokens))
                if overlap >= 0.72:
                    score = overlap
        if score:
            # Party agreement is useful, but party names differ; do not require it.
            mp_party = (mp.get("party") or "").lower()
            c_party = (cand.get("party") or "").lower()
            if mp_party and c_party and (mp_party in c_party or c_party in mp_party):
                score += 0.05
            scored.append((score, cand))
    if not scored:
        return None
    scored.sort(key=lambda x: x[0], reverse=True)
    if len(scored) > 1 and scored[0][0] < 0.98 and (scored[0][0] - scored[1][0]) < 0.06:
        return None
    return scored[0][1]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def write_json(path: Path, obj: dict[str, Any]) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False))


def raw_paths(states: set[str] | None = None) -> list[Path]:
    paths = [Path(p) for p in glob.glob(str(DATA_DIR / "*" / "raw" / "*.json"))]
    paths = [p for p in paths if not p.name.endswith("_validated.json")]
    if states:
        paths = [p for p in paths if p.parts[-3] in states or normalize_state(p.parts[-3]) in states]
    return sorted(paths)


def sibling_paths(raw_path: Path) -> tuple[Path, Path]:
    validated = raw_path.with_name(raw_path.stem + "_validated.json")
    score = raw_path.parents[1] / "scores" / f"{raw_path.stem}.json"
    return validated, score


def ensure_sources(container: dict[str, Any], source_name: str, url: str, grade: str, notes: str) -> None:
    sources = container.setdefault("sources", [])
    if not any(s.get("source_name") == source_name for s in sources if isinstance(s, dict)):
        sources.append({"url": url, "source_name": source_name, "grade": grade, "notes": notes})


def apply_myneta_to_obj(obj: dict[str, Any], cand: dict[str, Any]) -> bool:
    changed = False
    mp = obj.setdefault("mp", {})
    if cand.get("candidate_id") and mp.get("myneta_candidate_id") != cand["candidate_id"]:
        mp["myneta_candidate_id"] = cand["candidate_id"]
        changed = True
    if cand.get("education") and not mp.get("education"):
        mp["education"] = cand["education"]
        changed = True
    if cand.get("age") and not mp.get("age"):
        mp["age"] = cand["age"]
        changed = True

    assets = obj.setdefault("assets", {})
    if cand.get("total_assets") is not None and assets.get("total_assets") != cand["total_assets"]:
        assets["total_assets"] = cand["total_assets"]
        changed = True
    if cand.get("liabilities") is not None and assets.get("liabilities") != cand["liabilities"]:
        assets["liabilities"] = cand["liabilities"]
        changed = True
    if assets.get("total_assets") is not None and assets.get("liabilities") is not None:
        net = assets["total_assets"] - assets["liabilities"]
        if assets.get("net_worth") != net:
            assets["net_worth"] = net
            changed = True
    if cand.get("total_assets") is not None:
        if assets.get("source") != "myneta":
            assets["source"] = "myneta"
            changed = True
        if assets.get("confidence", 0) < 0.8:
            assets["confidence"] = 0.8
            changed = True
        ensure_sources(assets, "myneta", f"{MYNETA_BASE}candidate.php?candidate_id={cand['candidate_id']}", "B", "MyNeta/ADR Lok Sabha 2024 candidate affidavit summary")

    criminal = obj.setdefault("criminal_record", {})
    cases = int(cand.get("criminal_cases") or 0)
    if criminal.get("confidence", 0) < 0.8 or criminal.get("total_cases") != cases:
        criminal["total_cases"] = cases
        # The state list provides total cases only. Keep existing serious-case detail if already parsed.
        criminal.setdefault("serious_cases", 0)
        criminal.setdefault("convictions", 0)
        criminal["pending_cases"] = cases
        criminal.setdefault("disposed_cases", 0)
        criminal["source"] = "myneta"
        criminal["confidence"] = max(criminal.get("confidence", 0), 0.75)
        ensure_sources(criminal, "myneta", f"{MYNETA_BASE}candidate.php?candidate_id={cand['candidate_id']}", "B", "MyNeta/ADR Lok Sabha 2024 criminal-case summary")
        changed = True

    ev = obj.setdefault("evidence_summary", {})
    if cand.get("total_assets") is not None and ev.get("assets") != "B":
        ev["assets"] = "B"; changed = True
    if ev.get("criminal") != "B":
        ev["criminal"] = "B"; changed = True
    sc = obj.setdefault("sources_consulted", [])
    if "myneta" not in sc:
        sc.append("myneta"); changed = True
    return changed


def apply_myneta(myneta_by_state: dict[str, list[dict[str, Any]]], states: set[str] | None = None) -> tuple[int, int]:
    matched = updated = 0
    for raw_path in raw_paths(states):
        raw = load_json(raw_path)
        mp = raw.get("mp", {})
        state = normalize_state(mp.get("state") or raw_path.parts[-3])
        cand = best_myneta_match(mp, myneta_by_state.get(state, []))
        if not cand:
            continue
        matched += 1
        changed = apply_myneta_to_obj(raw, cand)
        validated_path, score_path = sibling_paths(raw_path)
        validated = load_json(validated_path) if validated_path.exists() else None
        score = load_json(score_path) if score_path.exists() else None
        if validated is not None:
            changed = apply_myneta_to_obj(validated, cand) or changed
        if score is not None:
            if score.get("mp"):
                before = json.dumps(score["mp"], sort_keys=True)
                apply_myneta_to_obj({"mp": score["mp"], "assets": {}, "criminal_record": {}, "evidence_summary": {}, "sources_consulted": []}, cand)
                changed = changed or before != json.dumps(score["mp"], sort_keys=True)
        if changed:
            write_json(raw_path, raw)
            if validated is not None:
                write_json(validated_path, validated)
            if score is not None:
                recompute_score(score, raw)
                write_json(score_path, score)
            updated += 1
    return matched, updated


def mplads_has_amounts(mplads: dict[str, Any]) -> bool:
    return any(mplads.get(k) is not None for k in (
        "entitled", "released", "sanctioned", "expended",
        "cumulative_entitled", "cumulative_released", "cumulative_expended",
    ))


def mplads_model_to_dict(fund: Any) -> dict[str, Any]:
    return json.loads(fund.model_dump_json())


def apply_mplads_to_obj(obj: dict[str, Any], fund_dict: dict[str, Any]) -> bool:
    before = json.dumps(obj.get("mplads", {}), sort_keys=True)
    obj["mplads"] = fund_dict
    if fund_dict.get("confidence", 0) > 0:
        ev = obj.setdefault("evidence_summary", {})
        ev["mplads"] = "A"
        sc = obj.setdefault("sources_consulted", [])
        if "mplads" not in sc:
            sc.append("mplads")
    return before != json.dumps(fund_dict, sort_keys=True)


def recompute_score(score: dict[str, Any], raw: dict[str, Any]) -> None:
    b = score.setdefault("breakdown", {})
    mplads = raw.get("mplads", {})
    assets = raw.get("assets", {})
    criminal = raw.get("criminal_record", {})

    if mplads:
        try:
            # Use Pydantic model to re-use computed utilization_rate / cumulative adjustment logic.
            from tracker.models.schemas import MPLADSFund
            fund_model = MPLADSFund.model_validate(mplads)
            b["mplads_score"] = round(calc_mplads_score(adjusted_utilization_rate(fund_model), works=fund_model.works or None), 1)
        except Exception:
            rate = None
            if mplads.get("released") and mplads.get("expended") is not None:
                rate = mplads["expended"] / mplads["released"] * 100
            b["mplads_score"] = round(calc_mplads_score(rate), 1)

    if assets.get("confidence", 0) > 0:
        growth = assets.get("growth_ratio")
        if growth is None and assets.get("total_assets") is not None and assets.get("previous_total_assets"):
            growth = (assets["total_assets"] - assets["previous_total_assets"]) / assets["previous_total_assets"]
        b["asset_score"] = round(calc_asset_score(growth), 1)

    if criminal.get("confidence", 0) > 0:
        b["criminal_score"] = round(calc_criminal_score(
            criminal.get("total_cases", 0),
            criminal.get("serious_cases", 0),
            criminal.get("convictions", 0),
            criminal.get("pending_cases", 0),
            criminal.get("disposed_cases", 0),
        ), 1)

    w = settings.weights
    score["composite_score"] = round(
        b.get("mplads_score", 0) * w.mplads
        + b.get("asset_score", 0) * w.asset
        + b.get("criminal_score", 0) * w.criminal
        + b.get("attendance_score", 0) * w.attendance
        + b.get("participation_score", 0) * w.participation
        + b.get("committee_score", 0) * w.committee
        + b.get("accessibility_score", 0) * w.accessibility
        + b.get("legislative_score", 0) * w.legislative,
        1,
    )

    confidences = [
        (raw.get("mplads", {}) or {}).get("confidence", 0),
        (raw.get("assets", {}) or {}).get("confidence", 0),
        (raw.get("criminal_record", {}) or {}).get("confidence", 0),
        (raw.get("parliament_activity", {}) or {}).get("confidence", 0),
        (raw.get("committees", {}) or {}).get("confidence", 0),
        (raw.get("social_media", {}) or {}).get("confidence", 0),
        (raw.get("legislative", {}) or {}).get("confidence", 0),
    ]
    score["data_confidence"] = round(sum(confidences) / len(confidences), 2)


def rebuild_leaderboards() -> None:
    from tracker.models.schemas import Leaderboard, LeaderboardEntry

    all_entries = []
    for state_dir in sorted(DATA_DIR.iterdir()):
        scores_dir = state_dir / "scores"
        if not scores_dir.is_dir():
            continue
        entries = []
        for score_path in sorted(scores_dir.glob("*.json")):
            score = load_json(score_path)
            mp = score.get("mp", {})
            b = score.get("breakdown", {})
            entries.append(LeaderboardEntry(
                rank=0,
                mp_name=mp.get("name", ""),
                constituency=mp.get("constituency", ""),
                state=mp.get("state", state_dir.name),
                party=mp.get("party", ""),
                composite_score=score.get("composite_score", 0),
                mplads_score=b.get("mplads_score", 0),
                asset_score=b.get("asset_score", 0),
                criminal_score=b.get("criminal_score", 0),
                attendance_score=b.get("attendance_score", 0),
                participation_score=b.get("participation_score", 0),
                committee_score=b.get("committee_score", 0),
                accessibility_score=b.get("accessibility_score", 0),
                legislative_score=b.get("legislative_score", 0),
                data_confidence=score.get("data_confidence", 0),
                key_finding=score.get("key_finding", ""),
                house=mp.get("house", "lok_sabha"),
                photo_url=mp.get("photo_url"),
            ))
        entries.sort(key=lambda e: e.composite_score, reverse=True)
        for i, entry in enumerate(entries, 1):
            entry.rank = i
        lb = Leaderboard(state=state_dir.name, total_mps=len(entries), entries=entries)
        out = state_dir / "leaderboard" / "latest.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(lb.model_dump_json(indent=2))
        all_entries.extend(entries)

    all_entries.sort(key=lambda e: e.composite_score, reverse=True)
    for i, entry in enumerate(all_entries, 1):
        entry.rank = i
    national = Leaderboard(state="national", total_mps=len(all_entries), entries=all_entries[:50])
    out = DATA_DIR / "national" / "leaderboard" / "latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(national.model_dump_json(indent=2))


async def apply_esakshi(states: set[str] | None = None, refresh_all: bool = False, limit: int | None = None) -> tuple[int, int, int]:
    paths = raw_paths(states)
    if limit:
        paths = paths[:limit]
    scraper = AsyncScraper()
    browser = PlaywrightBrowser()
    fetched = updated = failed = 0
    try:
        await browser.start()
        fetcher = ESAKSHIFetcher(scraper, browser=browser)
        for idx, raw_path in enumerate(paths, 1):
            raw = load_json(raw_path)
            if not refresh_all and mplads_has_amounts(raw.get("mplads", {})):
                continue
            mpd = raw.get("mp", {})
            if (mpd.get("house") or "lok_sabha") != House.LOK_SABHA.value:
                continue
            if not mpd.get("name") or not mpd.get("constituency"):
                failed += 1
                print(f"SKIP blank MP identity: {raw_path}")
                continue
            mp = MPProfile.model_validate(mpd)
            print(f"[{idx}/{len(paths)}] eSAKSHI {mp.state} / {mp.constituency} / {mp.name}")
            try:
                fund = await fetcher.fetch_fund_data(mp)
                fund_dict = mplads_model_to_dict(fund)
                if fund.confidence <= 0 or not mplads_has_amounts(fund_dict):
                    failed += 1
                    print(f"  no eSAKSHI amounts (confidence={fund.confidence})")
                    continue
                fetched += 1
                changed = apply_mplads_to_obj(raw, fund_dict)
                validated_path, score_path = sibling_paths(raw_path)
                validated = load_json(validated_path) if validated_path.exists() else None
                score = load_json(score_path) if score_path.exists() else None
                if validated is not None:
                    changed = apply_mplads_to_obj(validated, fund_dict) or changed
                if score is not None:
                    recompute_score(score, raw)
                    changed = True
                if changed:
                    write_json(raw_path, raw)
                    if validated is not None:
                        write_json(validated_path, validated)
                    if score is not None:
                        write_json(score_path, score)
                    updated += 1
                print(f"  OK entitled={fund.entitled} released={fund.released} expended={fund.expended} util={fund.utilization_rate}")
            except Exception as exc:
                failed += 1
                print(f"  ERROR {exc}")
    finally:
        await browser.close()
        await scraper.close()
    return fetched, updated, failed


def coverage_report() -> dict[str, Any]:
    paths = raw_paths(None)
    totals = {"total": len(paths), "missing_mplads": 0, "missing_assets": 0, "missing_myneta_id": 0, "blank_name": 0}
    by_state: dict[str, dict[str, int]] = {}
    for p in paths:
        obj = load_json(p)
        st = p.parts[-3]
        by_state.setdefault(st, {"total": 0, "missing_mplads": 0, "missing_assets": 0, "missing_myneta_id": 0, "blank_name": 0})
        by_state[st]["total"] += 1
        mp = obj.get("mp", {})
        if not mp.get("name"):
            totals["blank_name"] += 1; by_state[st]["blank_name"] += 1
        if not mp.get("myneta_candidate_id"):
            totals["missing_myneta_id"] += 1; by_state[st]["missing_myneta_id"] += 1
        if not (obj.get("assets") or {}).get("total_assets"):
            totals["missing_assets"] += 1; by_state[st]["missing_assets"] += 1
        if not mplads_has_amounts(obj.get("mplads", {})):
            totals["missing_mplads"] += 1; by_state[st]["missing_mplads"] += 1
    return {"totals": totals, "by_state": by_state}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--states", help="Comma-separated state slugs/names to process")
    p.add_argument("--skip-myneta", action="store_true")
    p.add_argument("--skip-esakshi", action="store_true")
    p.add_argument("--refresh-all-mplads", action="store_true")
    p.add_argument("--refresh-myneta-cache", action="store_true")
    p.add_argument("--limit", type=int)
    return p.parse_args()


async def main() -> int:
    args = parse_args()
    states = None
    if args.states:
        states = {s.strip().replace(" ", "-").lower() for s in args.states.split(",") if s.strip()}
        states |= {normalize_state(s).replace(" ", "-") for s in list(states)}
        states |= {s.replace("-", " ") for s in list(states)}

    if not args.skip_myneta:
        myneta = scrape_myneta_candidates(use_cache=not args.refresh_myneta_cache)
        matched, updated = apply_myneta(myneta, states)
        print(f"MyNeta matched {matched} MPs; updated {updated} artifact sets")

    if not args.skip_esakshi:
        fetched, updated, failed = await apply_esakshi(states, args.refresh_all_mplads, args.limit)
        print(f"eSAKSHI fetched {fetched}; updated {updated}; failed/skipped-no-data {failed}")

    rebuild_leaderboards()
    report = coverage_report()
    out = DATA_DIR / "enrichment" / "coverage_after_backfill.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps(report["totals"], indent=2))
    print(f"Coverage report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
