"""News fetcher — retrieves recent news articles about an MP."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from html import unescape
from urllib.parse import quote_plus

from ..models.schemas import (
    MPProfile,
    NewsAllegation,
    NewsSentiment,
    DataSource,
    EvidenceGrade,
)
from ..utils.logger import get_logger
from .scraper import AsyncScraper

log = get_logger(__name__)

# Simple keyword-based sentiment classification
_POSITIVE_KEYWORDS = {
    "inaugurated", "launched", "awarded", "praised", "development",
    "welfare", "achieved", "donated", "relief", "scheme",
    "progress", "improved", "successful", "contribution",
}
_NEGATIVE_KEYWORDS = {
    "arrested", "accused", "scam", "corruption", "scandal",
    "fraud", "allegation", "controversy", "raid", "chargesheet",
    "convicted", "booked", "fir", "complaint", "protest",
}


def _classify_sentiment(headline: str) -> str:
    """Simple keyword-based sentiment classification."""
    words = set(headline.lower().split())
    neg_count = len(words & _NEGATIVE_KEYWORDS)
    pos_count = len(words & _POSITIVE_KEYWORDS)

    if neg_count > pos_count:
        return "negative"
    if pos_count > neg_count:
        return "positive"
    return "neutral"


class NewsFetcher:
    """Fetches and classifies news about an MP."""

    def __init__(self, scraper: AsyncScraper) -> None:
        self.scraper = scraper

    async def fetch_news(self, mp: MPProfile) -> NewsSentiment:
        """Fetch recent news about an MP using Google News RSS."""
        query = f"{mp.name} MP {mp.constituency}"
        url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-IN&gl=IN&ceid=IN:en"

        try:
            rss_text = await self.scraper.fetch(url)
        except Exception as e:
            log.warning("News fetch failed for %s: %s", mp.name, e)
            return NewsSentiment(confidence=0.0)

        return self._parse_rss(rss_text, mp)

    def _parse_rss(self, rss_text: str, mp: MPProfile) -> NewsSentiment:
        """Parse Google News RSS feed and classify sentiment."""
        headlines: list[NewsAllegation] = []
        positive = 0
        negative = 0
        neutral = 0

        # Parse RSS with xml.etree — handles CDATA, encoding, namespaces correctly
        try:
            root = ET.fromstring(rss_text)
        except ET.ParseError:
            log.warning("Failed to parse RSS XML for %s, falling back to regex", mp.name)
            return self._parse_rss_regex_fallback(rss_text, mp)

        # RSS 2.0: root/channel/item
        channel = root.find("channel")
        items = channel.findall("item") if channel is not None else root.findall(".//item")

        for item in items[:10]:
            title_el = item.find("title")
            link_el = item.find("link")
            source_el = item.find("source")

            title = unescape(title_el.text or "") if title_el is not None else ""
            title = re.sub(r"<[^>]+>", "", title).strip()
            link = (link_el.text or "").strip() if link_el is not None else ""
            source_name = (source_el.text or "").strip() if source_el is not None else "Google News"

            if not title:
                continue

            sentiment = _classify_sentiment(title)
            if sentiment == "positive":
                positive += 1
                severity = "low"
            elif sentiment == "negative":
                negative += 1
                severity = "medium"
            else:
                neutral += 1
                severity = "low"

            headlines.append(NewsAllegation(
                headline=title,
                source=source_name,
                severity=severity,
                url=link,
                sentiment=sentiment,
            ))

        total = len(headlines)
        if total == 0:
            return NewsSentiment(confidence=0.0)

        # Build summary
        if negative > positive and negative > neutral:
            summary = f"Predominantly negative coverage ({negative}/{total} articles)"
        elif positive > negative and positive > neutral:
            summary = f"Predominantly positive coverage ({positive}/{total} articles)"
        else:
            summary = f"Mixed/neutral coverage ({total} articles)"

        return NewsSentiment(
            total_articles=total,
            positive=positive,
            negative=negative,
            neutral=neutral,
            top_headlines=headlines[:5],
            sentiment_summary=summary,
            confidence=0.5 if total > 0 else 0.0,
        )

    def _parse_rss_regex_fallback(self, rss_text: str, mp: MPProfile) -> NewsSentiment:
        """Regex fallback for malformed RSS that xml.etree can't parse."""
        items = re.findall(
            r"<item>.*?<title>(.*?)</title>.*?<link>(.*?)</link>.*?</item>",
            rss_text, re.DOTALL,
        )
        headlines = []
        positive = negative = neutral = 0
        for title, link in items[:10]:
            title = unescape(re.sub(r"<[^>]+>", "", title).strip())
            if not title:
                continue
            sentiment = _classify_sentiment(title)
            if sentiment == "positive":
                positive += 1
            elif sentiment == "negative":
                negative += 1
            else:
                neutral += 1
            headlines.append(NewsAllegation(
                headline=title, source="Google News",
                severity="medium" if sentiment == "negative" else "low",
                url=link, sentiment=sentiment,
            ))
        total = len(headlines)
        return NewsSentiment(
            total_articles=total, positive=positive, negative=negative, neutral=neutral,
            top_headlines=headlines[:5],
            sentiment_summary=f"Mixed coverage ({total} articles)" if total else "",
            confidence=0.5 if total > 0 else 0.0,
        )
