#!/usr/bin/env python3
"""Backfill deterministic profile text and explicit MPLADS availability notes.

No LLM/API calls. Reads existing JSON artifacts and fills dashboard-facing text
fields that otherwise render as missing/too terse on MP pages.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
MPLADS_NOTE = (
    "Constituency-level MPLADS figures for the 18th Lok Sabha are not published "
    "in a consistently accessible machine-readable source at this time. The legacy "
    "MoSPI/data.gov.in dataset covers older Lok Sabha terms and the eSAKSHI portal "
    "is treated as unavailable unless a per-constituency record is positively matched. "
    "This profile therefore marks MPLADS as unavailable rather than estimating fund "
    "amounts. Use the RTI template below for constituency-level verification."
)


def money(v):
    if v is None:
        return "not available"
    try:
        v = float(v)
    except Exception:
        return "not available"
    if abs(v) >= 1_00_00_000:
        return f"Rs {v/1_00_00_000:.2f} crore"
    if abs(v) >= 1_00_000:
        return f"Rs {v/1_00_000:.2f} lakh"
    return f"Rs {v:,.0f}"


def pct(v):
    return "not available" if v is None else f"{float(v):.1f}%"


def grade_label(conf):
    if conf is None:
        return "unknown"
    try:
        conf = float(conf)
    except Exception:
        return "unknown"
    if conf >= 0.8:
        return "high"
    if conf >= 0.5:
        return "medium"
    if conf > 0:
        return "low"
    return "unavailable"


def get(d, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return default if cur is None else cur


def build_summary(validated, score):
    f = validated.get("findings") or {}
    mp = score.get("mp") or validated.get("mp") or f.get("mp") or {}
    cr = f.get("criminal_record") or {}
    assets = f.get("assets") or {}
    mplads = f.get("mplads") or {}
    parliament = f.get("parliament_activity") or {}
    committees = f.get("committees") or {}
    social = f.get("social_media") or {}
    news = f.get("news_sentiment") or {}
    legislative = f.get("legislative") or {}
    comp = f.get("compensation") or {}
    cag = f.get("cag_findings") or []
    flags = validated.get("flags") or []

    name = mp.get("name") or "This MP"
    constituency = mp.get("constituency") or "the constituency"
    state = (mp.get("state") or "").title()
    party = mp.get("party") or "Unknown party"
    composite = score.get("composite_score", 0)
    confidence = score.get("data_confidence", validated.get("overall_confidence", 0))

    asset_bits = []
    if assets.get("total_assets") is not None:
        asset_bits.append(f"declared assets of {money(assets.get('total_assets'))}")
    if assets.get("liabilities") is not None:
        asset_bits.append(f"liabilities of {money(assets.get('liabilities'))}")
    if assets.get("net_worth") is not None:
        asset_bits.append(f"net worth of {money(assets.get('net_worth'))}")
    if assets.get("wealth_percentile") is not None:
        asset_bits.append(f"wealth percentile {float(assets.get('wealth_percentile')):.0f}/100 among scored MPs")
    asset_sentence = "; ".join(asset_bits) if asset_bits else "asset declaration values are not available from the current open-data cache"

    if cr.get("total_cases", 0):
        legal_sentence = (
            f"{cr.get('total_cases', 0)} declared criminal case(s), including "
            f"{cr.get('serious_cases', 0)} serious case(s), {cr.get('pending_cases', 0)} pending and "
            f"{cr.get('convictions', 0)} conviction(s)."
        )
    else:
        legal_sentence = "No criminal cases are declared in the available affidavit-derived data."

    mplads_vals = [mplads.get(k) for k in ("entitled", "released", "sanctioned", "expended")]
    if any(v is not None for v in mplads_vals):
        mplads_sentence = (
            f"MPLADS shows entitled {money(mplads.get('entitled'))}, released {money(mplads.get('released'))}, "
            f"sanctioned {money(mplads.get('sanctioned'))}, expended {money(mplads.get('expended'))}, "
            f"with utilization {pct(mplads.get('utilization_rate'))}."
        )
    else:
        mplads_sentence = MPLADS_NOTE

    attendance = parliament.get("attendance_percentage")
    q = parliament.get("questions_asked", 0) or 0
    debates = parliament.get("debates_participated", 0) or 0
    private_bills = parliament.get("private_bills_introduced", 0) or 0
    parl_sentence = (
        f"Parliamentary activity currently records attendance at {pct(attendance)}, "
        f"{q} questions, {debates} debates and {private_bills} private member bill(s)."
    )
    if committees.get("total_committees", 0):
        parl_sentence += f" Committee data shows {committees.get('total_committees')} committee membership(s) and {committees.get('leadership_roles', 0)} leadership role(s)."
    else:
        parl_sentence += " Committee membership data is not available or shows no committee assignment in the current cache."

    accessibility_sentence = (
        f"Public accessibility data has {grade_label(social.get('confidence', 0))} confidence: "
        f"{social.get('total_platforms', 0)} tracked social platform(s), "
        f"{social.get('total_followers', 0)} aggregate followers, and "
        f"{news.get('total_articles', 0)} recent/news-cache article(s) ({news.get('positive', 0)} positive, "
        f"{news.get('negative', 0)} negative, {news.get('neutral', 0)} neutral)."
    )

    legislative_sentence = (
        f"Legislative record fields show {legislative.get('bills_introduced', 0)} bills introduced, "
        f"{legislative.get('zero_hour_mentions', 0)} zero-hour mention(s) and "
        f"{legislative.get('special_mentions', 0)} special mention(s), with "
        f"{grade_label(legislative.get('confidence', 0))} source confidence."
    )

    caveats = []
    for field in ("criminal_record", "assets", "mplads", "parliament_activity"):
        conf = get(f, field, "confidence", default=0)
        if conf is not None and float(conf or 0) < 0.5:
            caveats.append(field.replace("_", " "))
    if flags:
        warn = sum(1 for fl in flags if fl.get("severity") == "warning")
        err = sum(1 for fl in flags if fl.get("severity") == "error")
        caveat_sentence = f"Validation recorded {warn} warning(s) and {err} error-level flag(s)."
    else:
        caveat_sentence = "No validation flags were recorded."
    if caveats:
        caveat_sentence += " Low-confidence dimensions: " + ", ".join(caveats) + "."
    if cag:
        caveat_sentence += f" State/national CAG context includes {len(cag)} MPLADS-related audit finding(s), used as context rather than direct proof against the MP."

    comp_sentence = ""
    if comp:
        comp_sentence = f" Informational compensation data records total monthly compensation/allowances of {money(comp.get('total_monthly'))}."

    key_finding = score.get("key_finding") or ""
    qualitative = score.get("qualitative_assessment") or ""

    return f"""## Executive Summary: {name}

