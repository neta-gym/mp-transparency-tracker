"""Tests for Digital Sansad API client."""

import json
import os
import pytest
from unittest.mock import AsyncMock

from tracker.tools.sansad import SansadFetcher
from tracker.tools.scraper import AsyncScraper
from tracker.models.schemas import House

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def sansad_data():
    with open(os.path.join(FIXTURES_DIR, "sansad_api_response.json")) as f:
        return json.load(f)


class TestSansadFetcher:
    @pytest.mark.asyncio
    async def test_fetch_all_ls_members(self, sansad_data):
        mock_scraper = AsyncMock(spec=AsyncScraper)
        mock_scraper.fetch_json.return_value = sansad_data

        fetcher = SansadFetcher(mock_scraper)
        members = await fetcher.fetch_all_ls_members()

        assert len(members) == 4
        assert members[0]["firstName"] == "Manoj"

    @pytest.mark.asyncio
    async def test_get_members_by_state_delhi(self, sansad_data):
        mock_scraper = AsyncMock(spec=AsyncScraper)
        mock_scraper.fetch_json.return_value = sansad_data

        fetcher = SansadFetcher(mock_scraper)
        mps = await fetcher.get_members_by_state("delhi", House.LOK_SABHA)

        assert len(mps) == 3
        assert all(mp.state == "delhi" for mp in mps)
        names = {mp.name for mp in mps}
        assert "Manoj Tiwari" in names
        assert "Bansuri Swaraj" in names
        assert "Harsh Malhotra" in names

    @pytest.mark.asyncio
    async def test_nct_alias_resolved(self, sansad_data):
        """Verifies that 'NCT of Delhi' in API response maps to 'delhi'."""
        mock_scraper = AsyncMock(spec=AsyncScraper)
        mock_scraper.fetch_json.return_value = sansad_data

        fetcher = SansadFetcher(mock_scraper)
        mps = await fetcher.get_members_by_state("delhi")

        assert len(mps) == 3  # Filters out Kerala MP

    @pytest.mark.asyncio
    async def test_sansad_member_id_populated(self, sansad_data):
        mock_scraper = AsyncMock(spec=AsyncScraper)
        mock_scraper.fetch_json.return_value = sansad_data

        fetcher = SansadFetcher(mock_scraper)
        mps = await fetcher.get_members_by_state("delhi")

        for mp in mps:
            assert mp.sansad_member_id is not None
            assert mp.profile_url is not None
            assert mp.canonical_name is not None

    @pytest.mark.asyncio
    async def test_empty_response(self):
        mock_scraper = AsyncMock(spec=AsyncScraper)
        mock_scraper.fetch_json.return_value = []

        fetcher = SansadFetcher(mock_scraper)
        mps = await fetcher.get_members_by_state("delhi")
        assert mps == []

    @pytest.mark.asyncio
    async def test_api_failure_graceful(self):
        mock_scraper = AsyncMock(spec=AsyncScraper)
        mock_scraper.fetch_json.side_effect = Exception("API down")

        fetcher = SansadFetcher(mock_scraper)
        mps = await fetcher.get_members_by_state("delhi")
        assert mps == []

    @pytest.mark.asyncio
    async def test_caching(self, sansad_data):
        mock_scraper = AsyncMock(spec=AsyncScraper)
        mock_scraper.fetch_json.return_value = sansad_data

        fetcher = SansadFetcher(mock_scraper)

        # First call fetches
        await fetcher.get_members_by_state("delhi")
        # Second call should use cache
        await fetcher.get_members_by_state("kerala")

        assert mock_scraper.fetch_json.call_count == 1  # Only one API call
