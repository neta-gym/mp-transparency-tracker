#!/usr/bin/env python3
"""Assemble ResearchFindings raw JSONs for Rajya Sabha MPs.

Combines:
- data/_meta/rs_roster.json (sansad roster)
- data/_meta/rs_works.json (eSAKSHI MPLADS works)
- data/_meta/rs_prs_activity.json (PRS attendance/debates/questions)
- data/_meta/rs_adr.json (ADR criminal + assets, June 2026 report)

Writes data/<state_slug>/raw/<slug>.json (ResearchFindings shape, house=rajya_sabha).
Nominated members go to data/nominated/. LS/RS slug collisions get a "-rs" suffix.

Usage: PYTHONPATH=src python scripts/assemble_rs_findings.py
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from tracker.models.schemas import ResearchFindings

DATA = Path(__file__).resolve().parent.parent / "data"
NOW = datetime.now(timezone.utc).isoformat()

ADR_SRC = {
    "url": "https://adrindia.org/content/Analysis-of-Criminal-Background-Financial-Education-Gender-and-other-details-of-Sitting-Rajya-Sabha-MPs-June2026",
    "source_name": "adr_rs_analysis_june2026",
    "grade": "B",
    "fetched_at": NOW,
    "notes": "ADR/MyNeta analysis of sitting RS MPs' affidavits (June 2026)",
}
ESAKSHI_SRC = {
    "url": "https://mplads.mospi.gov.in/digigov/dashboard.html",
    "source_name": "esakshi",
    "grade": "A",
    "fetched_at": NOW,
    "notes": "Official eSAKSHI REST API - RS member work-level reports (house=1, tenure=sitting)",
}


def main() -> int:
    roster = json.loads((DATA / "_meta" / "rs_roster.json").read_text())["members"]
    works = json.loads((DATA / "_meta" / "rs_works.json").read_text())
    prs = json.loads((DATA / "_meta" / "rs_prs_activity.json").read_text())
    adr = json.loads((DATA / "_meta" / "rs_adr.json").read_text())

    written = collisions = 0
    coverage = {"works": 0, "prs": 0, "adr": 0}
    for m in roster:
        slug = m["slug"]
        state = m["state_slug"]
        raw_dir = DATA / state / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        out_path = raw_dir / f"{slug}.json"
        if out_path.exists():
            existing = json.loads(out_path.read_text())
            if existing.get("mp", {}).get("house") == "lok_sabha":
                slug = f"{slug}-rs"
                out_path = raw_dir / f"{slug}.json"
                collisions += 1

        adr_e = adr.get(m["slug"], {})
        prs_e = prs.get(m["slug"], {})
        works_e = works.get(m["slug"], {})

        criminal = {"source": "none", "confidence": 0.0, "sources": []}
        assets = {"source": "none", "confidence": 0.0, "sources": []}
        if "criminal" in adr_e:
            c = adr_e["criminal"]
            criminal = {
                "total_cases": c["total_cases"],
                "serious_cases": c["serious_cases"],
                "convictions": c.get("convictions", 0),
                "pending_cases": c.get("pending_cases", 0),
                "disposed_cases": c.get("disposed_cases", 0),
                "cases": [],
                "source": "adr_rs_june2026",
                "confidence": 0.85,
                "sources": [ADR_SRC],
            }
            coverage["adr"] += 1
        if "assets" in adr_e:
            a = adr_e["assets"]
            assets = {
                "movable_assets": a["movable_assets"],
                "immovable_assets": a["immovable_assets"],
                "total_assets": a["total_assets"],
                "net_worth": a["total_assets"],
                "asset_year": 2026,
                "source": "adr_rs_june2026",
                "confidence": 0.85,
                "sources": [ADR_SRC],
            }

        mplads = {"source": "esakshi", "confidence": 0.0, "sources": []}
        if "works" in works_e:
            mplads = {
                "works": works_e["works"],
                "works_count": works_e["works_count"],
                "source": "esakshi",
                "confidence": 0.9,
                "sources": [dict(ESAKSHI_SRC, notes=f"RS works: {works_e['works_count']} work-level records")],
            }
            coverage["works"] += 1

        pa = {"source": "none", "confidence": 0.0, "sources": []}
        if "parliament_activity" in prs_e:
            p = prs_e["parliament_activity"]
            pa = {
                **p,
                "confidence": 0.9 if p.get("attendance_percentage") is not None else 0.5,
                "sources": [{
                    "url": prs_e.get("prs_url", ""),
                    "source_name": "prs_website",
                    "grade": "B",
                    "fetched_at": NOW,
                    "notes": "PRS India MP Track - Rajya Sabha",
                }],
            }
            coverage["prs"] += 1

        doc = {
            "mp": {
                "name": m["name"],
                "constituency": f"Rajya Sabha ({m['state_caption']})" if state != "nominated" else "Rajya Sabha (Nominated)",
                "state": state,
                "party": m["party"],
                "slug": slug,
                "house": "rajya_sabha",
                "sansad_member_id": m.get("sansad_rs_mpsno"),
                "profile_url": f"https://sansad.in/rs/members" ,
                "canonical_name": m["name"],
                "name_aliases": [],
                "age": adr_e.get("assets", {}).get("age") or m.get("age"),
                "photo_url": f"/mp-photos/rs/{m['sansad_rs_mpsno']}.jpg" if m.get("sansad_rs_mpsno") else m.get("photo_url"),
            },
            "criminal_record": criminal,
            "assets": assets,
            "mplads": mplads,
            "parliament_activity": pa,
            "sources_consulted": [s for s, ok in [
                ("adrindia.org RS analysis June 2026", "criminal" in adr_e or "assets" in adr_e),
                ("eSAKSHI MPLADS portal", "works" in works_e),
                ("PRS MP Track (Rajya Sabha)", "parliament_activity" in prs_e),
                ("Digital Sansad RS member directory", True),
            ] if ok],
            "collected_at": NOW,
        }
        findings = ResearchFindings.model_validate(doc)
        out_path.write_text(findings.model_dump_json(indent=1) + "\n")
        written += 1

    print(f"wrote {written} RS findings ({collisions} LS/RS slug collisions suffixed)")
    print("coverage:", coverage)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
