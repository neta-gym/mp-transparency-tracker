"""Async HTTP client with rate limiting and retry."""

from __future__ import annotations

import asyncio
from typing import Optional

import aiohttp

from ..config import settings
from ..utils.logger import get_logger

log = get_logger(__name__)


class AsyncScraper:
    """Rate-limited async HTTP client with exponential backoff retry."""

    def __init__(self) -> None:
        self._session: Optional[aiohttp.ClientSession] = None
        self._session_lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(5)
        self._delay = settings.scrape_delay

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is not None and not self._session.closed:
            return self._session
        async with self._session_lock:
            # Double-check after acquiring lock
            if self._session is None or self._session.closed:
                timeout = aiohttp.ClientTimeout(total=30)
                self._session = aiohttp.ClientSession(
                    timeout=timeout,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                                      "Chrome/120.0.0.0 Safari/537.36",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.5",
                    },
                )
        return self._session

    async def fetch(self, url: str, retries: int = 0) -> str:
        """Fetch URL content as text with rate limiting and retry."""
        max_retries = retries or settings.max_retries
        last_error: Exception | None = None

        for attempt in range(max_retries):
            # Rate-limit delay outside the semaphore to avoid holding a slot while sleeping
            await asyncio.sleep(self._delay)
            async with self._semaphore:
                try:
                    session = await self._get_session()
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            return await resp.text()
                        elif resp.status == 429:
                            delay = settings.retry_base_delay * (2 ** attempt)
                            log.warning("Rate limited on %s, retrying in %.1fs", url, delay)
                            await asyncio.sleep(delay)
                            continue
                        elif resp.status == 404:
                            log.warning("HTTP 404 for %s — not found, skipping retries", url)
                            raise aiohttp.ClientResponseError(
                                resp.request_info, resp.history, status=resp.status
                            )
                        else:
                            log.warning("HTTP %d for %s (attempt %d)", resp.status, url, attempt + 1)
                            last_error = aiohttp.ClientResponseError(
                                resp.request_info, resp.history, status=resp.status
                            )
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    last_error = e
                    delay = settings.retry_base_delay * (2 ** attempt)
                    log.warning("Request error for %s: %s, retrying in %.1fs", url, e, delay)
                    await asyncio.sleep(delay)

        log.error("Failed to fetch %s after %d attempts", url, max_retries)
        raise last_error or RuntimeError(f"Failed to fetch {url}")

    async def fetch_json(self, url: str) -> dict | list:
        """Fetch URL and parse as JSON."""
        max_retries = settings.max_retries
        last_error: Exception | None = None

        for attempt in range(max_retries):
            await asyncio.sleep(self._delay)
            async with self._semaphore:
                try:
                    session = await self._get_session()
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            return await resp.json(content_type=None)
                        last_error = aiohttp.ClientResponseError(
                            resp.request_info, resp.history, status=resp.status
                        )
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    last_error = e
                    await asyncio.sleep(settings.retry_base_delay * (2 ** attempt))

        raise last_error or RuntimeError(f"Failed to fetch JSON from {url}")

    async def fetch_html(self, url: str, parser: str = "lxml") -> "BeautifulSoup":
        """Fetch URL and parse as HTML with BeautifulSoup."""
        from bs4 import BeautifulSoup
        text = await self.fetch(url)
        return BeautifulSoup(text, parser)

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def __aenter__(self) -> "AsyncScraper":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()
