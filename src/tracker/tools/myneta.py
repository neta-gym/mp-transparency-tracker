"""MyNeta HTML parser — criminal records and asset declarations."""

from __future__ import annotations

import re
from typing import Optional

from bs4 import BeautifulSoup, Tag

from ..config import settings
from ..models.schemas import (
    CriminalCase, CriminalRecord, AssetDeclaration,
    DataSource, EvidenceGrade,
)
from ..utils.logger import get_logger
from .scraper import AsyncScraper

log = get_logger(__name__)

# IPC sections / keywords indicative of FIR/police station metadata (not actual sections)
_FIR_NOISE_PATTERN = re.compile(
    r"(FIR\s*No|PS\.|Police\s+Station|P\.S\.|Thana|Date\s*:)",
    re.IGNORECASE,
)


def _parse_amount(text: str) -> Optional[float]:
    """Parse Indian number format like '1,23,45,678' or 'Rs 1.5 Crore' to float."""
    if not text:
        return None
    text = text.strip().replace("~", "").replace("Rs", "").replace("INR", "").strip()

    crore_match = re.search(r"([\d,.]+)\s*Crore", text, re.IGNORECASE)
    lakh_match = re.search(r"([\d,.]+)\s*(?:Lakh|Lakhs|Lac|Lacs)", text, re.IGNORECASE)

    if crore_match:
        num = float(crore_match.group(1).replace(",", ""))
        return num * 1_00_00_000
    if lakh_match:
        num = float(lakh_match.group(1).replace(",", ""))
        return num * 1_00_000

    cleaned = re.sub(r"[^\d.]", "", text)
    if cleaned:
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _is_serious_case(sections: list[str], description: str) -> bool:
    """Heuristic: is this a serious criminal case?"""
    serious_sections = {
        "302", "304", "307", "376", "395", "396", "397", "399",
        "420", "467", "468", "471", "477", "120B",
        "13(1)", "13(2)",  # Prevention of Corruption Act
    }
    combined = " ".join(sections) + " " + description
    for s in serious_sections:
        if s in combined:
            return True
    keywords = ["murder", "attempt to murder", "rape", "kidnap", "corruption", "fraud"]
    for kw in keywords:
        if kw.lower() in combined.lower():
            return True
    return False


def _infer_case_status(text: str) -> str:
    """Infer case status from text content."""
    t = text.lower()
    if "convicted" in t or "conviction" in t:
        return "convicted"
    if "acquitted" in t or "acquittal" in t:
        return "acquitted"
    if "disposed" in t or "discharged" in t or "quashed" in t or "closed" in t:
        return "disposed"
    if "pending" in t or "ongoing" in t or "trial" in t:
        return "pending"
    return "unknown"


def _clean_ipc_sections(sections_text: str) -> list[str]:
    """Parse IPC sections, filtering out FIR/police station noise."""
    raw_parts = [s.strip() for s in re.split(r"[,;]", sections_text) if s.strip()]
    clean = []
    for part in raw_parts:
        if _FIR_NOISE_PATTERN.search(part):
            continue
        # Skip if it's purely a number that doesn't look like an IPC section
        if re.match(r"^\d{5,}$", part.strip()):
            continue
        clean.append(part)
    return clean


