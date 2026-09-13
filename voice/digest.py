"""Digest composer for NetaGym Watch subscribers.

One plain-text digest per subscriber: what changed since the last data
refresh for each watched MP, plus the current headline numbers. The same
text feeds the Telegram /digest command and the email digest.
"""

from __future__ import annotations

from .answers import SITE
from .data_index import MPDataIndex, MPRecord
from .watch import WatchStore, load_snapshots, fingerprint, TRACKED_FIELDS, _fmt_value


def _headline(rec: MPRecord) -> str:
    bits = []
    if rec.attendance_pct is not None:
        bits.append(f"attendance {rec.attendance_pct:.0f}%")
    if rec.questions_asked is not None:
        bits.append(f"{rec.questions_asked} questions")
    if rec.criminal_cases is not None:
        bits.append(f"{rec.criminal_cases} criminal cases")
    if rec.composite_score is not None:
        bits.append(f"score {rec.composite_score:.1f}")
        if rec.national_rank:
            bits.append(f"rank {rec.national_rank}/786")
    return ", ".join(bits) if bits else "no metrics on file"


def compose_digest(chat_id: str, index: MPDataIndex, store: WatchStore) -> str:
    slugs = store.watches(chat_id)
    if not slugs:
        return ("You are not watching any MPs yet. "
                "Send /watch <name> and your digest will start filling up.")
    by_slug = {r.slug: r for r in index.records}
    snaps = load_snapshots()
    lines = ["NetaGym Watch digest", ""]
    for slug in slugs:
        rec = by_slug.get(slug)
        if rec is None:
            continue
        lines.append(f"{rec.name} ({rec.constituency}, {rec.state_label})")
        lines.append(f"  Now: {_headline(rec)}")
        prev = snaps.get(slug)
        if prev:
            cur = fingerprint(rec)
            moved = [(dict(TRACKED_FIELDS)[f], _fmt_value(f, prev.get(f)), _fmt_value(f, cur.get(f)))
                     for f, _ in TRACKED_FIELDS if prev.get(f) != cur.get(f)]
            if moved:
                lines.append("  Changed since last refresh:")
                lines.extend(f"    - {label}: {old} -> {new}" for label, old, new in moved)
            else:
                lines.append("  No change since the last data refresh.")
        else:
            lines.append("  Baseline recorded at first refresh after you subscribed.")
        lines.append(f"  Source: {SITE}/mp/{rec.slug}/")
        lines.append("")
    lines.append("Every number above is from public records - attendance and "
                 "questions from sansad.in, criminal and asset data from sworn "
                 "election affidavits (myneta.info), fund usage from MPLADS.")
    return "\n".join(lines)
