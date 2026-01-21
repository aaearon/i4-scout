"""Service layer for scraping operations."""

import logging
import re
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from i4_scout.database.repository import ListingRepository
from i4_scout.matching.option_matcher import match_options
from i4_scout.matching.scorer import calculate_score
from i4_scout.models.pydantic_models import (
    ListingCreate,
    OptionsConfig,
    ScrapeProgress,
    ScrapeResult,
    SearchFilters,
    Source,
)
from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper
from i4_scout.scrapers.autoscout24_nl import AutoScout24NLScraper
from i4_scout.scrapers.browser import BrowserConfig, BrowserManager

logger = logging.getLogger(__name__)


def parse_first_registration(value: str | None) -> date | None:
    """Parse first registration string to date.

    Handles formats like:
    - "MM/YYYY" (e.g., "12/2024")
    - "MM-YYYY" (e.g., "12-2024")
    - "YYYY" (e.g., "2024")
    - "new" or other strings → None

    Returns:
        date with day=1 for the given month/year, or None if unparseable.
    """
    if not value or value.lower() == "new":
        return None

    # Try MM/YYYY or MM-YYYY format
    match = re.match(r"^(\d{1,2})[/-](\d{4})$", value)
    if match:
        month = int(match.group(1))
        year = int(match.group(2))
        if 1 <= month <= 12 and 2000 <= year <= 2100:
            return date(year, month, 1)

    # Try YYYY format
    match = re.match(r"^(\d{4})$", value)
    if match:
        year = int(match.group(1))
        if 2000 <= year <= 2100:
            return date(year, 1, 1)

    return None