class MyNetaParser:
    """Fetches and parses MyNeta candidate pages."""

    def __init__(self, scraper: AsyncScraper) -> None:
        self.scraper = scraper

    async def fetch_candidate(self, candidate_id: int) -> tuple[CriminalRecord, AssetDeclaration, dict]:
        """Fetch and parse a MyNeta candidate page. Returns criminal record + assets + profile extras."""
        url = settings.urls.myneta_candidate.format(candidate_id=candidate_id)
        try:
            html = await self.scraper.fetch(url)
            return self._parse(html)
        except Exception as e:
            log.error("Failed to fetch MyNeta candidate %d: %s", candidate_id, e)
            return CriminalRecord(confidence=0.0), AssetDeclaration(confidence=0.0), {}

    def _parse(self, html: str) -> tuple[CriminalRecord, AssetDeclaration, dict]:
        """Parse MyNeta candidate page HTML."""
        soup = BeautifulSoup(html, "lxml")
        criminal = self._parse_criminal(soup)
        assets = self._parse_assets(soup)
        profile_extras = self._parse_profile_extras(soup)

        # Extract income and election expenditure into assets
        if profile_extras.get("annual_income") is not None:
            assets.annual_income = profile_extras["annual_income"]
        if profile_extras.get("election_expenditure") is not None:
            assets.election_expenditure = profile_extras["election_expenditure"]

        return criminal, assets, profile_extras

    def _parse_criminal(self, soup: BeautifulSoup) -> CriminalRecord:
        """Extract criminal case information with pending/disposed breakdown."""
        cases: list[CriminalCase] = []
        serious_count = 0
        conviction_count = 0
        pending_count = 0
        disposed_count = 0

        # Look for criminal cases section
        criminal_section = None
        for tag in soup.find_all(["h2", "h3", "h4", "b", "strong"]):
            if "criminal" in tag.get_text(strip=True).lower():
                criminal_section = tag
                break

        if criminal_section:
            sibling = criminal_section.find_next("table")
            if sibling:
                rows = sibling.find_all("tr")
                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) >= 2:
                        desc = cells[-1].get_text(strip=True) if cells else ""
                        sections_text = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                        ipc_sections = _clean_ipc_sections(sections_text)

                        # Combine all cell text for status inference
                        full_row_text = " ".join(c.get_text(strip=True) for c in cells)
                        status = _infer_case_status(full_row_text)

                        is_serious = _is_serious_case(ipc_sections, desc)
                        is_convicted = status == "convicted"

                        if is_serious:
                            serious_count += 1
                        if is_convicted:
                            conviction_count += 1
                        if status == "pending" or status == "unknown":
                            pending_count += 1
                        if status == "disposed" or status == "acquitted":
                            disposed_count += 1

                        case = CriminalCase(
                            description=desc,
                            ipc_sections=ipc_sections,
                            is_serious=is_serious,
                            is_convicted=is_convicted,
                            status=status,
                        )
                        cases.append(case)

        # Also look for summary text
        total = len(cases)
        page_text = soup.get_text()
        case_match = re.search(r"(\d+)\s+criminal\s+cases?", page_text, re.IGNORECASE)
        if case_match:
            total = max(total, int(case_match.group(1)))

        # Check for "no criminal cases"
        if re.search(r"no\s+criminal\s+cases?", page_text, re.IGNORECASE):
            total = 0
            cases = []
            serious_count = 0
            conviction_count = 0
            pending_count = 0
            disposed_count = 0

        # If no status was inferrable, count all as pending
        if cases and pending_count == 0 and disposed_count == 0 and conviction_count == 0:
            pending_count = len(cases)

        source = DataSource(
            url=settings.urls.myneta_candidate.format(candidate_id="?"),
            source_name="myneta",
            grade=EvidenceGrade.B,
            notes="MyNeta candidate affidavit data",
        )

        return CriminalRecord(
            total_cases=total,
            serious_cases=serious_count,
            convictions=conviction_count,
            pending_cases=pending_count,
            disposed_cases=disposed_count,
            cases=cases,
            confidence=0.8 if total > 0 or cases else 0.7,
            sources=[source],
        )

    def _parse_assets(self, soup: BeautifulSoup) -> AssetDeclaration:
        """Extract asset and liability information, including previous election data."""
        movable = None
        immovable = None
        total = None
        liabilities = None
        previous_total = None

        # Get page text with &nbsp; normalized to spaces
        page_text = soup.get_text()
        page_text = page_text.replace("\xa0", " ")  # Replace &nbsp; with regular spaces

        # Strategy 1: Parse summary line — MyNeta format: "Assets: Rs 32,81,62,601"
        # Real pages have "Assets: Rs X" (with colon) in a summary section.
        # Fixture format has "Total Assets Rs X" (no colon but with "Total" prefix).
        # MUST NOT match "Movable Assets" or "Immovable Assets".
        summary_patterns = [
            # "Total Assets Rs X" or "Total Assets: Rs X" (explicit "Total" prefix)
            (r"Total\s+Assets?\s*[:=]?\s*Rs\.?\s*([\d,.\s]+)", "total"),
            # "Assets: Rs X" — colon REQUIRED to disambiguate from "Movable AssetsRs"
            (r"Assets?\s*:\s*Rs\.?\s*([\d,.\s]+)", "total"),
            # "Liabilities: Rs X" or "LiabilitiesRs X"
            (r"Liabilit(?:y|ies)\s*[:=]?\s*Rs\.?\s*([\d,.\s]+)", "liabilities"),
        ]
        for pattern, field in summary_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                val = _parse_amount(match.group(1))
                if val is not None and val > 0:
                    if field == "total" and total is None:
                        total = val
                    elif field == "liabilities" and liabilities is None:
                        liabilities = val

        # Strategy 2: Parse labeled values with more patterns
        detail_patterns = [
            (r"Movable\s+Assets?\s*[:=]?\s*Rs\.?\s*([\d,.\s]+(?:Crore|Lacs?h?)?)", "movable"),
            (r"Immovable\s+Assets?\s*[:=]?\s*Rs\.?\s*([\d,.\s]+(?:Crore|Lacs?h?)?)", "immovable"),
            (r"Total\s+Assets?\s*[:=]?\s*Rs\.?\s*([\d,.\s]+(?:Crore|Lacs?h?)?)", "total"),
            (r"Liabilit(?:y|ies)\s*[:=]?\s*Rs\.?\s*([\d,.\s]+(?:Crore|Lacs?h?)?)", "liabilities"),
        ]
        for pattern, field in detail_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                val = _parse_amount(match.group(1))
                if val is not None and val > 0:
                    if field == "movable" and movable is None:
                        movable = val
                    elif field == "immovable" and immovable is None:
                        immovable = val
                    elif field == "total" and total is None:
                        total = val
                    elif field == "liabilities" and liabilities is None:
                        liabilities = val

        # Strategy 3: Parse from HTML tables with anchor tags (movabletotal, etc.)
        for anchor_name, field in [("movabletotal", "movable"), ("immovabletotal", "immovable")]:
            anchor = soup.find("a", attrs={"name": anchor_name})
            if anchor:
                # The total value is in the last <td> of this row, inside a green/colored <b> tag
                row = anchor.find_parent("tr")
                if row:
                    bold_tags = row.find_all("b")
                    for b in bold_tags:
                        text = b.get_text(strip=True).replace("\xa0", " ")
                        val = _parse_amount(text)
                        if val is not None and val > 0:
                            if field == "movable" and movable is None:
                                movable = val
                            elif field == "immovable" and immovable is None:
                                immovable = val
                            break

        # Strategy 4: Parse grand total from liabilities table
        liab_table = soup.find("table", id="liabilities")
        if liab_table:
            for row in liab_table.find_all("tr"):
                label = row.get_text(strip=True).lower().replace("\xa0", " ")
                if "grand total" in label:
                    bold_tags = row.find_all("b")
                    for b in bold_tags:
                        text = b.get_text(strip=True).replace("\xa0", " ")
                        val = _parse_amount(text)
                        if val is not None and val > 0 and liabilities is None:
                            liabilities = val
                            break

        # Strategy 5: Parse from financial tables with current/previous columns
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            # Check if the table has a header row with "previous" or prior election year
            header_cells = rows[0].find_all(["td", "th"]) if rows else []
            header_text = " ".join(c.get_text(strip=True).lower().replace("\xa0", " ") for c in header_cells)
            has_previous_col = "previous" in header_text or re.search(r"20[01]\d", header_text)

            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    label = cells[0].get_text(strip=True).lower().replace("\xa0", " ")
                    value_text = cells[-1].get_text(strip=True).replace("\xa0", " ")

                    if "total" in label and ("value" in label or "asset" in label):
                        val = _parse_amount(value_text)
                        if val and val > 0:
                            if "movable" in label and movable is None:
                                movable = val
                            elif "immovable" in label and immovable is None:
                                immovable = val
                    elif "grand total" in label and "liabilit" in label:
                        val = _parse_amount(value_text)
                        if val and val > 0 and liabilities is None:
                            liabilities = val

                    # MyNeta tables often have columns: Label | Current | Previous
                    if len(cells) >= 3 and has_previous_col:
                        prev_text = cells[-2].get_text(strip=True).replace("\xa0", " ") if len(cells) == 3 else cells[1].get_text(strip=True).replace("\xa0", " ")
                        if "total" in label and "asset" in label and previous_total is None:
                            previous_total = _parse_amount(prev_text)

        # Fallback: look for explicit "previous election" asset text
        if previous_total is None:
            prev_match = re.search(
                r"(?:previous|last)\s+(?:election|affidavit).*?(?:total\s+)?assets?\s*[:=]?\s*Rs\.?\s*([\d,.\s]+(?:Crore|Lacs?h?)?)",
                page_text, re.IGNORECASE,
            )
            if prev_match:
                previous_total = _parse_amount(prev_match.group(1))

        if total is None and movable is not None and immovable is not None:
            total = movable + immovable

        net_worth = None
        if total is not None and liabilities is not None:
            net_worth = total - liabilities

        confidence = 0.8 if total is not None else 0.5 if (movable is not None or immovable is not None) else 0.3

        source = DataSource(
            url=settings.urls.myneta_candidate.format(candidate_id="?"),
            source_name="myneta",
            grade=EvidenceGrade.B,
            notes="MyNeta candidate affidavit data",
        )

        return AssetDeclaration(
            movable_assets=movable,
            immovable_assets=immovable,
            total_assets=total,
            liabilities=liabilities,
            net_worth=net_worth,
            previous_total_assets=previous_total,
            source="myneta",
            confidence=confidence,
            sources=[source],
        )

    def _parse_profile_extras(self, soup: BeautifulSoup) -> dict:
        """Extract education, profession, age, income, and election expenditure."""
        extras: dict = {}

        # Photo URL
        img = soup.find("img", class_="profile")
        if not img:
            img = soup.find("img", attrs={"alt": re.compile(r"profile", re.I)})
        if img and img.get("src"):
            src = img["src"]
            if not src.startswith("http"):
                src = f"https://myneta.info/{src.lstrip('/')}"
            extras["photo_url"] = src

        page_text = soup.get_text().replace("\xa0", " ")

        # Strategy 1: Extract from tables first (more reliable than regex on full text)
        for table in soup.find_all("table"):
            for row in table.find_all("tr"):
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    label = cells[0].get_text(strip=True).lower().replace("\xa0", " ")
                    value_text = cells[-1].get_text(strip=True).replace("\xa0", " ")

                    if "education" in label and "education" not in extras:
                        if value_text and value_text.lower() not in ("n/a", "na", "not given", ""):
                            extras["education"] = value_text
                    elif "profession" in label and "profession" not in extras:
                        if value_text and value_text.lower() not in ("n/a", "na", "not given", ""):
                            extras["profession"] = value_text
                    elif "age" in label and "age" not in extras:
                        try:
                            age_val = int(re.search(r"\d+", value_text).group())
                            if 18 <= age_val <= 120:
                                extras["age"] = age_val
                        except (AttributeError, ValueError):
                            pass

        # Strategy 2: Regex on page text (fallback)
        # Education — MyNeta format: "Educational Details\nCategory: Post Graduate\nDegree from University"
        if "education" not in extras:
            # Try "Category: X" pattern first (MyNeta specific)
            cat_match = re.search(
                r"Educational\s+Details.*?Category\s*[:=]?\s*([^\n]{3,80})",
                page_text, re.IGNORECASE | re.DOTALL,
            )
            if cat_match:
                edu = cat_match.group(1).strip().rstrip(".")
                if edu and edu.lower() not in ("n/a", "na", "not given", ""):
                    extras["education"] = edu
            else:
                # Generic "Education: X" pattern (with word boundary to avoid matching "Educational")
                edu_match = re.search(
                    r"\bEducation\b\s*[:=]\s*([A-Za-z][^\n]{2,80})",
                    page_text, re.IGNORECASE,
                )
                if edu_match:
                    edu = edu_match.group(1).strip().rstrip(".")
                    if edu and edu.lower() not in ("n/a", "na", "not given", ""):
                        extras["education"] = edu

        # Profession
        if "profession" not in extras:
            prof_match = re.search(
                r"\bProfession\b\s*[:=]?\s*([A-Za-z][^\n]{2,120})",
                page_text, re.IGNORECASE,
            )
            if prof_match:
                prof = prof_match.group(1).strip().rstrip(".")
                if prof and prof.lower() not in ("n/a", "na", "not given", ""):
                    extras["profession"] = prof

        # Age (fallback regex)
        if "age" not in extras:
            age_match = re.search(r"Age\s*[:=]?\s*(\d{1,3})", page_text, re.IGNORECASE)
            if age_match:
                age_val = int(age_match.group(1))
                if 18 <= age_val <= 120:
                    extras["age"] = age_val

        # Annual / Total Income
        income_match = re.search(
            r"(?:Total\s+)?Income\s*[:=]?\s*Rs\.?\s*([\d,.\s]+(?:Crore|Lacs?h?)?)",
            page_text, re.IGNORECASE,
        )
        if income_match:
            extras["annual_income"] = _parse_amount(income_match.group(1))

        # Election Expenditure — look in tables and text
        exp_match = re.search(
            r"(?:Election\s+)?Expenditure\s*[:=]?\s*Rs\.?\s*([\d,.\s]+(?:Crore|Lacs?h?)?)",
            page_text, re.IGNORECASE,
        )
        if exp_match:
            extras["election_expenditure"] = _parse_amount(exp_match.group(1))

        return extras
