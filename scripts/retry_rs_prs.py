#!/usr/bin/env python3
"""Second-chance PRS RS slug recovery: token-overlap candidates + page-title identity check."""
from __future__ import annotations
import html as html_mod
import json
import re
import time
import urllib.request
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from tracker.tools.prs import PRSFetcher  # noqa: E402
from tracker.utils.name_match import name_matches  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data"
CACHE = DATA / "_meta" / "rs_prs_cache"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh) Chrome/126.0", "Accept": "text/html"}
BASE = "https://prsindia.org/mptrack/rajya-sabha/"
TITLE_RE = re.compile("tit" + "le>([^&<]+)")


def fetch(url: str, tries: int = 2) -> str:
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=25) as resp:
                return resp.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            print("  retry", url, e, flush=True)
            time.sleep(2 * (i + 1))
    return ""


def main() -> int:
    roster = json.loads((DATA / "_meta" / "rs_roster.json").read_text())["members"]
    prs_slugs = json.loads((DATA / "_meta" / "rs_prs_index.json").read_text())
    out_file = DATA / "_meta" / "rs_prs_activity.json"
    results = json.loads(out_file.read_text())
    fetcher = PRSFetcher.__new__(PRSFetcher)
    slug_alnum = {re.sub(r"[^a-z0-9]", "", s): s for s in prs_slugs}
    recovered = 0
    for m in roster:
        slug = m["slug"]
        if "parliament_activity" in results.get(slug, {}):
            continue
        toks = [t for t in re.findall(r"[a-z]{4,}", m["name"].lower())]
        cands = []
        for a, s in slug_alnum.items():
            score = sum(len(t) for t in toks if t in a)
            if score:
                cands.append((score, s))
        cands.sort(key=lambda t: -t[0])
        for score, s in cands[:3]:
            cf = CACHE / f"{s}.html"
            if cf.exists():
                html = cf.read_text(errors="replace")
            else:
                html = fetch(BASE + s)
                if html:
                    cf.write_text(html)
                time.sleep(0.5)
            if not html:
                continue
            tm = TITLE_RE.search(html)
            page_name = html_mod.unescape(tm.group(1)).replace("| PRSIndia", "").strip() if tm else ""
            if not (name_matches(m["name"], page_name) or name_matches(page_name, m["name"])):
                continue
            parsed = fetcher._parse_prs_html(html, BASE + s)
            if parsed is None:
                continue
            results[slug] = {
                "name": m["name"], "prs_slug": s, "prs_url": BASE + s,
                "page_title": page_name, "identity_ok": True,
                "parliament_activity": {
                    "attendance_percentage": parsed.attendance_percentage,
                    "questions_asked": parsed.questions_asked,
                    "debates_participated": parsed.debates_participated,
                    "private_bills_introduced": parsed.private_bills_introduced,
                    "is_minister": parsed.is_minister, "source": "prs_rs",
                },
            }
            recovered += 1
            print("recovered", m["name"], "->", s, flush=True)
            out_file.write_text(json.dumps(results, indent=1, ensure_ascii=False))
            break
    out_file.write_text(json.dumps(results, indent=1, ensure_ascii=False) + "\n")
    ok = sum(1 for v in results.values() if "parliament_activity" in v)
    print(f"recovered {recovered}; total with activity {ok}/244", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