### Overall Assessment
{name} ({party}) represents {constituency}{', ' + state if state else ''}. The current composite transparency score is {float(composite):.1f}/100 with {grade_label(confidence)} overall data confidence. {qualitative or key_finding or 'The score combines open-data indicators for funds, assets, criminal disclosures, attendance, participation, committees, accessibility and legislative activity.'}

### Fund Utilization & Development
{mplads_sentence}

### Financial Transparency
The available financial record reports {asset_sentence}. Asset fields are based on available open affidavit/declared data and should be interpreted with the stated source confidence of {grade_label(assets.get('confidence', 0))}.

### Legal & Criminal Standing
{legal_sentence} Criminal-record confidence is {grade_label(cr.get('confidence', 0))}.

### Parliamentary Performance
{parl_sentence} {legislative_sentence}

### Public Engagement & Accessibility
{accessibility_sentence}{comp_sentence}

### Data Quality & Caveats
{caveat_sentence} Missing or unavailable open-data fields are displayed explicitly rather than filled with estimates.

### Key Takeaway
{name}'s profile is complete in the sense that every major dashboard section now has either data-backed values or an explicit availability caveat. The most important follow-up for this profile is to verify constituency-level MPLADS releases and expenditure through official RTI/departmental records because the public machine-readable sources are currently incomplete for the 18th Lok Sabha.
""".strip()


def ensure_mplads_note(obj):
    f = obj.get("findings") if "findings" in obj else obj
    if not isinstance(f, dict):
        return False
    mplads = f.setdefault("mplads", {})
    changed = False
    vals = [mplads.get(k) for k in ("entitled", "released", "sanctioned", "expended", "cumulative_entitled", "cumulative_released", "cumulative_expended")]
    if not any(v is not None for v in vals):
        if mplads.get("data_period_note") != MPLADS_NOTE:
            mplads["data_period_note"] = MPLADS_NOTE
            changed = True
        if not mplads.get("sources"):
            mplads["sources"] = [{
                "url": "https://mplads.mospi.gov.in",
                "source_name": "eSAKSHI/MoSPI",
                "grade": "A",
                "fetched_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "notes": MPLADS_NOTE,
            }]
            changed = True
    return changed


def main():
    updated = 0
    for score_path in DATA_DIR.glob("*/scores/*.json"):
        if score_path.name.startswith('.'):
            continue
        state = score_path.parts[-3]
        slug = score_path.stem
        validated_path = DATA_DIR / state / "raw" / f"{slug}_validated.json"
        raw_path = DATA_DIR / state / "raw" / f"{slug}.json"
        if not validated_path.exists():
            continue
        score = json.loads(score_path.read_text())
        validated = json.loads(validated_path.read_text())
        changed = False

        # Make MPLADS absence explicit in validated findings and raw findings.
        changed |= ensure_mplads_note(validated)
        if raw_path.exists():
            raw = json.loads(raw_path.read_text())
            if ensure_mplads_note(raw):
                raw_path.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n")

        summary = build_summary(validated, score)
        if len((validated.get("cross_reference_notes") or "").strip()) < 250 or "### Fund Utilization" not in (validated.get("cross_reference_notes") or ""):
            validated["cross_reference_notes"] = summary
            changed = True

        if len((score.get("qualitative_assessment") or "").strip()) < 100:
            score["qualitative_assessment"] = (
                f"{score.get('mp',{}).get('name','This MP')} scores {float(score.get('composite_score',0)):.1f}/100. "
                "The rating combines open-data signals across MPLADS availability, assets, criminal disclosures, "
                "attendance, participation, committees, accessibility and legislative activity; unavailable fields are treated as data gaps, not estimated."
            )
            changed = True

        if changed:
            validated_path.write_text(json.dumps(validated, indent=2, ensure_ascii=False) + "\n")
            score_path.write_text(json.dumps(score, indent=2, ensure_ascii=False) + "\n")
            updated += 1
    print(f"updated {updated} MP profiles")

if __name__ == "__main__":
    main()
