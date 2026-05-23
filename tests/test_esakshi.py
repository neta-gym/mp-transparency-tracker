"""Tests for eSAKSHI fetcher."""

import json
import pytest
from unittest.mock import AsyncMock

from tracker.tools.esakshi import ESAKSHIFetcher, _classify_sector, _parse_amount
from tracker.models.schemas import MPProfile


class TestParseAmount:
    def test_normal_number(self):
        assert _parse_amount("500.0") == 500.0

    def test_with_commas(self):
        assert _parse_amount("1,00,000") == 100000.0

    def test_with_currency_symbol(self):
        assert _parse_amount("Rs 5,000") == 5000.0

    def test_empty(self):
        assert _parse_amount("") is None

    def test_none(self):
        assert _parse_amount(None) is None


class TestClassifySector:
    def test_education(self):
        assert _classify_sector("Construction of School Building") == "education"

    def test_health(self):
        assert _classify_sector("Purchase of Ambulance for PHC") == "health"

    def test_infrastructure(self):
        assert _classify_sector("Road construction in village") == "infrastructure"

    def test_water(self):
        assert _classify_sector("Installation of Handpump") == "water"

    def test_community(self):
        assert _classify_sector("Construction of Community Hall") == "community"

    def test_other(self):
        assert _classify_sector("Miscellaneous work") == "other"


class TestESAKSHIFetcher:
    @pytest.mark.asyncio
    async def test_api_response_parsed(self):
        """When eSAKSHI API returns valid JSON, parse it correctly."""
        mock_scraper = AsyncMock()
        api_response = json.dumps({
            "mp_name": "Test MP",
            "constituency": "Test Constituency",
            "entitled": "2500",
            "released": "2000",
            "sanctioned": "1800",
            "expended": "1500",
        })
        mock_scraper.fetch.return_value = api_response

        fetcher = ESAKSHIFetcher(mock_scraper)
        mp = MPProfile(name="Test MP", constituency="Test Constituency", state="delhi", party="BJP")
        result = await fetcher.fetch_fund_data(mp)

        assert result.entitled == 2500.0
        assert result.released == 2000.0
        assert result.expended == 1500.0
        assert result.confidence == 0.9
        assert result.sources[0].grade.value == "A"
        assert result.sources[0].source_name == "esakshi"

    @pytest.mark.asyncio
    async def test_api_failure_returns_empty(self):
        """When eSAKSHI API fails, return empty result with Grade A source."""
        mock_scraper = AsyncMock()
        mock_scraper.fetch.side_effect = Exception("Connection refused")

        fetcher = ESAKSHIFetcher(mock_scraper)
        mp = MPProfile(name="Test MP", constituency="Test", state="delhi", party="BJP")
        result = await fetcher.fetch_fund_data(mp)

        assert result.confidence == 0.0
        assert len(result.sources) > 0
        assert result.sources[0].source_name == "esakshi"

    @pytest.mark.asyncio
    async def test_works_parsed_from_api(self):
        """When eSAKSHI works API returns data, parse individual works."""
        mock_scraper = AsyncMock()
        works_response = json.dumps([
            {
                "work_id": "W001",
                "work_name": "Construction of School Building",
                "sanctioned_amount": "15.0",
                "expended_amount": "12.5",
                "status": "completed",
                "district": "Central Delhi",
            },
            {
                "work_id": "W002",
                "work_name": "Road construction in village area",
                "sanctioned_amount": "8.0",
                "expended_amount": "0",
                "status": "sanctioned",
                "district": "New Delhi",
            },
        ])
        # fetch_works only calls _fetch_works_via_api which makes one fetch call
        mock_scraper.fetch.return_value = works_response

        fetcher = ESAKSHIFetcher(mock_scraper)
        mp = MPProfile(name="Test MP", constituency="Test", state="delhi", party="BJP")
        works = await fetcher.fetch_works(mp)

        assert len(works) == 2
        assert works[0].work_id == "W001"
        assert works[0].sector == "education"
        assert works[0].sanctioned_amount == 15.0
        assert works[1].sector == "infrastructure"

    @pytest.mark.asyncio
    async def test_html_dashboard_parsed(self):
        """When API fails but HTML dashboard has data, parse it."""
        mock_scraper = AsyncMock()
        html = """
        <html><body>
        <table>
            <tr><td>Entitled</td><td>2500.00</td></tr>
            <tr><td>Released</td><td>2000.00</td></tr>
            <tr><td>Expenditure</td><td>1800.00</td></tr>
        </table>
        </body></html>
        """
        # First call (API) fails, second call (HTML) succeeds
        mock_scraper.fetch.side_effect = [Exception("API error"), html]

        fetcher = ESAKSHIFetcher(mock_scraper)
        mp = MPProfile(name="Test MP", constituency="Test", state="delhi", party="BJP")
        result = await fetcher.fetch_fund_data(mp)

        assert result.entitled == 2500.0
        assert result.released == 2000.0
        assert result.expended == 1800.0
        assert result.confidence > 0
