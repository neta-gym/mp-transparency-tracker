"""Data fetching and parsing tools."""

from .scraper import AsyncScraper
from .browser import PlaywrightBrowser
from .mp_discovery import MPDiscovery
from .myneta import MyNetaParser
from .prs import PRSFetcher
from .mplads import MPLADSFetcher
from .esakshi import ESAKSHIFetcher
from .mplads_datagov import DataGovMPLADSFetcher
from .sansad import SansadFetcher
from .sansad_qa import SansadQAParser
from .doj import DoJFetcher
from .cag import CAGFetcher
from .budget import BudgetFetcher
from .sagy import SAGYFetcher
from .social_media import SocialMediaFetcher
from .news import NewsFetcher
from .constituency import ConstituencyFetcher

__all__ = [
    "AsyncScraper",
    "PlaywrightBrowser",
    "MPDiscovery",
    "MyNetaParser",
    "PRSFetcher",
    "MPLADSFetcher",
    "ESAKSHIFetcher",
    "DataGovMPLADSFetcher",
    "SansadFetcher",
    "SansadQAParser",
    "DoJFetcher",
    "CAGFetcher",
    "BudgetFetcher",
    "SAGYFetcher",
    "SocialMediaFetcher",
    "NewsFetcher",
    "ConstituencyFetcher",
]
