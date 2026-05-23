"""Conflict of Interest detection — cross-references MP business interests with committee/question activity."""

from __future__ import annotations

import re

from ..models.schemas import (
    ConflictOfInterest,
    CommitteeEngagement,
)
from ..utils.logger import get_logger

log = get_logger(__name__)

# Sector mappings: keywords in profession/business → sector label
_BUSINESS_SECTOR_MAP: dict[str, list[str]] = {
    "mining": ["mining", "mineral", "quarry", "ore"],
    "real_estate": ["real estate", "property", "construction", "builder", "developer", "housing"],
    "agriculture": ["agriculture", "farming", "plantation", "agri"],
    "healthcare": ["hospital", "pharma", "medical", "health", "drug"],
    "education": ["school", "college", "university", "education", "coaching", "institute"],
    "finance": ["bank", "finance", "nbfc", "lending", "insurance", "investment"],
    "energy": ["oil", "gas", "petroleum", "energy", "power", "solar", "coal"],
    "telecom": ["telecom", "communication", "mobile", "network"],
    "media": ["media", "news", "broadcast", "publication", "film", "entertainment"],
    "transport": ["transport", "logistics", "shipping", "airline", "railway"],
    "technology": ["tech", "software", "it ", "digital", "computer", "cyber"],
    "manufacturing": ["manufacturing", "factory", "industrial", "steel", "cement", "textile"],
    "legal": ["law", "legal", "advocate", "lawyer", "attorney"],
}

# Committee name → sector mapping
_COMMITTEE_SECTOR_MAP: dict[str, list[str]] = {
    "mining": ["coal", "mines", "mining", "mineral"],
    "real_estate": ["urban development", "housing", "real estate"],
    "agriculture": ["agriculture", "rural", "food", "farmer"],
    "healthcare": ["health", "family welfare", "medical", "pharma"],
    "education": ["education", "human resource", "hrd"],
    "finance": ["finance", "banking", "commerce", "corporate affairs"],
    "energy": ["energy", "petroleum", "power", "coal", "atomic"],
    "telecom": ["communication", "telecom", "information technology", "it"],
    "media": ["information", "broadcasting"],
    "transport": ["transport", "railways", "shipping", "civil aviation"],
    "technology": ["science", "technology", "information technology"],
    "defence": ["defence", "external affairs", "security"],
}


def _classify_sectors(text: str, sector_map: dict[str, list[str]]) -> list[str]:
    """Classify text into sectors using keyword matching."""
    text_lower = text.lower()
    sectors = set()
    for sector, keywords in sector_map.items():
        for kw in keywords:
            if kw in text_lower:
                sectors.add(sector)
                break
    return sorted(sectors)


def detect_conflicts(
    profession: str | None,
    businesses: list[str] | None,
    committees: CommitteeEngagement,
    focus_topics: list[str] | None,
) -> ConflictOfInterest:
    """Detect potential conflicts of interest between MP's business and parliamentary roles.

    This is a heuristic analysis — overlaps may represent domain expertise
    rather than conflicts. A nuanced assessment can be applied later.
    """
    # Classify MP's business sectors
    business_text = " ".join(filter(None, [profession] + (businesses or [])))
    if not business_text.strip():
        return ConflictOfInterest(confidence=0.0)

    mp_sectors = _classify_sectors(business_text, _BUSINESS_SECTOR_MAP)
    if not mp_sectors:
        return ConflictOfInterest(
            mp_businesses=[business_text],
            severity="none",
            confidence=0.3,
        )

    # Classify committee sectors
    committee_text = " ".join(m.committee_name for m in committees.memberships) if committees.memberships else ""
    committee_sectors = _classify_sectors(committee_text, _COMMITTEE_SECTOR_MAP)

    # Classify question/focus topic sectors
    topic_text = " ".join(focus_topics) if focus_topics else ""
    question_sectors = _classify_sectors(topic_text, _COMMITTEE_SECTOR_MAP)

    # Find overlaps
    overlaps = []
    mp_set = set(mp_sectors)

    for sector in mp_set & set(committee_sectors):
        matching_committees = [
            m.committee_name for m in committees.memberships
            if sector in _classify_sectors(m.committee_name, _COMMITTEE_SECTOR_MAP)
        ]
        overlaps.append(
            f"Business in {sector} sector + sits on {', '.join(matching_committees)}"
        )

    for sector in mp_set & set(question_sectors):
        overlaps.append(
            f"Business in {sector} sector + asks questions on {sector}-related topics"
        )

    # Determine severity
    if not overlaps:
        severity = "none"
    elif len(overlaps) == 1:
        severity = "low"
    elif len(overlaps) <= 3:
        severity = "medium"
    else:
        severity = "high"

    return ConflictOfInterest(
        mp_businesses=[business_text] if business_text else [],
        committee_sectors=committee_sectors,
        question_sectors=question_sectors,
        overlaps=overlaps,
        severity=severity,
        confidence=0.5 if overlaps else 0.3,
    )
