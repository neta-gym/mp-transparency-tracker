"""Tests for MP discovery module."""

import pytest
from unittest.mock import AsyncMock, patch

from tracker.tools.mp_discovery import MPDiscovery
from tracker.tools.sansad import SansadFetcher
from tracker.tools.scraper import AsyncScraper
from tracker.models.schemas import MPProfile, House
from tracker.utils.name_match import normalize_state


class TestNormalizeState:
    def test_normalize_state_basic(self):
        assert normalize_state("Delhi") == "delhi"
        assert normalize_state("  Uttar Pradesh  ") == "uttar pradesh"

    def test_normalize_state_nct_alias(self):
        assert normalize_state("NCT of Delhi") == "delhi"

    def test_normalize_state_jk_alias(self):
        assert normalize_state("Jammu & Kashmir") == "jammu and kashmir"


class TestSansadFirstDiscovery:
    @pytest.mark.asyncio
    async def test_discover_from_sansad(self):
        """Sansad API is primary source — should return MPs without hitting MyNeta."""
        mock_scraper = AsyncMock(spec=AsyncScraper)
        mock_sansad = AsyncMock(spec=SansadFetcher)

        # Sansad returns Delhi MPs
        mock_sansad.get_members_by_state.return_value = [
            MPProfile(name="Manoj Tiwari", constituency="North East Delhi",
                      state="delhi", party="BJP", house=House.LOK_SABHA,
                      sansad_member_id=101, canonical_name="Manoj Tiwari"),
            MPProfile(name="Bansuri Swaraj", constituency="New Delhi",
                      state="delhi", party="BJP", house=House.LOK_SABHA,
                      sansad_member_id=102, canonical_name="Bansuri Swaraj"),
        ]

        discovery = MPDiscovery(mock_scraper, mock_sansad)
        mps = await discovery.discover("delhi")

        assert len(mps) == 2
        assert mps[0].name == "Manoj Tiwari"
        assert mps[0].sansad_member_id == 101
        # Sansad was the primary source (not MyNeta winners page)
        mock_sansad.get_members_by_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_discover_with_rs(self):
        """include_rs=True should also fetch Rajya Sabha members."""
        mock_scraper = AsyncMock(spec=AsyncScraper)
        mock_sansad = AsyncMock(spec=SansadFetcher)

        ls_mps = [
            MPProfile(name="Manoj Tiwari", constituency="North East Delhi",
                      state="delhi", party="BJP", house=House.LOK_SABHA),
        ]
        rs_mps = [
            MPProfile(name="Sanjay Singh", constituency="Delhi",
                      state="delhi", party="AAP", house=House.RAJYA_SABHA),
        ]

        def side_effect(state, house=House.LOK_SABHA):
            if house == House.LOK_SABHA:
                return ls_mps
            return rs_mps

        mock_sansad.get_members_by_state.side_effect = side_effect

        discovery = MPDiscovery(mock_scraper, mock_sansad)
        mps = await discovery.discover("delhi", include_rs=True)

        assert len(mps) == 2
        assert any(mp.house == House.LOK_SABHA for mp in mps)
        assert any(mp.house == House.RAJYA_SABHA for mp in mps)

    @pytest.mark.asyncio
    async def test_fallback_to_myneta(self):
        """When Sansad returns empty, should try MyNeta."""
        mock_scraper = AsyncMock(spec=AsyncScraper)
        mock_sansad = AsyncMock(spec=SansadFetcher)
        mock_sansad.get_members_by_state.return_value = []

        # MyNeta also fails
        mock_scraper.fetch.side_effect = Exception("MyNeta unavailable")

        discovery = MPDiscovery(mock_scraper, mock_sansad)
        mps = await discovery.discover("nonexistent")

        assert mps == []

    @pytest.mark.asyncio
    async def test_empty_state(self):
        mock_scraper = AsyncMock(spec=AsyncScraper)
        mock_sansad = AsyncMock(spec=SansadFetcher)
        mock_sansad.get_members_by_state.return_value = []
        mock_scraper.fetch.side_effect = Exception("fail")

        discovery = MPDiscovery(mock_scraper, mock_sansad)
        mps = await discovery.discover("nonexistent")
        assert mps == []
