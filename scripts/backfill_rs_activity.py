#!/usr/bin/env python3
"""Backfill PRS parliament activity for Rajya Sabha members.

Crawl the PRS RS index, match slugs to the sansad RS roster, fetch each
member page, parse with PRSFetcher._parse_prs_html, verify the page title
matches the roster name. Output: data/_meta/rs_prs_activity.json keyed by
roster slug. Resumable via data/_meta/rs_prs_cache/.

Usage: PYTHONPATH=src python scripts/backfill_rs_activity.py
"""
from __future__ import annotations

import difflib
import html as html_mod
import json
import re
import time
import urllib.request
from pathlib import Path

from tracker.tools.prs import PRSFetcher
from tracker.utils.name_match import name_matches

DATA = Path(__file__).resolve().parent.parent / "data"
CACHE = DATA / "_meta" / "rs_prs_cache"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh) Chrome/126.0", "Accept": "text/html"}
INDEX = "https://prsindia.org/mptrack/rajya-sabha?page={n}"
BASE = "https://prsindia.org/mptrack/rajya-sabha/"
TITLE_RE = re.compile("tit" + "le>([^&<]+)")  # avoid literal tag in source


def fetch(url: str, tries: int = 3) -> str:
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            print(f"  retry {i+1} {url}: {e}", flush=True)
            time.sleep(3 * (i + 1))
    return ""


def alnum(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def crawl_index() -> list[str]:
    slugs: list[str] = []
    seen: set[str] = set()
    stale = 0
    for page in range(0, 80):
        html = fetch(INDEX.format(n=page))
        links = sorted(set(re.findall(r"/mptrack/rajya-sabha/([a-z0-9-]+)", html)))
        links = [s for s in links if s != "profile"]
        new = [s for s in links if s not in seen]
        seen.update(new)
        slugs.extend(new)
        stale = 0 if new else stale + 1
        print(f"index page {page}: {len(links)} links, {len(new)} new (total {len(slugs)})", flush=True)
        if stale >= 4:
            break
        time.sleep(0.5)
    return slugs


def match_slug(name: str, prs_slugs: list[str]) -> str | None:
    target = alnum(name)
    candidates = {alnum(s): s for s in prs_slugs}
    if target in candidates:
        return candidates[target]
    hits = [s for a, s in candidates.items() if target and (a.startswith(target) or target.startswith(a))]
    if len(hits) == 1:
        return hits[0]
    close = difflib.get_close_matches(target, list(candidates), n=1, cutoff=0.78)
    if close:
        return candidates[close[0]]
    return None


def main() -> int:
    CACHE.mkdir(parents=True, exist_ok=True)
    roster = json.loads((DATA / "_meta" / "rs_roster.json").read_text())["members"]

    idx_file = DATA / "_meta" / "rs_prs_index.json"
    if idx_file.exists():
        prs_slugs = json.loads(idx_file.read_text())
    else:
        prs_slugs = crawl_index()
        idx_file.write_text(json.dumps(prs_slugs, indent=0))
    print(f"{len(prs_slugs)} PRS RS slugs", flush=True)

    fetcher = PRSFetcher.__new__(PRSFetcher)
    out_file = DATA / "_meta" / "rs_prs_activity.json"
    results: dict[str, dict] = json.loads(out_file.read_text()) if out_file.exists() else {}

    done = ok = 0
    for i, m in enumerate(roster):
        slug = m["slug"]
        if slug in results and "error" not in results[slug]:
            done += 1
            ok += 1
            continue
        prs_slug = match_slug(m["name"], prs_slugs)
        if not prs_slug:
            results[slug] = {"name": m["name"], "error": "no_prs_slug_match"}
            continue
        cache_file = CACHE / f"{prs_slug}.html"
        if cache_file.exists():
            html = cache_file.read_text(errors="replace")
        else:
            html = fetch(BASE + prs_slug)
            if html:
                cache_file.write_text(html)
            time.sleep(0.6)
        if not html:
            results[slug] = {"name": m["name"], "prs_slug": prs_slug, "error": "fetch_failed"}
            continue
        tm = TITLE_RE.search(html)
        page_name = html_mod.unescape(tm.group(1)).replace("| PRSIndia", "").strip() if tm else ""
        ident_ok = name_matches(m["name"], page_name) or name_matches(page_name, m["name"])
        parsed = fetcher._parse_prs_html(html, BASE + prs_slug)
        entry: dict = {
            "name": m["name"],
            "prs_slug": prs_slug,
            "prs_url": BASE + prs_slug,
            "page_title": page_name,
            "identity_ok": bool(ident_ok),
        }
        if parsed is not None:
            entry["parliament_activity"] = {
                "attendance_percentage": parsed.attendance_percentage,
                "questions_asked": parsed.questions_asked,
                "debates_participated": parsed.debates_participated,
                "private_bills_introduced": parsed.private_bills_introduced,
                "is_minister": parsed.is_minister,
                "source": "prs_rs",
            }
        else:
            entry["error"] = "no_chart_data"
        results[slug] = entry
        done += 1
        ok += 1 if "parliament_activity" in entry else 0
        if done % 20 == 0:
            out_file.write_text(json.dumps(results, indent=1, ensure_ascii=False))
            print(f"progress {done}/{len(roster)} ok={ok}", flush=True)

    out_file.write_text(json.dumps(results, indent=1, ensure_ascii=False) + "\n")
    errs = {s: e for s, e in results.items() if "error" in e}
    bad_ident = [s for s, e in results.items() if not e.get("identity_ok", True)]
    print(f"DONE {ok}/{len(roster)} with activity; {len(errs)} errors; {len(bad_ident)} identity-mismatch", flush=True)
    for s in list(errs)[:15]:
        print("  err", s, errs[s].get("error"), errs[s].get("name"), flush=True)
    for s in bad_ident[:15]:
        print("  ident?", s, results[s].get("name"), "->", results[s].get("page_title"), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
