"""Unit tests for Pydantic models."""

import pytest
from datetime import date, datetime
from pydantic import ValidationError

from i4_scout.models.pydantic_models import (
    ListingCreate,
    ListingRead,
    MatchResult,
    OptionConfig,
    OptionsConfig,
    ScrapedListing,
    ScrapeProgress,
    ScrapeResult,
    ScrapeSession,
    ScrapeStatus,
    SearchFilters,
    Source,
)


class TestSource:
    """Tests for Source enum."""

    def test_source_values(self):
        assert Source.AUTOSCOUT24_DE.value == "autoscout24_de"
        assert Source.AUTOSCOUT24_NL.value == "autoscout24_nl"
        assert Source.MOBILE_DE.value == "mobile_de"

    def test_source_from_string(self):
        assert Source("autoscout24_de") == Source.AUTOSCOUT24_DE


class TestOptionConfig:
    """Tests for OptionConfig model."""

    def test_minimal_option(self):
        option = OptionConfig(name="Test Option")
        assert option.name == "Test Option"
        assert option.aliases == []
        assert option.category is None
        assert option.is_bundle is False

    def test_full_option(self):
        option = OptionConfig(
            name="M Sport Package",
            aliases=["M Sportpaket", "M Sport"],
            category="exterior",
            is_bundle=True,
            bundle_contents=["M brakes", "M steering wheel"],
        )
        assert option.name == "M Sport Package"
        assert len(option.aliases) == 2
        assert option.is_bundle is True
        assert len(option.bundle_contents) == 2

    def test_option_is_frozen(self):
        option = OptionConfig(name="Test")
        with pytest.raises(ValidationError):
            option.name = "Changed"  # type: ignore


class TestOptionsConfig:
    """Tests for OptionsConfig model."""

    def test_empty_config(self):
        config = OptionsConfig()
        assert config.required == []
        assert config.nice_to_have == []
        assert config.dealbreakers == []

    def test_full_config(self):
        config = OptionsConfig(
            required=[OptionConfig(name="HUD")],
            nice_to_have=[OptionConfig(name="Laser Light")],
            dealbreakers=["Accident damage"],
        )
        assert len(config.required) == 1
        assert len(config.nice_to_have) == 1
        assert len(config.dealbreakers) == 1


class TestScrapedListing:
    """Tests for ScrapedListing model."""

    def test_minimal_listing(self):
        listing = ScrapedListing(
            source=Source.AUTOSCOUT24_DE,
            url="https://www.autoscout24.de/angebote/123",
            title="BMW i4 eDrive40",
        )
        assert listing.source == Source.AUTOSCOUT24_DE
        assert listing.price is None
        assert listing.options_list == []

    def test_full_listing(self):
        listing = ScrapedListing(
            source=Source.AUTOSCOUT24_NL,
            external_id="ABC123",
            url="https://www.autoscout24.nl/aanbod/123",
            title="BMW i4 eDrive40 High Executive",
            price=4500000,  # 45,000 EUR in cents
            price_text="€ 45.000",
            mileage_km=15000,
            year=2023,
            first_registration="03/2023",
            location_city="Amsterdam",
            location_country="NL",
            dealer_name="BMW Dealer Amsterdam",
            dealer_type="dealer",
            options_list=["HUD", "Laser Light", "Parking Assistant"],
        )
        assert listing.price == 4500000
        assert listing.year == 2023
        assert len(listing.options_list) == 3

    def test_invalid_year(self):
        with pytest.raises(ValidationError):
            ScrapedListing(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com",
                title="Test",
                year=2015,  # Too old
            )

    def test_invalid_price(self):
        with pytest.raises(ValidationError):
            ScrapedListing(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com",
                title="Test",
                price=-100,  # Negative
            )


class TestListingCreate:
    """Tests for ListingCreate model."""

    def test_create_listing(self):
        listing = ListingCreate(
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com/123",
            title="BMW i4",
            price=4000000,
            match_score=85.5,
            is_qualified=True,
        )
        assert listing.match_score == 85.5
        assert listing.is_qualified is True

    def test_default_values(self):
        listing = ListingCreate(
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com",
            title="Test",
        )
        assert listing.match_score == 0.0
        assert listing.is_qualified is False
        assert listing.photo_urls == []


class TestListingRead:
    """Tests for ListingRead model."""

    def test_listing_read(self):
        now = datetime.utcnow()
        listing = ListingRead(
            id=1,
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com",
            title="Test",
            first_seen_at=now,
            last_seen_at=now,
            matched_options=["HUD", "Parking Assistant"],
        )
        assert listing.id == 1
        assert len(listing.matched_options) == 2


