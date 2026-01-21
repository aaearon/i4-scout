"""Base scraper abstract class."""

import asyncio
import random
from abc import ABC, abstractmethod
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, TypeVar

from playwright.async_api import Page
from tenacity import (
    AsyncRetrying,
    RetryError,
    stop_after_attempt,
    wait_fixed,
)

from i4_scout.models.pydantic_models import ScrapedListing, SearchFilters, Source
from i4_scout.scrapers.browser import BrowserManager
from i4_scout.scrapers.cache import get_cache

T = TypeVar("T")


@dataclass
class ScraperConfig:
    """Configuration for scraper behavior."""

    max_pages: int = 10
    min_delay: float = 2.0
    max_delay: float = 5.0
    max_retries: int = 3
    retry_delay: float = 5.0
    rate_limit_per_minute: int = 20


class BaseScraper(ABC):
    """Abstract base class for site-specific scrapers.

    Provides shared infrastructure for:
    - Browser context management
    - Human-like behavior (delays, scrolling)
    - Retry logic with tenacity
    - Rate limiting
    - Cookie consent handling

    Subclasses must implement:
    - source: The Source enum value
    - get_search_url(): Generate search URL for pagination
    - parse_listing_cards(): Extract listings from search results
    - parse_listing_detail(): Extract full details from listing page
    """

    source: Source

    # Cookie consent button selectors to try
    COOKIE_CONSENT_SELECTORS = [
        'button[data-testid="as24-cmp-accept-all-button"]',
        '#onetrust-accept-btn-handler',
        'button:has-text("Alle akzeptieren")',
        'button:has-text("Accept All")',
        'button:has-text("Zustimmen")',
        '[data-cy="consent-accept-all"]',
        'button:has-text("Akzeptieren")',
    ]

    def __init__(
        self,
        browser_manager: BrowserManager,
        config: ScraperConfig | None = None,
    ) -> None:
        """Initialize base scraper.

        Args:
            browser_manager: Browser manager instance.
            config: Scraper configuration. Uses defaults if not provided.
        """
        self._browser_manager = browser_manager
        self._config = config or ScraperConfig()
        self._last_request_time: float = 0.0

    @property
    def config(self) -> ScraperConfig:
        """Get scraper configuration."""
        return self._config

    @abstractmethod
    def get_search_url(
        self, page: int = 1, filters: SearchFilters | None = None
    ) -> str:
        """Generate search URL for the given page number.

        Args:
            page: Page number (1-indexed).
            filters: Optional search filters to apply.

        Returns:
            Full URL for the search results page.
        """
        ...

    @abstractmethod
    async def parse_listing_cards(self, html: str) -> list[dict[str, Any]]:
        """Parse listing cards from search results HTML.

        Args:
            html: Raw HTML content of search results page.

        Returns:
            List of dicts with basic listing info (title, url, price, etc.).
        """
        ...

    @abstractmethod
    async def parse_listing_detail(self, html: str, url: str) -> ScrapedListing:
        """Parse full listing details from detail page HTML.

        Args:
            html: Raw HTML content of listing detail page.
            url: URL of the listing.

        Returns:
            ScrapedListing with all extracted data.
        """
        ...

    async def random_delay(self, min_sec: float | None = None, max_sec: float | None = None) -> None:
        """Sleep for a random human-like delay.

        Args:
            min_sec: Minimum delay in seconds. Uses config default if not provided.
            max_sec: Maximum delay in seconds. Uses config default if not provided.
        """
        min_delay = min_sec if min_sec is not None else self._config.min_delay
        max_delay = max_sec if max_sec is not None else self._config.max_delay
        await asyncio.sleep(random.uniform(min_delay, max_delay))

    async def human_scroll(
        self,
        page: Page,
        scroll_count: int = 3,
        min_delta: int = 300,
        max_delta: int = 600,
    ) -> None:
        """Simulate human-like scrolling on a page.

        Args:
            page: Playwright Page instance.
            scroll_count: Number of scroll actions.
            min_delta: Minimum scroll distance in pixels.
            max_delta: Maximum scroll distance in pixels.
        """
        for _ in range(scroll_count):
            delta = random.randint(min_delta, max_delta)
            await page.mouse.wheel(0, delta)
            await asyncio.sleep(random.uniform(0.3, 0.8))

    async def handle_cookie_consent(self, page: Page) -> bool:
        """Handle cookie consent banners if present.

        Args:
            page: Playwright Page instance.

        Returns:
            True if a consent button was clicked, False otherwise.
        """
        for selector in self.COOKIE_CONSENT_SELECTORS:
            try:
                btn = page.locator(selector).first
                if await btn.is_visible(timeout=2000):
                    await btn.click()
                    await asyncio.sleep(random.uniform(0.5, 1.5))
                    return True
            except Exception:
                continue
        return False

    async def with_retry(
        self,
        operation: Callable[[], Coroutine[Any, Any, T]],
    ) -> T:
        """Execute an async operation with retry logic.

        Args:
            operation: Async function to execute.

        Returns:
            Result of the operation.

        Raises:
            Exception: If all retries are exhausted.
        """
        last_exception: BaseException | None = None

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self._config.max_retries),
                wait=wait_fixed(self._config.retry_delay),
                reraise=True,
            ):
                with attempt:
                    return await operation()
        except RetryError as e:
            if e.last_attempt.failed:
                last_exception = e.last_attempt.exception()
                if last_exception:
                    raise last_exception from e
            raise

        raise RuntimeError("Retry logic failed unexpectedly")

    async def check_rate_limit(self) -> None:
        """Enforce rate limiting by delaying if needed.

        Ensures requests don't exceed the configured rate limit.
        """
        if self._config.rate_limit_per_minute <= 0:
            return

        min_interval = 60.0 / self._config.rate_limit_per_minute
        current_time = asyncio.get_event_loop().time()
        elapsed = current_time - self._last_request_time

        if elapsed < min_interval and self._last_request_time > 0:
            wait_time = min_interval - elapsed
            await asyncio.sleep(wait_time)

        self._last_request_time = asyncio.get_event_loop().time()

    async def navigate_to(
        self,
        page: Page,
        url: str,
        wait_until: str = "domcontentloaded",
        use_cache: bool = False,  # Disabled by default for now
    ) -> str:
        """Navigate to a URL with caching, rate limiting and retries.

        Args:
            page: Playwright Page instance.
            url: URL to navigate to.
            wait_until: Wait condition for navigation.
            use_cache: Whether to check/use cache (default: True).

        Returns:
            HTML content of the page.
        """
        # Check cache first
        if use_cache:
            cache = get_cache()
            cached = cache.get(url)
            if cached:
                return cached.html

        await self.check_rate_limit()
        await self._browser_manager.increment_request_count()

        async def _navigate() -> str:
            await page.goto(url, wait_until=wait_until, timeout=30000)  # type: ignore[arg-type]
            return await page.content()

        html = await self.with_retry(_navigate)

        # Store in cache
        if use_cache:
            cache = get_cache()
            cache.set(url, html)

        return html

    async def scrape_search_page(
        self,
        page: Page,
        page_num: int = 1,
        filters: SearchFilters | None = None,
        use_cache: bool = True,
    ) -> list[dict[str, Any]]:
        """Scrape a single search results page.

        Args:
            page: Playwright Page instance.
            page_num: Page number to scrape.
            filters: Optional search filters to apply.
            use_cache: Whether to use HTML caching (1-hour TTL for search pages).

        Returns:
            List of listing card data.
        """
        url = self.get_search_url(page_num, filters)
        html = await self.navigate_to(page, url, use_cache=use_cache)
        await self.random_delay(1.0, 2.0)
        await self.handle_cookie_consent(page)
        await self.human_scroll(page)

        return await self.parse_listing_cards(html)

    async def scrape_listing_detail(
        self, page: Page, url: str, use_cache: bool = True
    ) -> ScrapedListing:
        """Scrape a single listing detail page.

        Args:
            page: Playwright Page instance.
            url: URL of the listing.
            use_cache: Whether to use HTML caching (24-hour TTL for detail pages).

        Returns:
            ScrapedListing with full details.
        """
        html = await self.navigate_to(page, url, use_cache=use_cache)
        await self.random_delay(1.0, 2.0)
        await self.handle_cookie_consent(page)
        await self.human_scroll(page)

        return await self.parse_listing_detail(html, url)
