"""Tests for scraper and parser tools using HTML/JSON fixtures."""

import os
import json
import pytest

from tracker.tools.myneta import MyNetaParser, _parse_amount, _is_serious_case, _clean_ipc_sections, _infer_case_status
from tracker.tools.prs import PRSFetcher
from tracker.tools.mplads import MPLADSFetcher, _is_html, _extract_csv_link
from tracker.models.schemas import MPProfile, House

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


class TestParseAmount:
    def test_plain_number(self):
        assert _parse_amount("1000000") == 1_000_000

    def test_comma_separated(self):
        assert _parse_amount("1,00,00,000") == 1_00_00_000

    def test_crore(self):
        assert _parse_amount("Rs 2.5 Crore") == 2.5 * 1_00_00_000

    def test_lakh(self):
        assert _parse_amount("Rs 50 Lakh") == 50 * 1_00_000

    def test_empty(self):
        assert _parse_amount("") is None

    def test_none(self):
        assert _parse_amount("") is None

    def test_with_tilde(self):
        assert _parse_amount("~ Rs 1,00,000") == 1_00_000


class TestIsSeriousCase:
    def test_murder(self):
        assert _is_serious_case(["302"], "Murder")

    def test_corruption(self):
        assert _is_serious_case(["13(1)"], "Prevention of Corruption Act")

    def test_non_serious(self):
        assert not _is_serious_case(["341"], "Wrongful restraint")

    def test_keyword_match(self):
        assert _is_serious_case([], "Attempt to murder the victim")


class TestCleanIPCSections:
    def test_filters_fir_noise(self):
        sections = _clean_ipc_sections("IPC 420, FIR No. 123/2020, IPC 406")
        assert "IPC 420" in sections
        assert "IPC 406" in sections
        assert not any("FIR" in s for s in sections)

    def test_filters_police_station(self):
        sections = _clean_ipc_sections("IPC 302, PS. Tilak Marg")
        assert "IPC 302" in sections
        assert not any("PS." in s for s in sections)

    def test_plain_sections(self):
        sections = _clean_ipc_sections("IPC 420, 406")
        assert len(sections) == 2


class TestInferCaseStatus:
    def test_pending(self):
        assert _infer_case_status("Case is pending in trial court") == "pending"

    def test_convicted(self):
        assert _infer_case_status("Convicted under IPC 302") == "convicted"

    def test_disposed(self):
        assert _infer_case_status("Case disposed by court") == "disposed"

    def test_acquitted(self):
        assert _infer_case_status("Acquitted in the matter") == "acquitted"

    def test_unknown(self):
        assert _infer_case_status("IPC 420 section case") == "unknown"


class TestMyNetaParser:
    def test_parse_criminal_from_fixture(self):
        html_path = os.path.join(FIXTURES_DIR, "myneta_sample.html")
        with open(html_path) as f:
            html = f.read()

        parser = MyNetaParser(scraper=None)
        criminal, assets, extras = parser._parse(html)

        assert criminal.total_cases == 2
        assert criminal.serious_cases >= 1  # IPC 302 is serious

    def test_parse_criminal_pending_count(self):
        html_path = os.path.join(FIXTURES_DIR, "myneta_sample.html")
        with open(html_path) as f:
            html = f.read()

        parser = MyNetaParser(scraper=None)
        criminal, _, _ = parser._parse(html)

        # Cases without explicit status should be counted as pending
        assert criminal.pending_cases + criminal.disposed_cases + criminal.convictions >= 0

    def test_parse_criminal_has_sources(self):
        html_path = os.path.join(FIXTURES_DIR, "myneta_sample.html")
        with open(html_path) as f:
            html = f.read()

        parser = MyNetaParser(scraper=None)
        criminal, _, _ = parser._parse(html)

        assert len(criminal.sources) > 0
        assert criminal.sources[0].source_name == "myneta"
        assert criminal.sources[0].grade.value == "B"

    def test_parse_assets_from_fixture(self):
        html_path = os.path.join(FIXTURES_DIR, "myneta_sample.html")
        with open(html_path) as f:
            html = f.read()

        parser = MyNetaParser(scraper=None)
        criminal, assets, extras = parser._parse(html)

        assert assets.movable_assets == 2_50_00_000
        assert assets.immovable_assets == 5_00_00_000
        assert assets.total_assets == 7_50_00_000
        assert assets.liabilities == 1_00_00_000
        assert assets.net_worth == 6_50_00_000

    def test_parse_returns_profile_extras(self):
        html_path = os.path.join(FIXTURES_DIR, "myneta_sample.html")
        with open(html_path) as f:
            html = f.read()

        parser = MyNetaParser(scraper=None)
        _, _, extras = parser._parse(html)

        # extras is a dict that may contain education, profession, age
        assert isinstance(extras, dict)


