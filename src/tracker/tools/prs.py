"""PRS India parliament activity fetcher — two-tier: CSV bulk + website scrape."""

from __future__ import annotations

import csv
import io
import re

from ..config import settings
from ..models.schemas import MPProfile, ParliamentActivity, DataSource, EvidenceGrade
from ..utils.logger import get_logger
from ..utils.name_match import normalize_state, name_matches
from .scraper import AsyncScraper

log = get_logger(__name__)

# Title prefixes to strip when building PRS slugs
_SLUG_TITLE_RE = re.compile(
    r"^(shri|smt|dr|mr|mrs|ms|prof|adv|capt|col|gen|justice|hon|sri|shrimati|kumari)\b\.?\s*",
    re.IGNORECASE,
)


class PRSFetcher:
    """Fetches parliament activity data from PRS India.

    Tier 1: GitHub CSV (~543 MPs, one HTTP request, cached).
    Tier 2: PRS website scrape per-MP (Google Charts JS parsing).
    """

    def __init__(self, scraper: AsyncScraper) -> None:
        self.scraper = scraper
        self._csv_rows: list[dict] | None = None

    # --- Public API (unchanged) ---

    async def fetch_activity(self, mp: MPProfile) -> ParliamentActivity:
        """Fetch parliament activity for a specific MP.

        1. Try CSV lookup (fast, cached)
        2. CSV miss → scrape PRS website page
        3. Both fail → return ParliamentActivity(confidence=0.0)
        """
        # Tier 1: CSV
        rows = await self._load_csv_data()
        result = self._find_in_csv(mp, rows)
        if result is not None:
            return result

        # Tier 2: PRS website scrape
        result = await self._scrape_prs_page(mp)
        if result is not None:
            return result

        log.warning("MP not found in PRS data (CSV + website): %s (%s)", mp.name, mp.constituency)
        return ParliamentActivity(confidence=0.0)

    # --- Tier 1: CSV ---

    async def _load_csv_data(self) -> list[dict]:
        """Load and cache the PRS GitHub CSV dataset."""
        if self._csv_rows is not None:
            return self._csv_rows

        try:
            text = await self.scraper.fetch(settings.urls.prs_github_csv)
            # Auto-detect delimiter: the PRS CSV uses semicolons
            delimiter = ";"
            if text and ";" not in text[:500] and "," in text[:500]:
                delimiter = ","
            reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
            self._csv_rows = list(reader)
            # Sanity check: if we got 0-1 columns, likely wrong delimiter
            if self._csv_rows and len(self._csv_rows[0]) <= 2:
                log.warning("PRS CSV parsed with few columns (%d), retrying with alt delimiter", len(self._csv_rows[0]))
                alt = "," if delimiter == ";" else ";"
                reader = csv.DictReader(io.StringIO(text), delimiter=alt)
                self._csv_rows = list(reader)
        except Exception as e:
            log.error("Failed to load PRS CSV data: %s", e)
            self._csv_rows = []

        log.info("Loaded %d members from PRS CSV", len(self._csv_rows))
        return self._csv_rows

    def _find_in_csv(self, mp: MPProfile, rows: list[dict]) -> ParliamentActivity | None:
        """Search CSV rows by name variants, constituency, then fuzzy matching."""
        mp_state = normalize_state(mp.state)

        # Build name variants
        name_variants = [mp.name]
        if mp.canonical_name and mp.canonical_name != mp.name:
            name_variants.append(mp.canonical_name)
        name_variants.extend(mp.name_aliases)

        # Pass 1: Match by name (token overlap)
        for row in rows:
            r_name = row.get("Name", "")
            for variant in name_variants:
                if name_matches(variant, r_name):
                    return self._parse_csv_row(row)

        # Pass 2: Match by constituency within same state
        if mp.constituency:
            mp_const = mp.constituency.strip().lower()
            for row in rows:
                r_state = normalize_state(row.get("State", ""))
                r_constituency = row.get("Constituency", "").strip().lower()
                if r_state == mp_state and (mp_const in r_constituency or r_constituency in mp_const):
                    return self._parse_csv_row(row)

        # Pass 3: Fuzzy match by last name + state
        mp_last_name = mp.name.split()[-1].lower() if mp.name.split() else ""
        if mp_last_name and len(mp_last_name) >= 3:
            candidates = []
            for row in rows:
                r_state = normalize_state(row.get("State", ""))
                if r_state != mp_state:
                    continue
                r_name = row.get("Name", "")
                r_last = r_name.split()[-1].lower() if r_name.split() else ""
                # Check if last names match within edit distance 2
                if r_last and self._similar_names(mp_last_name, r_last):
                    candidates.append(row)

            if len(candidates) == 1:
                # Unique match by last name in same state — accept
                log.info("PRS fuzzy match: %s → %s", mp.name, candidates[0].get("Name", ""))
                return self._parse_csv_row(candidates[0])

        return None

    @staticmethod
    def _similar_names(a: str, b: str) -> bool:
        """Check if two name strings are similar (within edit distance 2)."""
        if a == b:
            return True
        if abs(len(a) - len(b)) > 2:
            return False
        # Simple Levenshtein-like check: allow up to 2 character differences
        # Using a simplified approach that counts mismatches
        if len(a) != len(b):
            # Pad shorter string for comparison
            shorter, longer = (a, b) if len(a) < len(b) else (b, a)
            # Check if shorter is a substring starting from similar position
            if shorter in longer:
                return True
            # Check character overlap ratio
            common = sum(1 for c in shorter if c in longer)
            return common >= len(shorter) - 1
        else:
            diffs = sum(1 for ca, cb in zip(a, b) if ca != cb)
            return diffs <= 2

    def _parse_csv_row(self, row: dict) -> ParliamentActivity:
        """Parse a PRS CSV row into ParliamentActivity."""
        attendance = None
        att_val = row.get("Attendance", "")
        if att_val and att_val.strip().lower() != "minister":
            try:
                attendance = float(str(att_val).replace("%", "").strip())
            except (ValueError, TypeError):
                pass

        is_minister = (row.get("Minister", "").strip().lower() == "yes"
                       or row.get("Attendance", "").strip().lower() == "minister")

        questions = 0
        try:
            questions = int(row.get("Questions", 0))
        except (ValueError, TypeError):
            pass

        debates = 0
        try:
            debates = int(row.get("Debates", 0))
        except (ValueError, TypeError):
            pass

        bills = 0
        try:
            bills = int(row.get("Private Member Bills", 0))
        except (ValueError, TypeError):
            pass

        return ParliamentActivity(
            attendance_percentage=attendance,
            questions_asked=questions,
            debates_participated=debates,
            private_bills_introduced=bills,
            is_minister=is_minister,
            source="prs",
            confidence=0.8 if attendance is not None else 0.3,
            sources=[DataSource(
                url=settings.urls.prs_github_csv,
                source_name="prs_github_csv",
                grade=EvidenceGrade.C,
                notes="PRS India GitHub CSV - 18th Lok Sabha",
            )],
        )

    # --- Tier 2: PRS Website Scrape ---

    @staticmethod
    def _build_prs_slug(mp: MPProfile) -> str:
        """Build a PRS mptrack URL slug from MP name.

        e.g. "Dr. Harsh Vardhan" → "harsh-vardhan"
             "Manoj Tiwari" → "manoj-tiwari"
        """
        name = mp.canonical_name if mp.canonical_name else mp.name
        slug = name.strip().lower()
        # Strip title prefixes (may appear multiple times)
        for _ in range(3):
            slug = _SLUG_TITLE_RE.sub("", slug).strip()
        # Replace non-alphanumeric with hyphens
        slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
        return slug

    async def _scrape_prs_page(self, mp: MPProfile) -> ParliamentActivity | None:
        """Fetch and parse an individual PRS MP track page."""
        slug = self._build_prs_slug(mp)
        url = f"{settings.urls.prs_mptrack_base}/{slug}"
        try:
            html = await self.scraper.fetch(url)
        except Exception as e:
            log.debug("PRS page fetch failed for %s (%s): %s", mp.name, url, e)
            return None
        return self._parse_prs_html(html, url)

    def _parse_prs_html(self, html: str, url: str) -> ParliamentActivity | None:
        """Extract data from Google Charts JS functions embedded in PRS HTML.

        Chart mapping:
          drawChartw0 → Attendance %
          drawChartw1 → Debates count
          drawChartw2 → Questions count
          drawChartw3 → Private Member Bills count
        """
        attendance = self._extract_chart_value(html, "drawChartw0")
        debates_raw = self._extract_chart_value(html, "drawChartw1")
        questions_raw = self._extract_chart_value(html, "drawChartw2")
        bills_raw = self._extract_chart_value(html, "drawChartw3")

        if attendance is None and debates_raw is None and questions_raw is None:
            log.debug("No chart data found in PRS HTML for %s", url)
            return None

        debates = int(debates_raw) if debates_raw is not None else 0
        questions = int(questions_raw) if questions_raw is not None else 0
        bills = int(bills_raw) if bills_raw is not None else 0
        is_minister = bool(re.search(r'\bminister\b', html, re.IGNORECASE))

        # Phase 3: Extract focus areas and notable questions
        focus_topics = self._extract_focus_topics(html)
        notable_questions = self._extract_notable_questions(html)

        return ParliamentActivity(
            attendance_percentage=attendance,
            questions_asked=questions,
            debates_participated=debates,
            private_bills_introduced=bills,
            is_minister=is_minister,
            source="prs",
            confidence=0.9 if attendance is not None else 0.5,
            sources=[DataSource(
                url=url,
                source_name="prs_website",
                grade=EvidenceGrade.B,
                notes="PRS India MP Track page - 18th Lok Sabha",
            )],
            focus_topics=focus_topics,
            notable_questions=notable_questions,
        )

    @staticmethod
    def _extract_focus_topics(html: str) -> list[str]:
        """Extract topic tags/focus areas from PRS MP page content."""
        topics: list[str] = []
        seen: set[str] = set()

        # PRS pages sometimes have topic headings or keywords
        # Look for common parliamentary topic patterns
        topic_patterns = [
            r"(?:focus|topic|subject|area)[s]?\s*[:=]\s*([^<\n]+)",
            r"<(?:h[3-5]|strong|b)[^>]*>((?:Water|Health|Education|Infrastructure|Defence|"
            r"Agriculture|Finance|Commerce|Housing|Environment|Labour|Energy|Transport|"
            r"Rural|Urban|Women|Science|Technology|IT|Telecom|Railways)[^<]*)</(?:h[3-5]|strong|b)>",
        ]

        for pattern in topic_patterns:
            for match in re.finditer(pattern, html, re.IGNORECASE):
                topic = re.sub(r"<[^>]+>", "", match.group(1)).strip()
                if topic and topic.lower() not in seen and len(topic) < 80:
                    seen.add(topic.lower())
                    topics.append(topic)

        return topics[:10]  # Cap at 10

    @staticmethod
    def _extract_notable_questions(html: str) -> list[str]:
        """Extract notable question titles from PRS page."""
        questions: list[str] = []

        # Look for question titles in the page
        q_pattern = re.compile(
            r"(?:question|starred|unstarred)[^<]*?[:]\s*([^<\n]{10,150})",
            re.IGNORECASE,
        )
        for match in q_pattern.finditer(html):
            q_text = match.group(1).strip()
            if q_text and len(q_text) > 10:
                questions.append(q_text)

        return questions[:5]  # Cap at 5

    @staticmethod
    def _extract_chart_value(html: str, function_name: str) -> float | None:
        """Extract the MP's value (first data row) from a Google Charts drawChart function.

        Pattern: arrayToDataTable([["","",{header}],["",VALUE,"#8562a4"],...])
        The MP's value is tagged with purple color "#8562a4".
        """
        pattern = rf'function\s+{re.escape(function_name)}\s*\(\)\s*\{{.*?arrayToDataTable\(\[(.*?)\]\)'
        match = re.search(pattern, html, re.DOTALL)
        if not match:
            return None

        data_str = match.group(1)

        # Extract numeric values from data rows: ["",<number>,"#color"]
        values = re.findall(r'\[""\s*,\s*([\d.]+)\s*,', data_str)
        if values:
            try:
                return float(values[0])
            except (ValueError, TypeError):
                return None
        return None
