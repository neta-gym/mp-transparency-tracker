"""Social media presence checker — tracks MP public accessibility."""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..models.schemas import (
    DataSource,
    EvidenceGrade,
    MPProfile,
    PublicAccessibility,
    SocialMediaProfile,
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
                loaded = json.load(f)
                return loaded if isinstance(loaded, dict) else {}
        except Exception as e:
            log.warning("Failed to load social_handles.json: %s", e)
    return {}


_KNOWN_HANDLES: dict[str, dict[str, str]] = _load_known_handles()


class SocialMediaFetcher:
    """Fetches social media presence for MPs."""

    def __init__(self, scraper: AsyncScraper) -> None:
        self.scraper = scraper

    async def fetch_social_media(self, mp: MPProfile) -> PublicAccessibility:
        """Fetch social media profiles for an MP.

        Priority:
        1. Known handles from social_handles.json
        2. Sansad API member data (facebook, twitter, instagram fields)
        3. Profile page discovery (regex scraping)
        """
        profiles: list[SocialMediaProfile] = []

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

        # Always try Sansad API member data (has social media fields)
        if mp.sansad_member_id:
            sansad_profiles = await self._fetch_from_sansad_api(mp)
            if sansad_profiles:
                # Merge with known handles (known handles take precedence)
                existing_platforms = {p.platform for p in profiles}
                for sp in sansad_profiles:
                    if sp.platform not in existing_platforms:
                        profiles.append(sp)
                        existing_platforms.add(sp.platform)

        # If still no profiles, try to discover from MyNeta candidate page
        if not profiles and mp.myneta_candidate_id:
            profiles = await self._discover_from_myneta(mp)

        # Last resort: try to discover from MP profile page
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

    async def _fetch_from_sansad_api(self, mp: MPProfile) -> list[SocialMediaProfile]:
        """Fetch social media handles from the Sansad API member record."""
        if not mp.sansad_member_id:
            return []

        profiles: list[SocialMediaProfile] = []
        try:
            url = f"https://sansad.in/api_ls/member/{mp.sansad_member_id}"
            data = await self.scraper.fetch_json(url)
            if not isinstance(data, dict):
                return []

            for platform in ("twitter", "facebook", "instagram"):
                handle = data.get(platform, "")
                if handle and handle.strip() and handle.strip() not in ("", "NA", "N/A", "None"):
                    handle = handle.strip()
                    profiles.append(
                        SocialMediaProfile(
                            platform=platform,
                            handle=handle,
                            url=self._build_url(platform, handle),
                            verified=False,
                            active=True,
                        )
                    )
        except Exception as e:
            log.debug("Sansad API social media fetch failed for %s: %s", mp.name, e)

        return profiles

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
            "youtube": re.compile(
                r"https?://(?:www\.)?youtube\.com/(?:@|channel/|user/)([A-Za-z0-9_-]+)", re.IGNORECASE
            ),
        }

        for platform, pattern in platform_patterns.items():
            match = pattern.search(html)
            if match:
                handle = match.group(1)
                profiles.append(
                    SocialMediaProfile(
                        platform=platform,
                        handle=handle,
                        url=match.group(0),
                        active=True,
                    )
                )

        return profiles

    async def _discover_from_myneta(self, mp: MPProfile) -> list[SocialMediaProfile]:
        """Try to discover social media links from the MyNeta candidate page."""
        if not mp.myneta_candidate_id:
            return []

        try:
            from ..config import settings

            url = settings.urls.myneta_candidate.format(candidate_id=mp.myneta_candidate_id)
            html = await self.scraper.fetch(url)
        except Exception:
            return []

        profiles: list[SocialMediaProfile] = []
        platform_patterns = {
            "twitter": re.compile(r"https?://(?:www\.)?(?:twitter\.com|x\.com)/([A-Za-z0-9_]+)", re.IGNORECASE),
            "facebook": re.compile(r"https?://(?:www\.)?facebook\.com/([A-Za-z0-9_.]+)", re.IGNORECASE),
            "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/([A-Za-z0-9_.]+)", re.IGNORECASE),
            "youtube": re.compile(
                r"https?://(?:www\.)?youtube\.com/(?:@|channel/|user/)([A-Za-z0-9_-]+)", re.IGNORECASE
            ),
        }

        seen_platforms: set[str] = set()
        for platform, pattern in platform_patterns.items():
            match = pattern.search(html)
            if match and platform not in seen_platforms:
                handle = match.group(1)
                profiles.append(
                    SocialMediaProfile(
                        platform=platform,
                        handle=handle,
                        url=match.group(0),
                        verified=False,
                        active=True,
                    )
                )
                seen_platforms.add(platform)

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