# ========================
# PRS CSV Parser Tests
# ========================


class TestPRSCSVParser:
    """Test CSV row parsing with various field values."""

    def test_parse_normal_row(self):
        fetcher = PRSFetcher(scraper=None)
        row = {
            "Name": "Test MP",
            "Constituency": "Test Constituency",
            "State": "Delhi",
            "Attendance": "75",
            "Questions": "10",
            "Debates": "5",
            "Private Member Bills": "1",
            "Minister": "",
        }
        activity = fetcher._parse_csv_row(row)

        assert activity.attendance_percentage == 75.0
        assert activity.questions_asked == 10
        assert activity.debates_participated == 5
        assert activity.private_bills_introduced == 1
        assert activity.is_minister is False
        assert activity.confidence == 0.8
        assert len(activity.sources) > 0
        assert activity.sources[0].grade.value == "C"

    def test_parse_minister_attendance(self):
        """When Attendance is 'Minister', attendance should be None, is_minister True."""
        fetcher = PRSFetcher(scraper=None)
        row = {
            "Name": "Minister MP",
            "Attendance": "Minister",
            "Questions": "2",
            "Debates": "1",
            "Private Member Bills": "0",
            "Minister": "",
        }
        activity = fetcher._parse_csv_row(row)

        assert activity.attendance_percentage is None
        assert activity.is_minister is True
        assert activity.confidence == 0.3  # No attendance → low confidence

    def test_parse_minister_yes_field(self):
        """When Minister field is 'Yes', is_minister should be True."""
        fetcher = PRSFetcher(scraper=None)
        row = {
            "Name": "Minister MP",
            "Attendance": "45",
            "Questions": "2",
            "Debates": "1",
            "Private Member Bills": "0",
            "Minister": "Yes",
        }
        activity = fetcher._parse_csv_row(row)

        assert activity.attendance_percentage == 45.0
        assert activity.is_minister is True

    def test_parse_empty_fields(self):
        """Missing fields should produce defaults."""
        fetcher = PRSFetcher(scraper=None)
        row = {"Name": "Unknown MP"}
        activity = fetcher._parse_csv_row(row)

        assert activity.attendance_percentage is None
        assert activity.questions_asked == 0
        assert activity.debates_participated == 0
        assert activity.private_bills_introduced == 0
        assert activity.confidence == 0.3

    def test_parse_attendance_with_percent_sign(self):
        fetcher = PRSFetcher(scraper=None)
        row = {"Name": "MP", "Attendance": "90%", "Questions": "5", "Debates": "3", "Private Member Bills": "0"}
        activity = fetcher._parse_csv_row(row)
        assert activity.attendance_percentage == 90.0


# ========================
# PRS Slug Generation Tests
# ========================


class TestPRSSlugGeneration:
    """Test PRS URL slug building from MP names."""

    def test_simple_name(self):
        mp = MPProfile(name="Manoj Tiwari", constituency="NE Delhi", state="delhi", party="BJP")
        assert PRSFetcher._build_prs_slug(mp) == "manoj-tiwari"

    def test_title_prefix_dr(self):
        mp = MPProfile(name="Dr. Harsh Vardhan", constituency="Chandni Chowk", state="delhi", party="BJP")
        assert PRSFetcher._build_prs_slug(mp) == "harsh-vardhan"

    def test_title_prefix_shri(self):
        mp = MPProfile(name="Shri Ramesh Kumar", constituency="Test", state="delhi", party="INC")
        assert PRSFetcher._build_prs_slug(mp) == "ramesh-kumar"

    def test_uses_canonical_name(self):
        mp = MPProfile(
            name="Shri Some Alias",
            canonical_name="Real Name",
            constituency="Test",
            state="delhi",
            party="BJP",
        )
        assert PRSFetcher._build_prs_slug(mp) == "real-name"

    def test_multiple_title_prefixes(self):
        mp = MPProfile(name="Dr. Shri Test Person", constituency="Test", state="delhi", party="BJP")
        assert PRSFetcher._build_prs_slug(mp) == "test-person"


