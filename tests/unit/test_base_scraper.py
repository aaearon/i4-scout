"""Unit tests for BaseScraper ABC."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from car_scraper.models.pydantic_models import ScrapedListing, Source
from car_scraper.scrapers.base import BaseScraper, ScraperConfig


class TestScraperConfig:
    """Tests for ScraperConfig dataclass."""

    def test_default_values(self):
        """ScraperConfig should have sensible defaults."""
        config = ScraperConfig()

        assert config.max_pages == 10
        assert config.min_delay == 2.0
        assert config.max_delay == 5.0
        assert config.max_retries == 3
        assert config.retry_delay == 5.0
        assert config.rate_limit_per_minute == 20

    def test_custom_values(self):
        """ScraperConfig should accept custom values."""
        config = ScraperConfig(
            max_pages=5,
            min_delay=1.0,
            max_delay=3.0,
            max_retries=5,
            retry_delay=10.0,
            rate_limit_per_minute=10,
        )

        assert config.max_pages == 5
        assert config.min_delay == 1.0
        assert config.max_delay == 3.0
        assert config.max_retries == 5
        assert config.retry_delay == 10.0
        assert config.rate_limit_per_minute == 10


class ConcreteScraper(BaseScraper):
    """Concrete implementation for testing."""

    source = Source.AUTOSCOUT24_DE

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.search_url_calls = []
        self.parse_listing_cards_calls = []
        self.parse_listing_detail_calls = []

    def get_search_url(self, page: int = 1) -> str:
        self.search_url_calls.append(page)
        return f"https://example.com/search?page={page}"

    async def parse_listing_cards(self, html: str) -> list[dict]:
        self.parse_listing_cards_calls.append(html)
        return [
            {"title": "Test Car 1", "url": "https://example.com/car/1"},
            {"title": "Test Car 2", "url": "https://example.com/car/2"},
        ]

    async def parse_listing_detail(self, html: str, url: str) -> ScrapedListing:
        self.parse_listing_detail_calls.append((html, url))
        return ScrapedListing(
            source=self.source,
            url=url,
            title="Test Car",
            price=5000000,
            options_list=["Option1", "Option2"],
        )


class TestBaseScraper:
    """Tests for BaseScraper ABC."""

    def test_is_abstract_class(self):
        """BaseScraper should be abstract and not instantiable directly."""
        with pytest.raises(TypeError):
            BaseScraper(browser_manager=MagicMock())

    def test_concrete_subclass_instantiable(self):
        """Concrete subclasses should be instantiable."""
        manager = MagicMock()
        scraper = ConcreteScraper(browser_manager=manager)
        assert scraper is not None
        assert scraper.source == Source.AUTOSCOUT24_DE

    def test_get_search_url_abstract(self):
        """get_search_url should be abstract."""
        manager = MagicMock()
        scraper = ConcreteScraper(browser_manager=manager)
        url = scraper.get_search_url(page=2)
        assert "page=2" in url

    @pytest.mark.asyncio
    async def test_random_delay(self):
        """random_delay should sleep for configured duration."""
        manager = MagicMock()
        config = ScraperConfig(min_delay=0.01, max_delay=0.02)
        scraper = ConcreteScraper(browser_manager=manager, config=config)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await scraper.random_delay()
            mock_sleep.assert_called_once()
            delay = mock_sleep.call_args[0][0]
            assert 0.01 <= delay <= 0.02

    @pytest.mark.asyncio
    async def test_human_scroll(self):
        """human_scroll should simulate scrolling."""
        manager = MagicMock()
        mock_page = AsyncMock()
        mock_page.mouse.wheel = AsyncMock()

        scraper = ConcreteScraper(browser_manager=manager)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await scraper.human_scroll(mock_page, scroll_count=2)

        assert mock_page.mouse.wheel.call_count == 2

    @pytest.mark.asyncio
    async def test_handle_cookie_consent(self):
        """handle_cookie_consent should click consent buttons if present."""
        manager = MagicMock()
        scraper = ConcreteScraper(browser_manager=manager)

        # Create a proper async mock for the button
        mock_button = AsyncMock()
        mock_button.is_visible.return_value = True

        # Mock the page with proper locator chain
        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.first = mock_button
        mock_page.locator.return_value = mock_locator

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await scraper.handle_cookie_consent(mock_page)

        assert result is True
        mock_button.click.assert_awaited_once()


class TestRetryLogic:
    """Tests for retry logic with tenacity."""

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """Should retry on failure up to max_retries."""
        manager = MagicMock()
        config = ScraperConfig(max_retries=3, retry_delay=0.01)
        scraper = ConcreteScraper(browser_manager=manager, config=config)

        call_count = 0

        async def failing_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"

        result = await scraper.with_retry(failing_operation)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhausted(self):
        """Should raise after max_retries exhausted."""
        manager = MagicMock()
        config = ScraperConfig(max_retries=2, retry_delay=0.01)
        scraper = ConcreteScraper(browser_manager=manager, config=config)

        async def always_fails():
            raise Exception("Always fails")

        with pytest.raises(Exception, match="Always fails"):
            await scraper.with_retry(always_fails)


class TestRateLimiting:
    """Tests for rate limiting."""

    @pytest.mark.asyncio
    async def test_rate_limiter_delays_requests(self):
        """Rate limiter should space out requests."""
        manager = MagicMock()
        config = ScraperConfig(rate_limit_per_minute=60)  # 1 per second
        scraper = ConcreteScraper(browser_manager=manager, config=config)

        # Make two requests in quick succession
        start = asyncio.get_event_loop().time()
        await scraper.check_rate_limit()
        await scraper.check_rate_limit()
        elapsed = asyncio.get_event_loop().time() - start

        # Second request should have been delayed
        assert elapsed >= 0.9  # Allow some tolerance

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_spaced_requests(self):
        """Rate limiter should not delay already spaced requests."""
        manager = MagicMock()
        config = ScraperConfig(rate_limit_per_minute=60)
        scraper = ConcreteScraper(browser_manager=manager, config=config)

        await scraper.check_rate_limit()
        await asyncio.sleep(1.1)  # Wait longer than rate limit interval

        start = asyncio.get_event_loop().time()
        await scraper.check_rate_limit()
        elapsed = asyncio.get_event_loop().time() - start

        # Should not have been delayed
        assert elapsed < 0.1
