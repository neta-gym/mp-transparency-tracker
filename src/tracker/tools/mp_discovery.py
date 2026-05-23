"""Auto-discover MPs per state — Sansad-first cascade with MyNeta enrichment."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..config import settings, MYNETA_STATE_IDS
from ..models.schemas import MPProfile, House
from ..utils.logger import get_logger
from ..utils.name_match import normalize_state, name_matches
from .scraper import AsyncScraper
from .sansad import SansadFetcher

log = get_logger(__name__)


class MPDiscovery:
    """Discovers MPs for a given state.

    Cascade: Digital Sansad (A) -> MyNeta constituency page (B) -> Seed data (fallback).
    """

    def __init__(self, scraper: AsyncScraper, sansad: SansadFetcher) -> None:
        self.scraper = scraper
        self.sansad = sansad

    async def discover(self, state: str, include_rs: bool = False) -> list[MPProfile]:
        """Discover all MPs for a state.

        Args:
            state: State name (normalized internally).
            include_rs: If True, also discover Rajya Sabha MPs.

        Returns:
            List of MPProfile objects.
        """
        state_norm = normalize_state(state)
        log.info("[bold magenta]Discovering MPs for state:[/bold magenta] %s", state)

        # Try Digital Sansad first (Grade A)
        ls_mps = await self.sansad.get_members_by_state(state_norm, House.LOK_SABHA)
        if ls_mps:
            log.info("Found %d LS MPs from Digital Sansad for %s", len(ls_mps), state)
            # Enrich with MyNeta candidate IDs
            await self._enrich_myneta_ids(ls_mps, state_norm)
        else:
            # Fallback to MyNeta winners page
            log.info("Sansad API returned no results, trying MyNeta for %s", state)
            ls_mps = await self._from_myneta(state_norm)
            if ls_mps:
                log.info("Found %d MPs from MyNeta for %s", len(ls_mps), state)

        all_mps = list(ls_mps)

        # Optionally add Rajya Sabha members
        if include_rs:
            rs_mps = await self.sansad.get_members_by_state(state_norm, House.RAJYA_SABHA)
            if rs_mps:
                log.info("Found %d RS MPs from Digital Sansad for %s", len(rs_mps), state)
                all_mps.extend(rs_mps)

        if not all_mps:
            log.error("Could not discover MPs for state: %s", state)

        return all_mps

    async def _enrich_myneta_ids(self, mps: list[MPProfile], state_norm: str) -> None:
        """Try to find MyNeta candidate IDs for MPs via constituency page scraping."""
        state_id = MYNETA_STATE_IDS.get(state_norm)
        if not state_id:
            log.info("No MyNeta state ID mapping for %s, skipping enrichment", state_norm)
            return

        try:
            url = settings.urls.myneta_state_constituencies.format(state_id=state_id)
            html = await self.scraper.fetch(url)
            soup = BeautifulSoup(html, "lxml")

            # Build map of candidate links from MyNeta
            myneta_candidates: list[dict] = []
            for link in soup.find_all("a", href=re.compile(r"candidate\.php\?candidate_id=\d+")):
                href = link.get("href", "")
                cid_match = re.search(r"candidate_id=(\d+)", href)
                if cid_match:
                    candidate_name = link.get_text(strip=True)
                    candidate_id = int(cid_match.group(1))
                    # Try to get constituency from surrounding context
                    parent_row = link.find_parent("tr")
                    constituency = ""
                    if parent_row:
                        cells = parent_row.find_all("td")
                        for cell in cells:
                            if cell.find("a", href=re.compile(r"candidate\.php")) is None:
                                ct = cell.get_text(strip=True)
                                if ct and len(ct) > 2 and not ct.isdigit():
                                    constituency = ct
                                    break

                    myneta_candidates.append({
                        "name": candidate_name,
                        "id": candidate_id,
                        "constituency": constituency,
                    })

            # Match MPs to MyNeta candidates
            for mp in mps:
                if mp.myneta_candidate_id:
                    continue
                for mc in myneta_candidates:
                    if name_matches(mp.name, mc["name"]):
                        mp.myneta_candidate_id = mc["id"]
                        if not mp.name_aliases and mc["name"] != mp.name:
                            mp.name_aliases = [mc["name"]]
                        break
                    # Constituency-based fallback
                    if (mc["constituency"]
                            and mp.constituency
                            and normalize_state(mc["constituency"]) == normalize_state(mp.constituency)):
                        mp.myneta_candidate_id = mc["id"]
                        if not mp.name_aliases and mc["name"] != mp.name:
                            mp.name_aliases = [mc["name"]]
                        break

            matched = sum(1 for mp in mps if mp.myneta_candidate_id)
            log.info("MyNeta enrichment: matched %d/%d MPs", matched, len(mps))

        except Exception as e:
            log.warning("MyNeta enrichment failed for %s: %s", state_norm, e)

    async def _from_myneta(self, state_norm: str) -> list[MPProfile]:
        """Scrape MyNeta winners page and filter by state."""
        try:
            html = await self.scraper.fetch(settings.urls.myneta_state_winners)
            soup = BeautifulSoup(html, "lxml")
            mps: list[MPProfile] = []

            table = soup.find("table", class_="w3-table")
            if not table:
                tables = soup.find_all("table")
                table = tables[0] if tables else None

            if not table:
                log.warning("No table found on MyNeta winners page")
                return []

            rows = table.find_all("tr")
            current_state = ""

            for row in rows:
                cells = row.find_all("td")
                if not cells:
                    continue

                link = row.find("a", href=re.compile(r"candidate\.php\?candidate_id=\d+"))
                if link:
                    href = link.get("href", "")
                    cid_match = re.search(r"candidate_id=(\d+)", href)
                    candidate_id = int(cid_match.group(1)) if cid_match else None
                    candidate_name = link.get_text(strip=True)

                    constituency = ""
                    party = ""
                    row_state = ""

                    for cell in cells:
                        cell_text = cell.get_text(strip=True)
                        if cell.find("a", href=re.compile(r"candidate\.php")):
                            pass
                        elif not constituency and cell_text and not cell_text.isdigit():
                            if normalize_state(cell_text) == state_norm or (
                                current_state and normalize_state(current_state) == state_norm
                            ):
                                row_state = cell_text
                            elif not constituency:
                                constituency = cell_text

                    if len(cells) >= 4:
                        for cell in cells:
                            ct = cell.get_text(strip=True)
                            if ct and normalize_state(ct) == state_norm:
                                row_state = ct
                                break

                    if not row_state and current_state:
                        row_state = current_state

                    if row_state and normalize_state(row_state) == state_norm:
                        for cell in reversed(cells):
                            ct = cell.get_text(strip=True)
                            if ct and ct != candidate_name and ct not in (constituency, row_state) and not ct.isdigit():
                                party = ct
                                break

                        if not constituency:
                            for cell in cells:
                                ct = cell.get_text(strip=True)
                                if ct and ct != candidate_name and ct != party and ct != row_state and not ct.isdigit():
                                    constituency = ct
                                    break

                        mp = MPProfile(
                            name=candidate_name,
                            constituency=constituency or "Unknown",
                            state=state_norm,
                            party=party or "Unknown",
                            myneta_candidate_id=candidate_id,
                        )
                        mps.append(mp)
                else:
                    for cell in cells:
                        ct = cell.get_text(strip=True)
                        if ct and len(ct) > 2:
                            current_state = ct

            return mps

        except Exception as e:
            log.warning("MyNeta discovery error: %s", e)
            return []