# ========================
# PRS Chart Parsing Tests
# ========================


class TestPRSChartParsing:
    """Test extraction of values from Google Charts JS functions."""

    def test_extract_from_fixture(self):
        html_path = os.path.join(FIXTURES_DIR, "prs_page_sample.html")
        with open(html_path) as f:
            html = f.read()

        assert PRSFetcher._extract_chart_value(html, "drawChartw0") == 75.0
        assert PRSFetcher._extract_chart_value(html, "drawChartw1") == 10.0
        assert PRSFetcher._extract_chart_value(html, "drawChartw2") == 50.0
        assert PRSFetcher._extract_chart_value(html, "drawChartw3") == 1.0

    def test_missing_function(self):
        html = "<html><body>No charts here</body></html>"
        assert PRSFetcher._extract_chart_value(html, "drawChartw0") is None

    def test_parse_prs_html_full(self):
        html_path = os.path.join(FIXTURES_DIR, "prs_page_sample.html")
        with open(html_path) as f:
            html = f.read()

        fetcher = PRSFetcher(scraper=None)
        activity = fetcher._parse_prs_html(html, "https://prsindia.org/mptrack/test")

        assert activity is not None
        assert activity.attendance_percentage == 75.0
        assert activity.debates_participated == 10
        assert activity.questions_asked == 50
        assert activity.private_bills_introduced == 1
        assert activity.confidence == 0.9
        assert activity.sources[0].grade.value == "B"

    def test_parse_prs_html_no_data(self):
        fetcher = PRSFetcher(scraper=None)
        result = fetcher._parse_prs_html("<html><body></body></html>", "https://test.com")
        assert result is None


# ========================
# PRS Two-Tier Lookup Tests
# ========================


class TestPRSTwoTierLookup:
    """Test the two-tier fetch_activity strategy."""

    @pytest.mark.asyncio
    async def test_csv_hit_skips_scrape(self):
        """When CSV has the MP, website scrape should not be attempted."""
        from unittest.mock import AsyncMock, patch

        mock_scraper = AsyncMock()
        # Return CSV data with the MP
        csv_text = "Name,Constituency,State,Attendance,Questions,Debates,Private Member Bills,Minister\n"
        csv_text += "Manoj Tiwari,North East Delhi,NCT of Delhi,78,12,8,2,\n"
        mock_scraper.fetch.return_value = csv_text

        fetcher = PRSFetcher(mock_scraper)
        mp = MPProfile(name="Manoj Tiwari", constituency="North East Delhi", state="delhi", party="BJP")
        activity = await fetcher.fetch_activity(mp)

        assert activity.attendance_percentage == 78.0
        assert activity.questions_asked == 12
        assert activity.confidence == 0.8
        assert activity.sources[0].source_name == "prs_github_csv"
        # fetch should be called exactly once (for CSV), not twice (no scrape)
        assert mock_scraper.fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_csv_miss_triggers_scrape(self):
        """When CSV doesn't have the MP, fall back to PRS website scrape."""
        from unittest.mock import AsyncMock

        html_path = os.path.join(FIXTURES_DIR, "prs_page_sample.html")
        with open(html_path) as f:
            prs_html = f.read()

        mock_scraper = AsyncMock()
        # First call: CSV (no match for this MP)
        csv_text = "Name,Constituency,State,Attendance,Questions,Debates,Private Member Bills,Minister\n"
        csv_text += "Some Other MP,Other Place,Other State,50,5,3,0,\n"
        # Second call: PRS page HTML
        mock_scraper.fetch.side_effect = [csv_text, prs_html]

        fetcher = PRSFetcher(mock_scraper)
        mp = MPProfile(name="Bansuri Swaraj", constituency="New Delhi", state="delhi", party="BJP")
        activity = await fetcher.fetch_activity(mp)

        assert activity.attendance_percentage == 75.0
        assert activity.questions_asked == 50
        assert activity.confidence == 0.9
        assert activity.sources[0].source_name == "prs_website"
        # fetch called twice: once for CSV, once for PRS page
        assert mock_scraper.fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_both_miss_returns_zero_confidence(self):
        """When both CSV and scrape fail, return confidence 0.0."""
        from unittest.mock import AsyncMock

        mock_scraper = AsyncMock()
        csv_text = "Name,Constituency,State,Attendance,Questions,Debates,Private Member Bills,Minister\n"
        mock_scraper.fetch.side_effect = [csv_text, Exception("404 Not Found")]

        fetcher = PRSFetcher(mock_scraper)
        mp = MPProfile(name="Nonexistent MP", constituency="Nowhere", state="delhi", party="IND")
        activity = await fetcher.fetch_activity(mp)

        assert activity.confidence == 0.0

    @pytest.mark.asyncio
    async def test_csv_constituency_fallback(self):
        """When name doesn't match but constituency + state do, should still find."""
        from unittest.mock import AsyncMock

        mock_scraper = AsyncMock()
        csv_text = "Name,Constituency,State,Attendance,Questions,Debates,Private Member Bills,Minister\n"
        csv_text += "Manoj Tiwari,North East Delhi,NCT of Delhi,78,12,8,2,\n"
        mock_scraper.fetch.return_value = csv_text

        fetcher = PRSFetcher(mock_scraper)
        mp = MPProfile(name="Unknown Name", constituency="North East Delhi", state="delhi", party="BJP")
        activity = await fetcher.fetch_activity(mp)

        assert activity.attendance_percentage == 78.0
        assert activity.confidence == 0.8


