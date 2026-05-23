"""Shared Playwright browser manager for JS-rendered pages."""

from __future__ import annotations

import asyncio
from typing import Optional

from ..utils.logger import get_logger

log = get_logger(__name__)


class PlaywrightBrowser:
    """Manages a singleton headless Chromium instance.

    Usage::

        browser = PlaywrightBrowser()
        await browser.start()
        page = await browser.new_page()
        await page.goto("https://example.com")
        # ... interact with page ...
        await page.close()
        await browser.close()
    """

    def __init__(self, headless: bool = True) -> None:
        self._headless = headless
        self._playwright: Optional[object] = None
        self._browser: Optional[object] = None
        self._context: Optional[object] = None
        self._lock = asyncio.Lock()
        self._started = False

    async def start(self) -> None:
        """Launch Chromium browser (idempotent)."""
        async with self._lock:
            if self._started:
                return
            try:
                from playwright.async_api import async_playwright

                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(
                    headless=self._headless,
                    args=["--disable-blink-features=AutomationControlled"],
                )
                self._context = await self._browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                )
                self._started = True
                log.info("Playwright browser started (headless=%s)", self._headless)
            except Exception as e:
                log.error("Failed to start Playwright browser: %s", e)
                await self._cleanup_partial()
                raise

    async def new_page(self):
        """Create a new page in the shared browser context."""
        if not self._started:
            await self.start()
        return await self._context.new_page()

    async def close(self) -> None:
        """Shut down browser and Playwright."""
        async with self._lock:
            await self._cleanup_partial()
            self._started = False

    async def _cleanup_partial(self) -> None:
        """Close resources that were successfully created."""
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
            self._context = None

        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

    @property
    def is_started(self) -> bool:
        return self._started
