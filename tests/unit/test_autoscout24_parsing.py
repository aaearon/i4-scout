"""Unit tests for AutoScout24 HTML parsing - TDD approach."""

from pathlib import Path

import pytest

# Import will fail until we implement the scraper
# from car_scraper.scrapers.autoscout24_base import AutoScout24BaseScraper


@pytest.fixture
def de_search_html() -> str:
    """Load German search results HTML fixture."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "autoscout24_de_search.html"
    return fixture_path.read_text()


@pytest.fixture
def de_detail_html() -> str:
    """Load German detail page HTML fixture."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "autoscout24_de_detail.html"
    return fixture_path.read_text()


@pytest.fixture
def nl_search_html() -> str:
    """Load Dutch search results HTML fixture."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "autoscout24_nl_search.html"
    return fixture_path.read_text()


@pytest.fixture
def nl_detail_html() -> str:
    """Load Dutch detail page HTML fixture."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "autoscout24_nl_detail.html"
    return fixture_path.read_text()


class TestAutoScout24SearchParsing:
    """Tests for search results page parsing."""

    def test_parse_listing_cards_extracts_expected_count(self, de_search_html: str) -> None:
        """Search results should contain at least 10 listings."""
        from car_scraper.scrapers.autoscout24_de import AutoScout24DEScraper

        listings = AutoScout24DEScraper.parse_listing_cards_sync(de_search_html)

        assert len(listings) >= 10, "Expected at least 10 listings from search results"

    def test_parse_listing_cards_extracts_external_id(self, de_search_html: str) -> None:
        """Each listing should have a GUID extracted from data-guid."""
        from car_scraper.scrapers.autoscout24_de import AutoScout24DEScraper

        listings = AutoScout24DEScraper.parse_listing_cards_sync(de_search_html)

        assert len(listings) > 0
        first_listing = listings[0]
        assert "external_id" in first_listing
        assert first_listing["external_id"] == "6bbf18bf-3ab9-4fce-9148-90d4ed48e8e4"

    def test_parse_listing_cards_extracts_url(self, de_search_html: str) -> None:
        """Each listing should have a valid URL."""
        from car_scraper.scrapers.autoscout24_de import AutoScout24DEScraper

        listings = AutoScout24DEScraper.parse_listing_cards_sync(de_search_html)

        assert len(listings) > 0
        first_listing = listings[0]
        assert "url" in first_listing
        assert first_listing["url"].startswith("https://www.autoscout24.de/angebote/")

    def test_parse_listing_cards_extracts_price_from_data_attr(self, de_search_html: str) -> None:
        """Price should be extracted from data-price attribute as integer (EUR)."""
        from car_scraper.scrapers.autoscout24_de import AutoScout24DEScraper

        listings = AutoScout24DEScraper.parse_listing_cards_sync(de_search_html)

        first_listing = listings[0]
        assert "price" in first_listing
        assert first_listing["price"] == 34990  # EUR, not cents
        assert isinstance(first_listing["price"], int)

    def test_parse_listing_cards_extracts_mileage(self, de_search_html: str) -> None:
        """Mileage should be extracted from data-mileage attribute."""
        from car_scraper.scrapers.autoscout24_de import AutoScout24DEScraper

        listings = AutoScout24DEScraper.parse_listing_cards_sync(de_search_html)

        first_listing = listings[0]
        assert "mileage_km" in first_listing
        assert first_listing["mileage_km"] == 790
        assert isinstance(first_listing["mileage_km"], int)

    def test_parse_listing_cards_extracts_first_registration(self, de_search_html: str) -> None:
        """First registration should be extracted and formatted as MM/YYYY."""
        from car_scraper.scrapers.autoscout24_de import AutoScout24DEScraper

        listings = AutoScout24DEScraper.parse_listing_cards_sync(de_search_html)

        first_listing = listings[0]
        assert "first_registration" in first_listing
        # data-first-registration="08-2022" should become "08/2022"
        assert first_listing["first_registration"] == "08/2022"

    def test_parse_listing_cards_extracts_title(self, de_search_html: str) -> None:
        """Title should be extracted from h2 element."""
        from car_scraper.scrapers.autoscout24_de import AutoScout24DEScraper

        listings = AutoScout24DEScraper.parse_listing_cards_sync(de_search_html)

        first_listing = listings[0]
        assert "title" in first_listing
        assert "BMW i4" in first_listing["title"]

    def test_parse_listing_cards_handles_new_vehicles(self, de_search_html: str) -> None:
        """New vehicles have data-first-registration='new' - should be handled."""
        from car_scraper.scrapers.autoscout24_de import AutoScout24DEScraper

        listings = AutoScout24DEScraper.parse_listing_cards_sync(de_search_html)

        # Find listing with 'new' registration (GUID: 5e16c831-2d85-45e9-afff-aba3f2521159)
        new_listing = next(
            (l for l in listings if l.get("external_id") == "5e16c831-2d85-45e9-afff-aba3f2521159"),
            None
        )
        assert new_listing is not None
        # Should return None or empty string for 'new' vehicles
        assert new_listing.get("first_registration") in (None, "", "new")

    def test_nl_parse_listing_cards_extracts_expected_count(self, nl_search_html: str) -> None:
        """Dutch search results should also parse correctly."""
        from car_scraper.scrapers.autoscout24_nl import AutoScout24NLScraper

        listings = AutoScout24NLScraper.parse_listing_cards_sync(nl_search_html)

        assert len(listings) >= 5, "Expected at least 5 listings from NL search results"