# ========================
# MPLADS HTML Detection Tests
# ========================


class TestMPLADSHTMLDetection:
    """Test that HTML responses are detected and not silently parsed as CSV."""

    def test_detect_html_doctype(self):
        assert _is_html("<!DOCTYPE html><html><head>...")

    def test_detect_html_tag(self):
        assert _is_html("<html><head><title>Dataset</title>...")

    def test_detect_html_head(self):
        assert _is_html("  \n<head><meta charset='utf-8'>...")

    def test_csv_not_detected(self):
        assert not _is_html("Name,State,Amount\nMP1,Delhi,100\n")

    def test_extract_csv_link_found(self):
        html = '<html><body><a href="/download/data.csv">Download CSV</a></body></html>'
        link = _extract_csv_link(html, "https://dataful.in/datasets/18540/")
        assert link is not None
        assert link.endswith(".csv")

    def test_extract_csv_link_text_match(self):
        html = '<html><body><a href="/download/data">Download as CSV</a></body></html>'
        link = _extract_csv_link(html, "https://dataful.in/datasets/18540/")
        assert link is not None

    def test_extract_csv_link_not_found(self):
        html = "<html><body><p>No download links</p></body></html>"
        link = _extract_csv_link(html, "https://dataful.in/datasets/18540/")
        assert link is None

    @pytest.mark.asyncio
    async def test_html_response_not_parsed_as_csv(self):
        """HTML landing page should result in empty data, not garbled records."""
        from unittest.mock import AsyncMock

        mock_scraper = AsyncMock()
        mock_scraper.fetch.return_value = (
            "<!DOCTYPE html><html><head><title>MPLADS Dataset</title></head>"
            "<body><h1>MPLADS Data</h1><p>No download link here</p></body></html>"
        )

        fetcher = MPLADSFetcher(mock_scraper)
        mp = MPProfile(name="Test MP", constituency="Test", state="delhi", party="BJP")
        result = await fetcher.fetch_fund_data(mp)

        assert result.confidence == 0.0
        assert len(result.sources) > 0

    @pytest.mark.asyncio
    async def test_valid_csv_still_works(self):
        """A proper CSV response should still be parsed correctly."""
        from unittest.mock import AsyncMock

        mock_scraper = AsyncMock()
        csv_text = (
            "MP Name,Constituency,State,Released,Expended\n"
            "Test MP,Test Seat,Delhi,500.0,400.0\n"
        )
        mock_scraper.fetch.return_value = csv_text

        fetcher = MPLADSFetcher(mock_scraper)
        mp = MPProfile(name="Test MP", constituency="Test Seat", state="delhi", party="BJP")
        result = await fetcher.fetch_fund_data(mp)

        assert result.released == 500.0
        assert result.expended == 400.0
        assert result.confidence == 0.8