class TestScrapeSession:
    """Tests for ScrapeSession model."""

    def test_new_session(self):
        session = ScrapeSession(source=Source.AUTOSCOUT24_DE)
        assert session.status == ScrapeStatus.PENDING
        assert session.listings_found == 0

    def test_completed_session(self):
        session = ScrapeSession(
            id=1,
            source=Source.AUTOSCOUT24_NL,
            status=ScrapeStatus.COMPLETED,
            listings_found=50,
            listings_new=10,
            pages_scraped=5,
        )
        assert session.status == ScrapeStatus.COMPLETED
        assert session.listings_found == 50


class TestMatchResult:
    """Tests for MatchResult model."""

    def test_qualified_result(self):
        result = MatchResult(
            matched_required=["HUD", "Parking Assistant"],
            matched_nice_to_have=["Laser Light"],
            missing_required=[],
            score=95.0,
            is_qualified=True,
        )
        assert result.is_qualified is True
        assert result.score == 95.0
        assert result.has_dealbreaker is False

    def test_disqualified_by_dealbreaker(self):
        result = MatchResult(
            matched_required=["HUD"],
            has_dealbreaker=True,
            dealbreaker_found="Accident damage",
            is_qualified=False,
        )
        assert result.is_qualified is False
        assert result.dealbreaker_found == "Accident damage"


class TestSearchFilters:
    """Tests for SearchFilters model."""

    def test_empty_filters(self):
        """Should create filters with all None values by default."""
        filters = SearchFilters()
        assert filters.price_max_eur is None
        assert filters.mileage_max_km is None
        assert filters.year_min is None
        assert filters.year_max is None
        assert filters.countries is None

    def test_full_filters(self):
        """Should accept all filter values."""
        filters = SearchFilters(
            price_max_eur=55000,
            mileage_max_km=50000,
            year_min=2023,
            year_max=2025,
            countries=["D", "NL", "B"],
        )
        assert filters.price_max_eur == 55000
        assert filters.mileage_max_km == 50000
        assert filters.year_min == 2023
        assert filters.year_max == 2025
        assert filters.countries == ["D", "NL", "B"]

    def test_partial_filters(self):
        """Should allow partial filter specification."""
        filters = SearchFilters(
            price_max_eur=45000,
            year_min=2024,
        )
        assert filters.price_max_eur == 45000
        assert filters.year_min == 2024
        assert filters.mileage_max_km is None
        assert filters.countries is None

    def test_single_country(self):
        """Should accept single country in list."""
        filters = SearchFilters(countries=["D"])
        assert filters.countries == ["D"]

    def test_filters_are_optional(self):
        """All filter fields should be optional."""
        # Should not raise
        SearchFilters()
        SearchFilters(price_max_eur=None)
        SearchFilters(countries=None)


class TestScrapeProgress:
    """Tests for ScrapeProgress model."""

    def test_scrape_progress_minimal(self):
        """Should create progress with required fields."""
        progress = ScrapeProgress(
            page=1,
            total_pages=10,
            listings_found=20,
            new_count=5,
            updated_count=10,
            skipped_count=5,
        )
        assert progress.page == 1
        assert progress.total_pages == 10
        assert progress.listings_found == 20
        assert progress.new_count == 5
        assert progress.updated_count == 10
        assert progress.skipped_count == 5
        assert progress.current_listing is None

    def test_scrape_progress_with_current_listing(self):
        """Should accept current_listing optional field."""
        progress = ScrapeProgress(
            page=3,
            total_pages=10,
            listings_found=45,
            new_count=10,
            updated_count=20,
            skipped_count=15,
            current_listing="BMW i4 eDrive40 M Sport",
        )
        assert progress.current_listing == "BMW i4 eDrive40 M Sport"


class TestScrapeResult:
    """Tests for ScrapeResult model."""

    def test_scrape_result(self):
        """Should create result with all counts."""
        result = ScrapeResult(
            total_found=100,
            new_listings=25,
            updated_listings=50,
            skipped_unchanged=25,
            fetched_details=75,
        )
        assert result.total_found == 100
        assert result.new_listings == 25
        assert result.updated_listings == 50
        assert result.skipped_unchanged == 25
        assert result.fetched_details == 75

    def test_scrape_result_empty(self):
        """Should handle zero counts."""
        result = ScrapeResult(
            total_found=0,
            new_listings=0,
            updated_listings=0,
            skipped_unchanged=0,
            fetched_details=0,
        )
        assert result.total_found == 0
