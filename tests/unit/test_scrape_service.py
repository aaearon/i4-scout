"""Unit tests for ScrapeService."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from i4_scout.models.db_models import Base
from i4_scout.models.pydantic_models import (
    OptionConfig,
    OptionsConfig,
    ScrapeProgress,
    ScrapeResult,
    Source,
)
from i4_scout.services.scrape_service import ScrapeService


@pytest.fixture
def in_memory_session():
    """Create an in-memory SQLite session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def options_config():
    """Sample options configuration for testing."""
    return OptionsConfig(
        required=[OptionConfig(name="HUD")],
        nice_to_have=[OptionConfig(name="Laser Light")],
        dealbreakers=["Accident damage"],
    )


@pytest.fixture
def scrape_service(in_memory_session, options_config):
    """Create a ScrapeService with an in-memory database."""
    return ScrapeService(in_memory_session, options_config)


class TestScrapeServiceInit:
    """Tests for ScrapeService initialization."""

    def test_init(self, in_memory_session, options_config):
        """Should initialize with session and options config."""
        service = ScrapeService(in_memory_session, options_config)
        assert service._session is in_memory_session
        assert service._options_config is options_config


class TestScrapeServiceRunScrape:
    """Tests for ScrapeService.run_scrape()."""

    @pytest.mark.asyncio
    async def test_run_scrape_returns_scrape_result(self, scrape_service):
        """Should return ScrapeResult from scraping."""
        # Mock the scraper to return empty results (no actual network calls)
        with patch.object(scrape_service, '_create_scraper') as mock_create:
            mock_scraper = AsyncMock()
            mock_scraper.scrape_search_page = AsyncMock(return_value=[])
            mock_scraper.random_delay = AsyncMock()
            mock_create.return_value = mock_scraper

            with patch.object(scrape_service, '_create_browser_context') as mock_browser:
                mock_browser.return_value.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock()))
                mock_browser.return_value.__aexit__ = AsyncMock(return_value=None)

                result = await scrape_service.run_scrape(
                    source=Source.AUTOSCOUT24_DE,
                    max_pages=1,
                )

        assert isinstance(result, ScrapeResult)
        assert result.total_found == 0
        assert result.new_listings == 0

    @pytest.mark.asyncio
    async def test_run_scrape_with_progress_callback(self, scrape_service):
        """Should call progress callback during scraping."""
        progress_updates = []

        def capture_progress(progress: ScrapeProgress):
            progress_updates.append(progress)

        with patch.object(scrape_service, '_create_scraper') as mock_create:
            mock_scraper = AsyncMock()
            mock_scraper.scrape_search_page = AsyncMock(return_value=[])
            mock_scraper.random_delay = AsyncMock()
            mock_create.return_value = mock_scraper

            with patch.object(scrape_service, '_create_browser_context') as mock_browser:
                mock_browser.return_value.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock()))
                mock_browser.return_value.__aexit__ = AsyncMock(return_value=None)

                await scrape_service.run_scrape(
                    source=Source.AUTOSCOUT24_DE,
                    max_pages=2,
                    progress_callback=capture_progress,
                )

        # Should have at least one progress update per page attempted
        assert len(progress_updates) >= 1

    @pytest.mark.asyncio
    async def test_run_scrape_processes_listings(self, scrape_service):
        """Should process listings from search page."""
        # Mock listing data returned from scraper
        mock_listing = {
            "url": "https://www.autoscout24.de/angebote/test-123",
            "title": "BMW i4 eDrive40",
            "price": 45000,
            "external_id": "test-123",
        }

        mock_detail = MagicMock()
        mock_detail.options_list = ["HUD", "Laser Light"]
        mock_detail.description = "Great car with HUD"
        mock_detail.location_city = "Berlin"
        mock_detail.location_zip = "10115"
        mock_detail.location_country = "DE"
        mock_detail.dealer_name = "Test Dealer"
        mock_detail.dealer_type = "dealer"

        with patch.object(scrape_service, '_create_scraper') as mock_create:
            mock_scraper = AsyncMock()
            # Return one listing on first page, empty on second
            mock_scraper.scrape_search_page = AsyncMock(
                side_effect=[[mock_listing], []]
            )
            mock_scraper.scrape_listing_detail = AsyncMock(return_value=mock_detail)
            mock_scraper.random_delay = AsyncMock()
            mock_create.return_value = mock_scraper

            with patch.object(scrape_service, '_create_browser_context') as mock_browser:
                mock_browser.return_value.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock()))
                mock_browser.return_value.__aexit__ = AsyncMock(return_value=None)

                result = await scrape_service.run_scrape(
                    source=Source.AUTOSCOUT24_DE,
                    max_pages=2,
                )

        assert result.total_found == 1
        assert result.new_listings == 1
        assert result.fetched_details == 1


class TestScrapeServiceHelpers:
    """Tests for ScrapeService helper methods."""

    def test_get_scraper_class_de(self, scrape_service):
        """Should return correct scraper class for DE."""
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper
        cls = scrape_service._get_scraper_class(Source.AUTOSCOUT24_DE)
        assert cls is AutoScout24DEScraper

    def test_get_scraper_class_nl(self, scrape_service):
        """Should return correct scraper class for NL."""
        from i4_scout.scrapers.autoscout24_nl import AutoScout24NLScraper
        cls = scrape_service._get_scraper_class(Source.AUTOSCOUT24_NL)
        assert cls is AutoScout24NLScraper

    def test_get_scraper_class_unsupported(self, scrape_service):
        """Should raise error for unsupported source."""
        with pytest.raises(ValueError, match="No scraper available"):
            scrape_service._get_scraper_class(Source.MOBILE_DE)