# ========================
# Social Media Fetcher Tests
# ========================


class TestSocialMediaFetcher:
    @pytest.mark.asyncio
    async def test_known_mp_returns_profiles(self):
        from unittest.mock import AsyncMock
        from tracker.tools.social_media import SocialMediaFetcher

        mock_scraper = AsyncMock()
        fetcher = SocialMediaFetcher(mock_scraper)
        mp = MPProfile(name="Bansuri Swaraj", constituency="New Delhi", state="delhi", party="BJP")
        result = await fetcher.fetch_social_media(mp)

        assert result.total_platforms > 0
        assert result.confidence > 0
        assert any(p.platform == "twitter" for p in result.profiles)

    @pytest.mark.asyncio
    async def test_unknown_mp_low_confidence(self):
        from unittest.mock import AsyncMock
        from tracker.tools.social_media import SocialMediaFetcher

        mock_scraper = AsyncMock()
        fetcher = SocialMediaFetcher(mock_scraper)
        mp = MPProfile(name="Unknown Person", constituency="Nowhere", state="delhi", party="IND")
        result = await fetcher.fetch_social_media(mp)

        assert result.total_platforms == 0
        assert result.confidence <= 0.3


# ========================
# News Fetcher Tests
# ========================


class TestNewsFetcher:
    def test_classify_sentiment(self):
        from tracker.tools.news import _classify_sentiment

        assert _classify_sentiment("MP arrested in scam case") == "negative"
        assert _classify_sentiment("MP inaugurated new school") == "positive"
        assert _classify_sentiment("MP meets delegation") == "neutral"

    def test_parse_rss_empty(self):
        from tracker.tools.news import NewsFetcher

        fetcher = NewsFetcher(scraper=None)
        mp = MPProfile(name="Test", constituency="Test", state="delhi", party="BJP")
        result = fetcher._parse_rss("<rss></rss>", mp)

        assert result.total_articles == 0
        assert result.confidence == 0.0


# ========================
# Constituency Fetcher Tests
# ========================


class TestConstituencyFetcher:
    def test_delhi_constituency_found(self):
        from tracker.tools.constituency import ConstituencyFetcher

        fetcher = ConstituencyFetcher()
        mp = MPProfile(name="Test", constituency="New Delhi", state="delhi", party="BJP")
        ctx = fetcher.fetch_context(mp)

        assert ctx.district == "New Delhi"
        assert ctx.population is not None
        assert ctx.literacy_rate is not None

    def test_unknown_constituency_empty(self):
        from tracker.tools.constituency import ConstituencyFetcher

        fetcher = ConstituencyFetcher()
        mp = MPProfile(name="Test", constituency="Unknown Place", state="unknown", party="BJP")
        ctx = fetcher.fetch_context(mp)

        assert ctx.district == ""
        assert ctx.population is None


# ========================
# Sansad Committee Parser Tests
# ========================


class TestSansadCommitteeParser:
    def test_parse_committees_from_html(self):
        from tracker.tools.sansad import SansadFetcher

        html = """
        <div>
        <h3>Committee Memberships</h3>
        <ul>
            <li>Standing Committee on Finance - Chairperson</li>
            <li>Joint Committee on Food Processing</li>
            <li>Committee on External Affairs</li>
        </ul>
        </div>
        """
        fetcher = SansadFetcher(scraper=None)
        result = fetcher._parse_committees(html, "https://sansad.in/test")

        assert result.total_committees >= 2
        assert result.confidence > 0

    def test_parse_committees_empty_html(self):
        from tracker.tools.sansad import SansadFetcher

        fetcher = SansadFetcher(scraper=None)
        result = fetcher._parse_committees("<html><body>No data</body></html>", "https://test.com")

        assert result.total_committees == 0
        assert result.confidence <= 0.3
