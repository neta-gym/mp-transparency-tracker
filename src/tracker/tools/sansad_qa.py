"""Sansad Q&A Annexure Parser — cross-verification of MPLADS data via Parliament Q&A.

Parliament Q&A annexures contain official MPLADS fund tables (state-wise, sometimes
year-wise). These are Grade A data for cross-verifying eSAKSHI/data.gov.in figures.
"""

from __future__ import annotations

import re
from typing import Optional

from ..config import settings
from ..models.schemas import DataSource, EvidenceGrade
from ..utils.logger import get_logger
from ..utils.name_match import normalize_state
from .scraper import AsyncScraper

log = get_logger(__name__)


class SansadQAParser:
    """Parses MPLADS-related Parliament Q&A annexures for cross-verification.

    Searches for MPLADS questions in Sansad Q&A, downloads PDF annexures,
    and extracts state-level fund tables for verification against primary sources.
    """

    def __init__(self, scraper: AsyncScraper) -> None:
        self.scraper = scraper
        self._cached_data: dict[str, dict] | None = None

    async def search_mplads_questions(self) -> list[dict]:
        """Search Sansad Q&A for MPLADS-related questions.

        Returns list of question metadata (question_id, title, date, annexure_urls).
        """
        log.info("Sansad Q&A: Searching for MPLADS questions")
        results = []

        try:
            # Search the Sansad Q&A portal
            search_url = f"{settings.urls.sansad_qa_search}?query=MPLADS+fund+utilization&type=starred"
            text = await self.scraper.fetch(search_url)

            # Try to parse as JSON (API response)
            import json
            try:
                data = json.loads(text)
                items = data if isinstance(data, list) else data.get("results", [])
                for item in items:
                    results.append({
                        "question_id": item.get("question_id", ""),
                        "title": item.get("title", "") or item.get("subject", ""),
                        "date": item.get("date", ""),
                        "annexure_url": item.get("annexure_url", ""),
                        "ministry": item.get("ministry", ""),
                    })
            except (json.JSONDecodeError, ValueError):
                # HTML response — parse for question links
                results = self._parse_search_html(text)

        except Exception as e:
            log.warning("Sansad Q&A search failed: %s", e)

        log.info("Sansad Q&A: Found %d MPLADS questions", len(results))
        return results

    async def fetch_annexure(self, url: str) -> Optional[str]:
        """Download a Q&A annexure and extract text.

        Supports PDF (via pdfplumber) and HTML annexures.
        """
        if not url:
            return None

        try:
            if url.lower().endswith(".pdf"):
                return await self._extract_pdf_text(url)
            else:
                text = await self.scraper.fetch(url)
                return self._strip_html(text)
        except Exception as e:
            log.warning("Sansad Q&A: Failed to fetch annexure %s: %s", url, e)
            return None

    def parse_mplads_table(self, text: str, state: str) -> Optional[dict]:
        """Extract MPLADS fund figures for a state from annexure text.

        Tries regex patterns first, then heuristic fallback for complex tables.

        Returns dict with: entitled, released, expended, fiscal_year, source
        """
        if not text:
            return None

        normalized = normalize_state(state)

        # Try regex patterns for common table formats
        result = self._regex_parse(text, normalized)
        if result:
            return result

        return None

    def _regex_parse(self, text: str, state: str) -> Optional[dict]:
        """Try to extract state-level MPLADS figures using regex patterns."""
        # Pattern 1: "State | Entitled | Released | Expended" table
        # Looking for the state name followed by numeric columns
        state_pattern = re.escape(state.title())

        # Try various common table patterns
        patterns = [
            # Pattern: Delhi    500.00    400.00    350.00
            rf"(?i){state_pattern}\s+(\d[\d,.]+)\s+(\d[\d,.]+)\s+(\d[\d,.]+)",
            # Pattern: NCT of Delhi | 500.00 | 400.00 | 350.00
            rf"(?i)(?:NCT\s+of\s+)?{state_pattern}\s*\|\s*(\d[\d,.]+)\s*\|\s*(\d[\d,.]+)\s*\|\s*(\d[\d,.]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    vals = [float(v.replace(",", "")) for v in match.groups()]
                    return {
                        "entitled": vals[0] if len(vals) > 0 else None,
                        "released": vals[1] if len(vals) > 1 else None,
                        "expended": vals[2] if len(vals) > 2 else None,
                        "source": DataSource(
                            url=settings.urls.sansad_qa_search,
                            source_name="sansad_qa",
                            grade=EvidenceGrade.A,
                            notes="Extracted from Parliament Q&A annexure",
                        ),
                    }
                except (ValueError, IndexError):
                    continue

        return None

    async def _extract_pdf_text(self, url: str) -> Optional[str]:
        """Download PDF and extract text using pdfplumber."""
        try:
            import pdfplumber
            import io

            # Download PDF bytes
            content = await self.scraper.fetch(url)
            if isinstance(content, str):
                content = content.encode("utf-8", errors="replace")

            with pdfplumber.open(io.BytesIO(content)) as pdf:
                text_parts = []
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                return "\n".join(text_parts)

        except ImportError:
            log.warning("pdfplumber not installed — cannot parse PDF annexures")
            return None
        except Exception as e:
            log.warning("PDF extraction failed for %s: %s", url, e)
            return None

    def _strip_html(self, html: str) -> str:
        """Strip HTML tags to get plain text."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            return soup.get_text(separator="\n", strip=True)
        except Exception:
            return re.sub(r"<[^>]+>", " ", html)

    def _parse_search_html(self, html: str) -> list[dict]:
        """Parse Sansad Q&A search results from HTML."""
        results = []
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            for item in soup.find_all("div", class_=re.compile(r"question|result", re.I)):
                title_el = item.find(["h3", "h4", "a"])
                title = title_el.get_text(strip=True) if title_el else ""
                link = title_el.get("href", "") if title_el and title_el.name == "a" else ""

                if "mplads" in title.lower() or "mplad" in title.lower():
                    results.append({
                        "question_id": "",
                        "title": title,
                        "date": "",
                        "annexure_url": link,
                        "ministry": "MoSPI",
                    })
        except Exception:
            pass

        return results