class TestAutoScout24DetailParsing:
    """Tests for detail page parsing."""

    def test_parse_listing_detail_extracts_options(self, de_detail_html: str) -> None:
        """Options should be extracted from detail page."""
        from car_scraper.scrapers.autoscout24_de import AutoScout24DEScraper

        options = AutoScout24DEScraper.parse_options_sync(de_detail_html)

        assert len(options) > 0, "Expected at least some options"
        # Check for known options from the fixture
        assert "Einparkhilfe" in options
        assert "Sitzheizung" in options

    def test_parse_listing_detail_extracts_options_from_all_categories(
        self, de_detail_html: str
    ) -> None:
        """Options from all categories (Komfort, Sicherheit, etc.) should be included."""
        from car_scraper.scrapers.autoscout24_de import AutoScout24DEScraper

        options = AutoScout24DEScraper.parse_options_sync(de_detail_html)

        # Check for options from different categories
        assert any("ABS" in opt for opt in options), "Safety option ABS missing"
        assert any("Bordcomputer" in opt for opt in options), "Entertainment option missing"

    def test_parse_listing_detail_handles_missing_sections(self, de_search_html: str) -> None:
        """Parser should handle pages without equipment sections gracefully."""
        from car_scraper.scrapers.autoscout24_de import AutoScout24DEScraper

        # Search page doesn't have detail sections
        options = AutoScout24DEScraper.parse_options_sync(de_search_html)

        # Should return empty list, not crash
        assert isinstance(options, list)

    def test_nl_parse_listing_detail_extracts_options(self, nl_detail_html: str) -> None:
        """Dutch detail page options should also parse correctly."""
        from car_scraper.scrapers.autoscout24_nl import AutoScout24NLScraper

        options = AutoScout24NLScraper.parse_options_sync(nl_detail_html)

        assert len(options) > 0, "Expected at least some options from NL detail"

    def test_parse_description_extracts_text(self, de_detail_html: str) -> None:
        """Description (Fahrzeugbeschreibung) should be extracted from detail page."""
        from car_scraper.scrapers.autoscout24_de import AutoScout24DEScraper

        description = AutoScout24DEScraper.parse_description_sync(de_detail_html)

        assert description is not None, "Description should not be None"
        assert len(description) > 50, "Description should have substantial content"
        # Check for known content from the fixture (sellerNotesSection)
        assert "Sitzbezug" in description or "Ablagenpaket" in description

    def test_parse_description_handles_missing_section(self, de_search_html: str) -> None:
        """Parser should handle pages without description section gracefully."""
        from car_scraper.scrapers.autoscout24_de import AutoScout24DEScraper

        # Search page doesn't have description section
        description = AutoScout24DEScraper.parse_description_sync(de_search_html)

        # Should return None, not crash
        assert description is None or isinstance(description, str)


class TestAutoScout24SearchURL:
    """Tests for search URL generation."""

    def test_get_search_url_includes_pagination(self) -> None:
        """Search URL should include page parameter."""
        from car_scraper.scrapers.autoscout24_de import AutoScout24DEScraper

        url_page1 = AutoScout24DEScraper.get_search_url_static(page=1)
        url_page2 = AutoScout24DEScraper.get_search_url_static(page=2)

        assert "page=1" in url_page1 or url_page1.endswith("/1")
        assert "page=2" in url_page2 or url_page2.endswith("/2")
        assert url_page1 != url_page2

    def test_de_search_url_uses_correct_domain(self) -> None:
        """German scraper should use autoscout24.de domain."""
        from car_scraper.scrapers.autoscout24_de import AutoScout24DEScraper

        url = AutoScout24DEScraper.get_search_url_static(page=1)

        assert "autoscout24.de" in url

    def test_nl_search_url_uses_correct_domain(self) -> None:
        """Dutch scraper should use autoscout24.nl domain."""
        from car_scraper.scrapers.autoscout24_nl import AutoScout24NLScraper

        url = AutoScout24NLScraper.get_search_url_static(page=1)

        assert "autoscout24.nl" in url