class ScrapeService:
    """Service for scraping operations.

    Encapsulates the scraping logic previously in cli.py, providing
    a clean interface for running scrapes with progress callbacks.
    """

    def __init__(self, session: Session, options_config: OptionsConfig) -> None:
        """Initialize with database session and options config.

        Args:
            session: SQLAlchemy session instance.
            options_config: Configuration for option matching.
        """
        self._session = session
        self._options_config = options_config
        self._repo = ListingRepository(session)

    async def run_scrape(
        self,
        source: Source,
        max_pages: int,
        search_filters: SearchFilters | None = None,
        headless: bool = True,
        use_cache: bool = True,
        progress_callback: Callable[[ScrapeProgress], None] | None = None,
    ) -> ScrapeResult:
        """Run the scraping process.

        Args:
            source: The source to scrape.
            max_pages: Maximum pages to scrape.
            search_filters: Optional search filters to apply.
            headless: Run browser in headless mode.
            use_cache: Whether to use HTML caching.
            progress_callback: Optional callback for progress updates.

        Returns:
            ScrapeResult with counts of processed listings.
        """
        total_found = 0
        new_count = 0
        updated_count = 0
        skipped_count = 0
        fetched_count = 0

        async with self._create_browser_context(headless) as (browser, page):
            scraper = self._create_scraper(source, browser)

            for page_num in range(1, max_pages + 1):
                # Emit progress update at start of page
                if progress_callback:
                    progress_callback(ScrapeProgress(
                        page=page_num,
                        total_pages=max_pages,
                        listings_found=total_found,
                        new_count=new_count,
                        updated_count=updated_count,
                        skipped_count=skipped_count,
                        current_listing=None,
                    ))

                try:
                    listings_data = await scraper.scrape_search_page(
                        page, page_num, search_filters, use_cache=use_cache
                    )

                    if not listings_data:
                        # No more listings, stop scraping
                        break

                    # Process each listing
                    for listing_data in listings_data:
                        result = await self._process_listing(
                            scraper, page, listing_data, source, use_cache
                        )

                        total_found += 1
                        if result["status"] == "new":
                            new_count += 1
                            fetched_count += 1
                        elif result["status"] == "updated":
                            updated_count += 1
                            fetched_count += 1
                        elif result["status"] == "skipped":
                            skipped_count += 1

                        # Emit progress with current listing
                        if progress_callback:
                            progress_callback(ScrapeProgress(
                                page=page_num,
                                total_pages=max_pages,
                                listings_found=total_found,
                                new_count=new_count,
                                updated_count=updated_count,
                                skipped_count=skipped_count,
                                current_listing=listing_data.get("title"),
                            ))

                    await scraper.random_delay()

                except Exception:
                    logger.exception("Error scraping page %d, continuing to next page", page_num)
                    continue

        return ScrapeResult(
            total_found=total_found,
            new_listings=new_count,
            updated_listings=updated_count,
            skipped_unchanged=skipped_count,
            fetched_details=fetched_count,
        )

    async def _process_listing(
        self,
        scraper: Any,
        page: Any,
        listing_data: dict[str, Any],
        source: Source,
        use_cache: bool,
    ) -> dict[str, str]:
        """Process a single listing from search results.

        Args:
            scraper: Scraper instance.
            page: Browser page.
            listing_data: Raw listing data from search.
            source: Source being scraped.
            use_cache: Whether to use caching.

        Returns:
            Dict with "status" key: "new", "updated", or "skipped".
        """
        url = listing_data.get("url")
        price = listing_data.get("price")

        # Check if we can skip the detail fetch
        if url and self._repo.listing_exists_with_price(url, price):
            # Update last_seen_at for the existing listing
            existing = self._repo.get_listing_by_url(url)
            if existing:
                self._repo.update_listing(existing.id)
            return {"status": "skipped"}

        # Get detail page for options, description, and location/dealer info
        options_list = []
        description = None
        location_city = None
        location_zip = None
        location_country = None
        dealer_name = None
        dealer_type = None
        if url:
            try:
                detail = await scraper.scrape_listing_detail(page, url, use_cache=use_cache)
                options_list = detail.options_list
                description = detail.description
                location_city = detail.location_city
                location_zip = detail.location_zip
                location_country = detail.location_country
                dealer_name = detail.dealer_name
                dealer_type = detail.dealer_type
            except Exception:
                logger.exception("Error fetching detail page %s", url)

        # Combine title and description for text search
        title = listing_data.get("title", "")
        searchable_text = title
        if description:
            searchable_text = f"{title}\n{description}"

        # Match options
        match_result = match_options(options_list, self._options_config, searchable_text)
        scored_result = calculate_score(match_result, self._options_config)

        # Create listing data
        first_reg_str = listing_data.get("first_registration")
        first_reg_date = parse_first_registration(first_reg_str)

        create_data = ListingCreate(
            source=source,
            external_id=listing_data.get("external_id"),
            url=url or "",
            title=title,
            price=listing_data.get("price"),
            mileage_km=listing_data.get("mileage_km"),
            first_registration=first_reg_date,
            description=description,
            location_city=location_city,
            location_zip=location_zip,
            location_country=location_country,
            dealer_name=dealer_name,
            dealer_type=dealer_type,
            match_score=scored_result.score,
            is_qualified=scored_result.is_qualified,
        )

        # Upsert to database
        listing, created = self._repo.upsert_listing(create_data)

        if not created:
            # Clear existing scrape-sourced options (preserve PDF-sourced options)
            self._repo.clear_listing_options(listing.id, source="scrape")

        # Store matched options
        all_matched = match_result.matched_required + match_result.matched_nice_to_have
        for option_name in all_matched:
            option, _ = self._repo.get_or_create_option(option_name)
            self._repo.add_option_to_listing(listing.id, option.id)

        return {"status": "new" if created else "updated"}

    def _get_scraper_class(self, source: Source) -> type:
        """Get the scraper class for a source.

        Args:
            source: Source to get scraper for.

        Returns:
            Scraper class.

        Raises:
            ValueError: If no scraper available for source.
        """
        scrapers = {
            Source.AUTOSCOUT24_DE: AutoScout24DEScraper,
            Source.AUTOSCOUT24_NL: AutoScout24NLScraper,
        }
        if source not in scrapers:
            raise ValueError(f"No scraper available for {source.value}")
        return scrapers[source]

    def _create_scraper(self, source: Source, browser: BrowserManager) -> Any:
        """Create a scraper instance.

        Args:
            source: Source to create scraper for.
            browser: Browser manager instance.

        Returns:
            Scraper instance.
        """
        scraper_class = self._get_scraper_class(source)
        return scraper_class(browser)

    @asynccontextmanager
    async def _create_browser_context(
        self, headless: bool = True
    ) -> Any:  # AsyncGenerator[tuple[BrowserManager, Any], None]
        """Create a browser context for scraping.

        Args:
            headless: Run browser in headless mode.

        Yields:
            Tuple of (browser_manager, page).
        """
        browser_config = BrowserConfig(headless=headless)
        async with BrowserManager(browser_config) as browser:
            page = await browser.get_page()
            yield browser, page
