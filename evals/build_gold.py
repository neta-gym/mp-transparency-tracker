#!/usr/bin/env python3
"""Generate evals/gold.json from the real MP data index.

Expectations are computed from the DATA (the number in the record must be
the number in the answer), not from the answer templates - so a template
regression that changes or drops a number fails the eval. Deterministic:
fixed MP/topic picks where the records exist, fixed refusal + Hindi cases.
"""

from __future__ import annotations

import json
from pathlib import Path

from voice.data_index import MPDataIndex

OUT = Path(__file__).parent / "gold.json"

# (topic, question template, expect formatter) - formatters mirror the
# template wording so substring checks hit the spoken number exactly.
TOPICS = [
    ("attendance", "What is the attendance of {name}?",
     lambda r: [r.name, f"{r.attendance_pct:.0f} percent"] if r.attendance_pct is not None else None),
    ("funds", "How much MPLADS fund did {name} spend?",
     lambda r: [r.name, f"{r.mplads_expended_cr:.1f} crore rupees"] if r.mplads_expended_cr is not None else None),
    ("criminal", "How many criminal cases does {name} have?",
     lambda r: [r.name, ("no criminal cases" if r.criminal_cases == 0 else f"{r.criminal_cases} criminal cases")]
       if r.criminal_cases is not None else None),
    ("assets", "What are the declared assets of {name}?",
     lambda r: [r.name, f"{r.total_assets / 1e7:.1f} crore rupees"] if r.total_assets and r.total_assets >= 1e7 else None),
    ("questions", "How many questions has {name} asked in Parliament?",
     lambda r: [r.name, f"{r.questions_asked} questions"] if r.questions_asked is not None else None),
    ("score", "What is the transparency score of {name}?",
     lambda r: [r.name, f"{r.composite_score:.1f} out of 100"] if r.composite_score is not None else None),
]

# Well-known MPs to prefer; the generator skips any that are missing or
# lack the metric, so the gold set tracks the dataset as it grows.
PREFERRED = ["Narendra Modi", "Rahul Gandhi", "Amit Shah", "Smriti Irani",
             "Nirmala Sitharaman", "Akhilesh Yadav", "Owaisi", "Mamata"]

REFUSAL_CASES = [
    {"question": "What is the attendance of Zyxnotarealperson Qwerty?", "kind": "refusal"},
    {"question": "How many criminal cases does Fake Name McFakeface have?", "kind": "refusal"},
    {"question": "What is the GDP of India?", "kind": "refusal"},
    {"question": "Who will win the next election?", "kind": "refusal"},
]


def main() -> None:
    index = MPDataIndex()
    gold: list[dict] = []
    used = set()
    # One topic per preferred MP, rotating topics
    picks = [index.find(p) for p in PREFERRED]
    picks = [p for p in picks if p is not None]
    for i, rec in enumerate(picks):
        topic, qt, fmt = TOPICS[i % len(TOPICS)]
        expect = fmt(rec)
        if expect is None or rec.slug in used:
            continue
        used.add(rec.slug)
        gold.append({"question": qt.format(name=rec.name), "kind": "accuracy",
                     "expect": expect})
    # Hindi cases: romanized, for the first two MPs that have attendance data
    hindi_done = 0
    for rec in picks:
        if rec.attendance_pct is None or hindi_done >= 2:
            continue
        hindi_done += 1
        gold.append({"question": f"{rec.name} ki haziri kaisi hai?",
                     "kind": "hindi", "expect": [f"{rec.attendance_pct:.0f} percent"]})
    # Devanagari: Rahul Gandhi has no attendance data -> honest Hindi refusal
    gold.append({"question": "राहुल गांधी की हाजिरी कितनी है?",
                 "kind": "hindi", "expect": ["available nahin"]})
    gold.extend(REFUSAL_CASES)
    OUT.write_text(json.dumps(gold, indent=1, ensure_ascii=False))
    kinds = {}
    for g in gold:
        kinds[g["kind"]] = kinds.get(g["kind"], 0) + 1
    print(f"wrote {len(gold)} cases to {OUT}: {kinds}")


if __name__ == "__main__":
    main()
