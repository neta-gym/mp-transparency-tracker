"""Social media presence checker — tracks MP public accessibility."""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..models.schemas import (
    MPProfile,
    SocialMediaProfile,
    PublicAccessibility,
    DataSource,
    EvidenceGrade,
)
from ..utils.logger import get_logger
from .scraper import AsyncScraper

log = get_logger(__name__)


def _load_known_handles() -> dict[str, dict[str, str]]:
    """Load social media handles from external JSON config."""
    handles_path = Path(__file__).parent.parent / "data" / "social_handles.json"
    if handles_path.exists():
        try:
            with open(handles_path) as f:
                return json.load(f)
        except Exception as e:
            log.warning("Failed to load social_handles.json: %s", e)
    return {}


_KNOWN_HANDLES: dict[str, dict[str, str]] = _load_known_handles()


class SocialMediaFetcher:
    """Fetches social media presence for MPs."""

    def __init__(self, scraper: AsyncScraper) -> None:
        self.scraper = scraper

    async def fetch_social_media(self, mp: MPProfile) -> PublicAccessibility:
        """Fetch social media profiles for an MP."""
        profiles: list[SocialMediaProfile] = []
        total_followers = 0

        # Check known handles first
        known = _KNOWN_HANDLES.get(mp.name.lower(), {})

        for platform, handle in known.items():
            profile = SocialMediaProfile(
                platform=platform,
                handle=handle,
                url=self._build_url(platform, handle),
                verified=True,  # Known handles are verified
                active=True,  # Assume active
            )
            profiles.append(profile)

        # If no known handles, try to discover from MP profile page
        if not profiles and mp.profile_url:
            profiles = await self._discover_from_profile(mp)

        total_followers = sum(p.followers or 0 for p in profiles)
        confidence = 0.7 if profiles else 0.2

        source = DataSource(
            source_name="social_media_lookup",
            grade=EvidenceGrade.D,
            notes="Social media handle lookup",
        )

        return PublicAccessibility(
            profiles=profiles,
            total_platforms=len(profiles),
            total_followers=total_followers,
            confidence=confidence,
            sources=[source] if profiles else [],
        )

    async def _discover_from_profile(self, mp: MPProfile) -> list[SocialMediaProfile]:
        """Try to discover social media links from the MP's official profile page."""
        if not mp.profile_url:
            return []

        try:
            html = await self.scraper.fetch(mp.profile_url)
        except Exception:
            return []

        profiles: list[SocialMediaProfile] = []
        platform_patterns = {
            "twitter": re.compile(r"https?://(?:www\.)?(?:twitter\.com|x\.com)/([A-Za-z0-9_]+)", re.IGNORECASE),
            "facebook": re.compile(r"https?://(?:www\.)?facebook\.com/([A-Za-z0-9_.]+)", re.IGNORECASE),
            "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/([A-Za-z0-9_.]+)", re.IGNORECASE),
            "youtube": re.compile(r"https?://(?:www\.)?youtube\.com/(?:@|channel/|user/)([A-Za-z0-9_-]+)", re.IGNORECASE),
        }

        for platform, pattern in platform_patterns.items():
            match = pattern.search(html)
            if match:
                handle = match.group(1)
                profiles.append(SocialMediaProfile(
                    platform=platform,
                    handle=handle,
                    url=match.group(0),
                    active=True,
                ))

        return profiles

    @staticmethod
    def _build_url(platform: str, handle: str) -> str:
        """Build a URL from platform and handle."""
        urls = {
            "twitter": f"https://x.com/{handle}",
            "facebook": f"https://facebook.com/{handle}",
            "instagram": f"https://instagram.com/{handle}",
            "youtube": f"https://youtube.com/@{handle}",
        }
        return urls.get(platform, "")
