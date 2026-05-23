"""Digital Sansad API client — authoritative MP data (Grade A)."""

from __future__ import annotations

import re

from ..config import settings
from ..models.schemas import (
    MPProfile, House, EvidenceGrade, DataSource,
    CommitteeMembership, CommitteeEngagement,
    VoteRecord, LegislativeRecord,
)
from ..utils.logger import get_logger
from ..utils.name_match import normalize_state, name_matches
from .scraper import AsyncScraper

log = get_logger(__name__)


class SansadFetcher:
    """Fetches MP data from Digital Sansad API (sansad.in)."""

    def __init__(self, scraper: AsyncScraper) -> None:
        self.scraper = scraper
        self._ls_cache: list[dict] | None = None
        self._rs_cache: list[dict] | None = None

    async def fetch_all_ls_members(self) -> list[dict]:
        """Fetch all current (18th) Lok Sabha members from Digital Sansad API."""
        if self._ls_cache is not None:
            return self._ls_cache

        try:
            data = await self.scraper.fetch_json(settings.urls.sansad_ls_api)
            all_members: list[dict] = []
            if isinstance(data, list):
                all_members = data
            elif isinstance(data, dict):
                # API wraps members in "membersDtoList" (confirmed Mar 2026)
                all_members = data.get(
                    "membersDtoList",
                    data.get("members", data.get("data", data.get("results", []))),
                )
                if not isinstance(all_members, list):
                    all_members = []
            # API returns ALL members across all terms (5000+).
            # Filter to current 18th Lok Sabha sitting members only.
            self._ls_cache = [
                m for m in all_members
                if str(m.get("status", "")).strip().lower() == "sitting"
                and str(m.get("lastLoksabha", "")).strip() == "18"
            ]
            # Fallback: if filter is too strict (API schema change), accept all "Sitting"
            if not self._ls_cache and all_members:
                sitting = [m for m in all_members if str(m.get("status", "")).strip().lower() == "sitting"]
                if sitting:
                    self._ls_cache = sitting
                    log.info("Used status-only filter (%d sitting members)", len(sitting))
            log.info("Loaded %d current Lok Sabha members from Digital Sansad (of %d total)", len(self._ls_cache), len(all_members))
        except Exception as e:
            log.warning("Failed to fetch Lok Sabha members from Sansad API: %s", e)
            self._ls_cache = []

        return self._ls_cache

    async def fetch_all_rs_members(self) -> list[dict]:
        """Fetch all current Rajya Sabha members from Digital Sansad API."""
        if self._rs_cache is not None:
            return self._rs_cache

        try:
            data = await self.scraper.fetch_json(settings.urls.sansad_rs_api)
            all_members: list[dict] = []
            if isinstance(data, list):
                all_members = data
            elif isinstance(data, dict):
                # API wraps members in "membersDtoList" (confirmed Mar 2026)
                all_members = data.get(
                    "membersDtoList",
                    data.get("members", data.get("data", data.get("results", []))),
                )
                if not isinstance(all_members, list):
                    all_members = []
            # Filter to current sitting members only
            self._rs_cache = [
                m for m in all_members
                if str(m.get("status", "")).strip().lower() == "sitting"
            ]
            if not self._rs_cache and all_members:
                # Fallback if no status field
                self._rs_cache = all_members
            log.info("Loaded %d current Rajya Sabha members from Digital Sansad (of %d total)", len(self._rs_cache), len(all_members))
        except Exception as e:
            log.warning("Failed to fetch Rajya Sabha members from Sansad API: %s", e)
            self._rs_cache = []

        return self._rs_cache

    async def get_members_by_state(
        self, state: str, house: House = House.LOK_SABHA
    ) -> list[MPProfile]:
        """Get MPs for a state from the Sansad API.

        Args:
            state: State name (will be normalized).
            house: Which house to query.

        Returns:
            List of MPProfile objects with sansad_member_id, profile_url, canonical_name.
        """
        state_norm = normalize_state(state)

        if house == House.LOK_SABHA:
            members = await self.fetch_all_ls_members()
        else:
            members = await self.fetch_all_rs_members()

        mps: list[MPProfile] = []
        for member in members:
            member_state = self._extract_state(member)
            if normalize_state(member_state) != state_norm:
                continue

            mp = self._member_to_profile(member, state_norm, house)
            if mp:
                mps.append(mp)

        log.info(
            "Found %d %s members for %s from Digital Sansad",
            len(mps), house.value, state,
        )
        return mps

    def _extract_state(self, member: dict) -> str:
        """Extract state name from a Sansad API member record."""
        for key in ["stateName", "state_name", "state", "State"]:
            val = member.get(key, "")
            if val:
                return str(val).strip()  # API pads stateName with trailing spaces
        return ""

    def _member_to_profile(
        self, member: dict, state_norm: str, house: House
    ) -> MPProfile | None:
        """Convert a Sansad API member dict to an MPProfile."""
        # Extract name — API uses firstName/lastName or full name, with fallback to mpFirstLastName
        first = member.get("firstName", member.get("first_name", ""))
        last = member.get("lastName", member.get("last_name", ""))
        full_name = member.get("name", member.get("fullName", ""))
        # mpFirstLastName is a reliable fallback (e.g. "Shri  Chhotelal", "Shri Mohibbullah")
        mp_first_last = member.get("mpFirstLastName", "")

        if first and last:
            name = f"{first} {last}".strip()
        elif full_name:
            name = str(full_name).strip()
        elif mp_first_last:
            # Use mpFirstLastName, stripping title prefixes
            name = str(mp_first_last).strip()
        else:
            return None

        if not name:
            return None

        constituency = ""
        for key in ["constName", "constituency_name", "constituency", "Constituency"]:
            val = member.get(key, "")
            if val:
                constituency = str(val).strip()
                break

        party = ""
        for key in ["partyFname", "party_name", "party", "Party"]:
            val = member.get(key, "")
            if val:
                party = str(val).strip()
                break

        member_id = member.get("mpsno", member.get("member_id", member.get("id")))
        profile_url = member.get("profileUrl", member.get("profile_url", ""))

        return MPProfile(
            name=name,
            constituency=constituency or "Unknown",
            state=state_norm,
            party=party or "Unknown",
            house=house,
            sansad_member_id=int(member_id) if member_id else None,
            profile_url=str(profile_url) if profile_url else None,
            canonical_name=name,
        )

    async def lookup_member(self, mp: MPProfile) -> dict | None:
        """Look up a Sansad API member record by matching name.

        Searches the cached member list and returns the matching dict, or None.
        Also enriches the MPProfile with sansad_member_id and profile_url if found.
        """
        house = mp.house if mp.house else House.LOK_SABHA
        if house == House.LOK_SABHA:
            members = await self.fetch_all_ls_members()
        else:
            members = await self.fetch_all_rs_members()

        if not members:
            return None

        # Build full name for each member and match
        for member in members:
            first = member.get("firstName", member.get("first_name", ""))
            last = member.get("lastName", member.get("last_name", ""))
            full_name = member.get("name", member.get("fullName", ""))

            if first and last:
                candidate_name = f"{first} {last}".strip()
            elif full_name:
                candidate_name = str(full_name).strip()
            else:
                continue

            if name_matches(mp.name, candidate_name):
                member_id = member.get("mpsno", member.get("member_id", member.get("id")))
                profile_url = member.get("profileUrl", member.get("profile_url", ""))

                if member_id and not mp.sansad_member_id:
                    mp.sansad_member_id = int(member_id)
                if profile_url and not mp.profile_url:
                    mp.profile_url = str(profile_url)

                log.info("Sansad lookup matched %s → member_id=%s", mp.name, member_id)
                return member

        # Fallback: match by constituency within same state
        mp_state = normalize_state(mp.state)
        if mp.constituency:
            mp_const = mp.constituency.strip().lower()
            for member in members:
                for key in ["constName", "constituency_name", "constituency", "Constituency"]:
                    val = member.get(key, "")
                    if val and val.strip().lower() == mp_const:
                        member_state = self._extract_state(member)
                        if normalize_state(member_state) == mp_state:
                            member_id = member.get("mpsno", member.get("member_id", member.get("id")))
                            profile_url = member.get("profileUrl", member.get("profile_url", ""))
                            if member_id and not mp.sansad_member_id:
                                mp.sansad_member_id = int(member_id)
                            if profile_url and not mp.profile_url:
                                mp.profile_url = str(profile_url)
                            log.info("Sansad lookup (constituency) matched %s → member_id=%s", mp.name, member_id)
                            return member

        return None

    async def _ensure_member_id(self, mp: MPProfile) -> bool:
        """Ensure the MP has a sansad_member_id, looking it up if necessary.

        Returns True if an ID is available (existing or newly looked up).
        """
        if mp.sansad_member_id or mp.profile_url:
            return True
        member = await self.lookup_member(mp)
        return member is not None and (mp.sansad_member_id is not None or mp.profile_url is not None)

    async def fetch_committees(self, mp: MPProfile) -> CommitteeEngagement:
        """Fetch committee memberships for an MP from their Sansad profile page."""
        # Auto-lookup member if no ID or profile URL
        if not mp.sansad_member_id and not mp.profile_url:
            await self._ensure_member_id(mp)

        if not mp.sansad_member_id and not mp.profile_url:
            log.debug("No Sansad member ID or profile URL for %s, skipping committees", mp.name)
            return CommitteeEngagement(confidence=0.0)

        # Try profile page scrape
        url = mp.profile_url or f"https://sansad.in/ls/members/{mp.sansad_member_id}"
        try:
            html = await self.scraper.fetch(url)
        except Exception as e:
            log.warning("Failed to fetch Sansad profile for %s: %s", mp.name, e)
            return CommitteeEngagement(confidence=0.0)

        return self._parse_committees(html, url)

    def _parse_committees(self, html: str, url: str) -> CommitteeEngagement:
        """Parse committee memberships from Sansad profile HTML."""
        memberships: list[CommitteeMembership] = []
        leadership_count = 0

        source = DataSource(
            url=url,
            source_name="sansad",
            grade=EvidenceGrade.A,
            notes="Digital Sansad MP profile",
        )

        # Look for committee section patterns in the HTML
        # Pattern: committee names in list items or table rows
        committee_patterns = [
            # "Standing Committee on X" / "Joint Committee on X"
            re.compile(r"((?:Standing|Joint|Select|Consultative)\s+Committee\s+on\s+[^<\n]+)", re.IGNORECASE),
            # "Committee on X"
            re.compile(r"(Committee\s+on\s+[^<\n]{5,80})", re.IGNORECASE),
        ]

        seen_names: set[str] = set()
        for pattern in committee_patterns:
            for match in pattern.finditer(html):
                name = match.group(1).strip()
                # Clean HTML tags if any
                name = re.sub(r"<[^>]+>", "", name).strip()
                if not name or len(name) < 5 or name.lower() in seen_names:
                    continue
                seen_names.add(name.lower())

                # Determine role
                role = "member"
                context = html[max(0, match.start() - 100):match.end() + 100].lower()
                if "chairperson" in context or "chairman" in context:
                    role = "chairperson"
                    leadership_count += 1
                elif "vice-chairperson" in context or "vice chairman" in context:
                    role = "vice-chairperson"
                    leadership_count += 1

                # Determine type
                ctype = ""
                name_lower = name.lower()
                if "standing" in name_lower:
                    ctype = "standing"
                elif "joint" in name_lower:
                    ctype = "joint"
                elif "select" in name_lower:
                    ctype = "select"
                elif "consultative" in name_lower:
                    ctype = "consultative"

                memberships.append(CommitteeMembership(
                    committee_name=name,
                    role=role,
                    committee_type=ctype,
                    source=source,
                ))

        confidence = 0.7 if memberships else 0.3
        return CommitteeEngagement(
            memberships=memberships,
            total_committees=len(memberships),
            leadership_roles=leadership_count,
            confidence=confidence,
            sources=[source] if memberships else [],
        )

    async def fetch_voting_record(self, mp: MPProfile) -> list[VoteRecord]:
        """Fetch division voting record for an MP from Sansad."""
        if not mp.sansad_member_id:
            await self._ensure_member_id(mp)
        if not mp.sansad_member_id:
            return []

        # Try the division votes page
        url = f"https://sansad.in/ls/division-votes"
        try:
            html = await self.scraper.fetch(url)
        except Exception as e:
            log.warning("Failed to fetch voting record for %s: %s", mp.name, e)
            return []

        return self._parse_voting_record(html, mp, url)

    def _parse_voting_record(self, html: str, mp: MPProfile, url: str) -> list[VoteRecord]:
        """Parse voting record from Sansad division votes page."""
        records: list[VoteRecord] = []
        source = DataSource(
            url=url,
            source_name="sansad",
            grade=EvidenceGrade.A,
            notes="Sansad division votes",
        )

        # Look for division vote entries mentioning the MP
        mp_name_lower = mp.name.lower()
        # Pattern: bill name, date, and vote status in table rows
        bill_pattern = re.compile(
            r"<tr[^>]*>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>([\d/\-]+)</td>.*?</tr>",
            re.DOTALL | re.IGNORECASE,
        )
        for match in bill_pattern.finditer(html):
            bill_name = re.sub(r"<[^>]+>", "", match.group(1)).strip()
            date = match.group(2).strip()
            if bill_name and date:
                records.append(VoteRecord(
                    bill_name=bill_name,
                    date=date,
                    vote="unknown",
                    source=source,
                ))

        return records[:20]  # Cap at 20 most recent

    async def fetch_legislative_record(self, mp: MPProfile) -> LegislativeRecord:
        """Fetch legislative effectiveness data from Sansad (zero hour, special mentions)."""
        # Auto-lookup member if no ID
        if not mp.sansad_member_id:
            await self._ensure_member_id(mp)
        if not mp.sansad_member_id:
            log.debug("No Sansad member ID for %s, skipping legislative record", mp.name)
            return LegislativeRecord(confidence=0.0)

        source = DataSource(
            url=f"https://sansad.in/ls/members/{mp.sansad_member_id}",
            source_name="sansad",
            grade=EvidenceGrade.A,
            notes="Digital Sansad legislative record",
        )

        try:
            url = f"https://sansad.in/ls/members/{mp.sansad_member_id}"
            html = await self.scraper.fetch(url)
        except Exception as e:
            log.warning("Failed to fetch legislative record for %s: %s", mp.name, e)
            return LegislativeRecord(confidence=0.0)

        return self._parse_legislative_record(html, source)

    def _parse_legislative_record(self, html: str, source: DataSource) -> LegislativeRecord:
        """Parse legislative effectiveness data from Sansad profile."""
        zero_hour = 0
        special_mentions = 0
        bills_introduced = 0

        # Zero Hour mentions
        zh_match = re.search(r"Zero\s+Hour.*?(\d+)", html, re.IGNORECASE | re.DOTALL)
        if zh_match:
            zero_hour = int(zh_match.group(1))

        # Special Mentions / Rule 377
        sm_match = re.search(r"Special\s+Mention.*?(\d+)", html, re.IGNORECASE | re.DOTALL)
        if not sm_match:
            sm_match = re.search(r"Rule\s+377.*?(\d+)", html, re.IGNORECASE | re.DOTALL)
        if sm_match:
            special_mentions = int(sm_match.group(1))

        # Bills introduced
        bill_match = re.search(r"(?:Private\s+Member\s+)?Bills?\s+Introduced.*?(\d+)", html, re.IGNORECASE | re.DOTALL)
        if bill_match:
            bills_introduced = int(bill_match.group(1))

        has_data = zero_hour > 0 or special_mentions > 0 or bills_introduced > 0
        return LegislativeRecord(
            bills_introduced=bills_introduced,
            zero_hour_mentions=zero_hour,
            special_mentions=special_mentions,
            confidence=0.7 if has_data else 0.3,
            sources=[source],
        )
