"""Slim in-memory index over the tracker's per-MP public-record JSON files.

Loads data/<state>/raw/<slug>.json (skipping *_validated.json duplicates)
once, then answers lookups by MP name, alias, or constituency. All data is
the same public-record JSON the published scores and dashboard use.
"""

from __future__ import annotations

import difflib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from voice.transliterate import DEVANAGARI_RE, to_latin

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9 ]", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


@dataclass
class MPRecord:
    name: str
    slug: str
    state: str
    constituency: str
    party: str
    house: str
    photo_url: str | None
    aliases: list[str] = field(default_factory=list)
    attendance_pct: float | None = None
    questions_asked: int | None = None
    debates_participated: int | None = None
    criminal_cases: int | None = None
    serious_criminal_cases: int | None = None
    total_assets: float | None = None  # rupees
    mplads_entitled_cr: float | None = None  # crore
    mplads_expended_cr: float | None = None  # crore
    mplads_utilization: float | None = None  # percent
    composite_score: float | None = None
    national_rank: int | None = None
    sources: list[str] = field(default_factory=list)

    @property
    def state_label(self) -> str:
        return self.state.replace("-", " ").title()


class MPDataIndex:
    """Lookup layer over per-MP public records."""

    def __init__(self, data_dir: Path | str = DATA_DIR):
        self.data_dir = Path(data_dir)
        self.records: list[MPRecord] = []
        self._by_norm: dict[str, MPRecord] = {}
        self._by_constituency: dict[str, MPRecord] = {}
        self._load()

    def _load(self) -> None:
        for path in sorted(self.data_dir.glob("*/raw/*.json")):
            if path.stem.endswith("_validated"):
                continue
            try:
                raw = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            rec = self._to_record(raw, path.parent.parent.name)
            if rec is None:
                continue
            self.records.append(rec)
            for key in {rec.name, rec.name.split("(")[0].strip(), *rec.aliases}:
                n = _norm(key)
                if n and n not in self._by_norm:
                    self._by_norm[n] = rec
            cn = _norm(rec.constituency)
            if cn and cn not in self._by_constituency:
                self._by_constituency[cn] = rec
        self._attach_ranks()

    @staticmethod
    def _to_record(raw: dict, state: str) -> MPRecord | None:
        mp = raw.get("mp") or {}
        name = mp.get("canonical_name") or mp.get("name")
        if not name:
            return None
        pa = raw.get("parliament_activity") or {}
        cr = raw.get("criminal_record") or {}
        assets = raw.get("assets") or {}
        mplads = raw.get("mplads") or {}
        return MPRecord(
            name=name,
            slug=mp.get("slug") or _norm(name).replace(" ", "-"),
            state=(mp.get("state") or state).lower(),
            constituency=mp.get("constituency") or "",
            party=mp.get("party") or "Unknown",
            house=mp.get("house") or "",
            photo_url=mp.get("photo_url"),
            aliases=[a for a in (mp.get("name_aliases") or []) if isinstance(a, str)],
            attendance_pct=pa.get("attendance_percentage"),
            questions_asked=pa.get("questions_asked"),
            debates_participated=pa.get("debates_participated"),
            criminal_cases=cr.get("total_cases"),
            serious_criminal_cases=cr.get("serious_cases"),
            total_assets=assets.get("total_assets"),
            mplads_entitled_cr=mplads.get("entitled"),
            mplads_expended_cr=mplads.get("expended"),
            mplads_utilization=mplads.get("utilization_rate"),
            sources=raw.get("sources_consulted") or [],
        )

    def _attach_ranks(self) -> None:
        lb_path = self.data_dir / "national" / "leaderboard" / "latest.json"
        if not lb_path.exists():
            return
        try:
            lb = json.loads(lb_path.read_text())
        except (json.JSONDecodeError, OSError):
            return
        scores: dict[str, tuple[float, int]] = {}
        for e in lb.get("entries", []):
            n = _norm(e.get("mp_name", ""))
            if n:
                scores[n] = (e.get("composite_score", e.get("score", 0.0)), e.get("rank", 0))
        # latest.json may only carry top_n entries; fall back to per-state score files
        for rec in self.records:
            hit = scores.get(_norm(rec.name))
            if hit:
                rec.composite_score, rec.national_rank = hit
        for path in sorted(self.data_dir.glob("*/scores/*.json")):
            try:
                sc = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            n = _norm((sc.get("mp") or {}).get("name", ""))
            if not n:
                continue
            rec = self._by_norm.get(n)
            if rec and rec.composite_score is None:
                rec.composite_score = sc.get("composite_score")

    # -- queries -----------------------------------------------------------

    def find(self, query: str) -> MPRecord | None:
        """Best-effort MP match by name, alias, or constituency."""
        # Hindi speech arrives in Devanagari; the index is Latin-script, and
        # _norm drops non-ASCII, so transliterate before normalizing.
        if DEVANAGARI_RE.search(query):
            query = to_latin(query)
        n = _norm(query)
        if not n:
            return None
        if n in self._by_norm:
            return self._by_norm[n]
        if n in self._by_constituency:
            return self._by_constituency[n]
        # substring over names, preferring the shortest matching name
        sub = [r for key, r in self._by_norm.items() if n in key or key in n]
        if sub:
            return min(sub, key=lambda r: len(r.name))
        close = difflib.get_close_matches(n, self._by_norm.keys(), n=1, cutoff=0.75)
        if close:
            return self._by_norm[close[0]]
        close = difflib.get_close_matches(n, self._by_constituency.keys(), n=1, cutoff=0.8)
        if close:
            return self._by_constituency[close[0]]
        return None

    def state_leaders(self, state: str, limit: int = 3) -> list[MPRecord]:
        n = _norm(state).replace(" ", "-")
        recs = [r for r in self.records if r.state == n and r.composite_score is not None]
        return sorted(recs, key=lambda r: r.composite_score or 0, reverse=True)[:limit]

    def state_laggards(self, state: str, limit: int = 3) -> list[MPRecord]:
        n = _norm(state).replace(" ", "-")
        recs = [r for r in self.records if r.state == n and r.composite_score is not None]
        return sorted(recs, key=lambda r: r.composite_score or 0)[:limit]

    def stats(self) -> dict:
        return {
            "mps_indexed": len(self.records),
            "states": len({r.state for r in self.records}),
            "with_scores": sum(1 for r in self.records if r.composite_score is not None),
        }
