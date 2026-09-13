"""Watch registry and change detection for NetaGym Watch.

A user (Telegram chat id, or an email subscriber id) watches MPs. The
tracker data refreshes on a schedule; after each refresh we fingerprint
every watched MP's public record and diff against the last snapshot.
Any metric that moved becomes an alert line with the source link.

State lives in a small JSON dir (VOICE_STATE_DIR, default .state/).
On Render's free tier that disk is ephemeral - watches reset on redeploy.
That is an accepted, disclosed limit of this demo deployment, not hidden.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path

from .data_index import MPDataIndex, MPRecord

REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = Path(os.environ.get("VOICE_STATE_DIR", REPO_ROOT / ".state"))

# Metrics we fingerprint per MP. Label is the plain-English alert name.
TRACKED_FIELDS: list[tuple[str, str]] = [
    ("attendance_pct", "Parliament attendance"),
    ("questions_asked", "questions asked"),
    ("debates_participated", "debates joined"),
    ("criminal_cases", "declared criminal cases"),
    ("serious_criminal_cases", "serious criminal cases"),
    ("total_assets", "declared assets"),
    ("mplads_expended_cr", "MP fund spent"),
    ("mplads_utilization", "MP fund utilization"),
    ("composite_score", "transparency score"),
    ("national_rank", "national rank"),
]


def fingerprint(rec: MPRecord) -> dict:
    """The metrics snapshot we diff between refreshes."""
    return {name: getattr(rec, name) for name, _ in TRACKED_FIELDS}


def _fmt_value(name: str, value) -> str:
    if value is None:
        return "no data"
    if name == "total_assets":
        return f"{value / 1e7:.1f} crore rupees" if value >= 1e7 else f"{value:.0f} rupees"
    if name in ("mplads_expended_cr",):
        return f"{value:.1f} crore rupees"
    if name in ("attendance_pct", "mplads_utilization"):
        return f"{value:.0f}%"
    if name == "composite_score":
        return f"{value:.1f}"
    return str(value)


@dataclass
class Change:
    slug: str
    name: str
    diffs: list[tuple[str, object, object]] = field(default_factory=list)

    def lines(self) -> list[str]:
        labels = dict(TRACKED_FIELDS)
        return [
            f"- {labels.get(f, f)}: {_fmt_value(f, old)} -> {_fmt_value(f, new)}"
            for f, old, new in self.diffs
        ]


class WatchStore:
    """JSON-backed registry: chat_id -> set of MP slugs."""

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else STATE_DIR / "watches.json"
        self._lock = threading.Lock()
        self._data: dict[str, list[str]] = {}
        self._load()

    def _load(self) -> None:
        try:
            raw = json.loads(self.path.read_text())
            self._data = {str(k): sorted(set(v)) for k, v in raw.items()}
        except (OSError, json.JSONDecodeError, AttributeError):
            self._data = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=1, sort_keys=True))
        tmp.replace(self.path)

    def watch(self, chat_id: str, slug: str) -> bool:
        """Add a watch. Returns True if this is a new watch."""
        with self._lock:
            watches = self._data.setdefault(str(chat_id), [])
            if slug in watches:
                return False
            watches.append(slug)
            self._save()
            return True

    def unwatch(self, chat_id: str, slug: str) -> bool:
        with self._lock:
            watches = self._data.get(str(chat_id), [])
            if slug not in watches:
                return False
            watches.remove(slug)
            self._save()
            return True

    def watches(self, chat_id: str) -> list[str]:
        return list(self._data.get(str(chat_id), []))

    def watchers_of(self, slug: str) -> list[str]:
        return [cid for cid, slugs in self._data.items() if slug in slugs]

    def all_slugs(self) -> list[str]:
        out: set[str] = set()
        for slugs in self._data.values():
            out.update(slugs)
        return sorted(out)

    def subscriber_count(self) -> int:
        return len(self._data)


def load_snapshots(path: Path | str | None = None) -> dict:
    p = Path(path) if path else STATE_DIR / "snapshots.json"
    try:
        return json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def save_snapshots(snaps: dict, path: Path | str | None = None) -> None:
    p = Path(path) if path else STATE_DIR / "snapshots.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(snaps, indent=0, sort_keys=True))


def detect_changes(index: MPDataIndex, slugs: list[str], old: dict) -> tuple[list[Change], dict]:
    """Diff watched MPs' current fingerprints against stored snapshots.

    Returns (changes, new_snapshots). First-ever snapshot of an MP is not a
    change - it is the baseline.
    """
    by_slug = {r.slug: r for r in index.records}
    changes: list[Change] = []
    new_snaps = dict(old)
    for slug in slugs:
        rec = by_slug.get(slug)
        if rec is None:
            continue
        fp = fingerprint(rec)
        prev = old.get(slug)
        new_snaps[slug] = fp
        if prev is None:
            continue
        diffs = [(f, prev.get(f), fp.get(f))
                 for f, _ in TRACKED_FIELDS if prev.get(f) != fp.get(f)]
        if diffs:
            changes.append(Change(slug=slug, name=rec.name, diffs=diffs))
    return changes, new_snaps
