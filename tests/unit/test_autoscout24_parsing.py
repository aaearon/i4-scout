"""Unit tests for AutoScout24 HTML parsing - TDD approach."""

from pathlib import Path

import pytest

# Import will fail until we implement the scraper
# from i4_scout.scrapers.autoscout24_base import AutoScout24BaseScraper


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
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        listings = AutoScout24DEScraper.parse_listing_cards_sync(de_search_html)

        assert len(listings) >= 10, "Expected at least 10 listings from search results"

    def test_parse_listing_cards_extracts_external_id(self, de_search_html: str) -> None:
        """Each listing should have a GUID extracted from data-guid."""
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        listings = AutoScout24DEScraper.parse_listing_cards_sync(de_search_html)

        assert len(listings) > 0
        first_listing = listings[0]
        assert "external_id" in first_listing
        assert first_listing["external_id"] == "6bbf18bf-3ab9-4fce-9148-90d4ed48e8e4"

    def test_parse_listing_cards_extracts_url(self, de_search_html: str) -> None:
        """Each listing should have a valid URL."""
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        listings = AutoScout24DEScraper.parse_listing_cards_sync(de_search_html)

        assert len(listings) > 0
        first_listing = listings[0]
        assert "url" in first_listing
        assert first_listing["url"].startswith("https://www.autoscout24.de/angebote/")

    def test_parse_listing_cards_extracts_price_from_data_attr(self, de_search_html: str) -> None:
        """Price should be extracted from data-price attribute as integer (EUR)."""
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        listings = AutoScout24DEScraper.parse_listing_cards_sync(de_search_html)

        first_listing = listings[0]
        assert "price" in first_listing
        assert first_listing["price"] == 34990  # EUR, not cents
        assert isinstance(first_listing["price"], int)

    def test_parse_listing_cards_extracts_mileage(self, de_search_html: str) -> None:
        """Mileage should be extracted from data-mileage attribute."""
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        listings = AutoScout24DEScraper.parse_listing_cards_sync(de_search_html)

        first_listing = listings[0]
        assert "mileage_km" in first_listing
        assert first_listing["mileage_km"] == 790
        assert isinstance(first_listing["mileage_km"], int)

    def test_parse_listing_cards_extracts_first_registration(self, de_search_html: str) -> None:
        """First registration should be extracted and formatted as MM/YYYY."""
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        listings = AutoScout24DEScraper.parse_listing_cards_sync(de_search_html)

        first_listing = listings[0]
        assert "first_registration" in first_listing
        # data-first-registration="08-2022" should become "08/2022"
        assert first_listing["first_registration"] == "08/2022"

    def test_parse_listing_cards_extracts_title(self, de_search_html: str) -> None:
        """Title should be extracted from h2 element."""
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        listings = AutoScout24DEScraper.parse_listing_cards_sync(de_search_html)

        first_listing = listings[0]
        assert "title" in first_listing
        assert "BMW i4" in first_listing["title"]

    def test_parse_listing_cards_handles_new_vehicles(self, de_search_html: str) -> None:
        """New vehicles have data-first-registration='new' - should be handled."""
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        listings = AutoScout24DEScraper.parse_listing_cards_sync(de_search_html)

        # Find listing with 'new' registration (GUID: 5e16c831-2d85-45e9-afff-aba3f2521159)
        new_listing = next(
            (item for item in listings if item.get("external_id") == "5e16c831-2d85-45e9-afff-aba3f2521159"),
            None
        )
        assert new_listing is not None
        # Should return None or empty string for 'new' vehicles
        assert new_listing.get("first_registration") in (None, "", "new")

    def test_nl_parse_listing_cards_extracts_expected_count(self, nl_search_html: str) -> None:
        """Dutch search results should also parse correctly."""
        from i4_scout.scrapers.autoscout24_nl import AutoScout24NLScraper

        listings = AutoScout24NLScraper.parse_listing_cards_sync(nl_search_html)

        assert len(listings) >= 5, "Expected at least 5 listings from NL search results"


class TestAutoScout24DetailParsing:
    """Tests for detail page parsing."""

    def test_parse_listing_detail_extracts_options(self, de_detail_html: str) -> None:
        """Options should be extracted from detail page."""
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        options = AutoScout24DEScraper.parse_options_sync(de_detail_html)

        assert len(options) > 0, "Expected at least some options"
        # Check for known options from the fixture
        assert "Einparkhilfe" in options
        assert "Sitzheizung" in options

    def test_parse_listing_detail_extracts_options_from_all_categories(
        self, de_detail_html: str
    ) -> None:
        """Options from all categories (Komfort, Sicherheit, etc.) should be included."""
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        options = AutoScout24DEScraper.parse_options_sync(de_detail_html)

        # Check for options from different categories
        assert any("ABS" in opt for opt in options), "Safety option ABS missing"
        assert any("Bordcomputer" in opt for opt in options), "Entertainment option missing"

    def test_parse_listing_detail_handles_missing_sections(self, de_search_html: str) -> None:
        """Parser should handle pages without equipment sections gracefully."""
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        # Search page doesn't have detail sections
        options = AutoScout24DEScraper.parse_options_sync(de_search_html)

        # Should return empty list, not crash
        assert isinstance(options, list)

    def test_nl_parse_listing_detail_extracts_options(self, nl_detail_html: str) -> None:
        """Dutch detail page options should also parse correctly."""
        from i4_scout.scrapers.autoscout24_nl import AutoScout24NLScraper

        options = AutoScout24NLScraper.parse_options_sync(nl_detail_html)

        assert len(options) > 0, "Expected at least some options from NL detail"

    def test_parse_description_extracts_text(self, de_detail_html: str) -> None:
        """Description (Fahrzeugbeschreibung) should be extracted from detail page."""
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        description = AutoScout24DEScraper.parse_description_sync(de_detail_html)

        assert description is not None, "Description should not be None"
        assert len(description) > 50, "Description should have substantial content"
        # Check for known content from the fixture (sellerNotesSection)
        assert "Sitzbezug" in description or "Ablagenpaket" in description

    def test_parse_description_handles_missing_section(self, de_search_html: str) -> None:
        """Parser should handle pages without description section gracefully."""
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        # Search page doesn't have description section
        description = AutoScout24DEScraper.parse_description_sync(de_search_html)

        # Should return None, not crash
        assert description is None or isinstance(description, str)


class TestAutoScout24SearchURL:
    """Tests for search URL generation."""

    def test_get_search_url_includes_pagination(self) -> None:
        """Search URL should include page parameter."""
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        url_page1 = AutoScout24DEScraper.get_search_url_static(page=1)
        url_page2 = AutoScout24DEScraper.get_search_url_static(page=2)

        assert "page=1" in url_page1 or url_page1.endswith("/1")
        assert "page=2" in url_page2 or url_page2.endswith("/2")
        assert url_page1 != url_page2

    def test_de_search_url_uses_correct_domain(self) -> None:
        """German scraper should use autoscout24.de domain."""
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        url = AutoScout24DEScraper.get_search_url_static(page=1)

        assert "autoscout24.de" in url

    def test_nl_search_url_uses_correct_domain(self) -> None:
        """Dutch scraper should use autoscout24.nl domain."""
        from i4_scout.scrapers.autoscout24_nl import AutoScout24NLScraper

        url = AutoScout24NLScraper.get_search_url_static(page=1)

        assert "autoscout24.nl" in url


class TestAutoScout24SearchURLWithFilters:
    """Tests for search URL generation with SearchFilters."""

    def test_search_url_with_price_max(self) -> None:
        """Should include priceto parameter when price_max_eur is set."""
        from i4_scout.models.pydantic_models import SearchFilters
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        filters = SearchFilters(price_max_eur=55000)
        url = AutoScout24DEScraper.get_search_url_static(page=1, filters=filters)

        assert "priceto=55000" in url

    def test_search_url_with_mileage_max(self) -> None:
        """Should include kmto parameter when mileage_max_km is set."""
        from i4_scout.models.pydantic_models import SearchFilters
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        filters = SearchFilters(mileage_max_km=50000)
        url = AutoScout24DEScraper.get_search_url_static(page=1, filters=filters)

        assert "kmto=50000" in url

    def test_search_url_with_year_min(self) -> None:
        """Should include fregfrom parameter when year_min is set."""
        from i4_scout.models.pydantic_models import SearchFilters
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        filters = SearchFilters(year_min=2023)
        url = AutoScout24DEScraper.get_search_url_static(page=1, filters=filters)

        assert "fregfrom=2023" in url
        # Should NOT contain old hardcoded value
        assert "fregfrom=2022" not in url

    def test_search_url_with_year_max(self) -> None:
        """Should include fregto parameter when year_max is set."""
        from i4_scout.models.pydantic_models import SearchFilters
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        filters = SearchFilters(year_max=2025)
        url = AutoScout24DEScraper.get_search_url_static(page=1, filters=filters)

        assert "fregto=2025" in url

    def test_search_url_with_countries(self) -> None:
        """Should include cy parameter with URL-encoded countries."""
        from i4_scout.models.pydantic_models import SearchFilters
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        filters = SearchFilters(countries=["D", "NL", "B"])
        url = AutoScout24DEScraper.get_search_url_static(page=1, filters=filters)

        # "D,NL,B" should be URL encoded to "D%2CNL%2CB"
        assert "cy=D%2CNL%2CB" in url or "cy=D,NL,B" in url

    def test_search_url_with_single_country(self) -> None:
        """Should handle single country correctly."""
        from i4_scout.models.pydantic_models import SearchFilters
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        filters = SearchFilters(countries=["D"])
        url = AutoScout24DEScraper.get_search_url_static(page=1, filters=filters)

        assert "cy=D" in url

    def test_search_url_with_all_filters(self) -> None:
        """Should include all filter parameters when all are set."""
        from i4_scout.models.pydantic_models import SearchFilters
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        filters = SearchFilters(
            price_max_eur=55000,
            mileage_max_km=50000,
            year_min=2023,
            year_max=2025,
            countries=["D", "NL"],
        )
        url = AutoScout24DEScraper.get_search_url_static(page=1, filters=filters)

        assert "priceto=55000" in url
        assert "kmto=50000" in url
        assert "fregfrom=2023" in url
        assert "fregto=2025" in url
        # cy parameter should contain both countries
        assert "D" in url and "NL" in url

    def test_search_url_without_filters_uses_defaults(self) -> None:
        """Should use default values when no filters provided."""
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        url = AutoScout24DEScraper.get_search_url_static(page=1)

        # Should still have the basic parameters
        assert "autoscout24.de" in url
        assert "page=1" in url

    def test_search_url_with_empty_filters(self) -> None:
        """Should handle empty SearchFilters gracefully."""
        from i4_scout.models.pydantic_models import SearchFilters
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        filters = SearchFilters()  # All None
        url = AutoScout24DEScraper.get_search_url_static(page=1, filters=filters)

        # Should not include filter params when values are None
        assert "priceto=" not in url
        assert "kmto=" not in url

    def test_nl_search_url_with_filters(self) -> None:
        """Dutch scraper should also handle filters."""
        from i4_scout.models.pydantic_models import SearchFilters
        from i4_scout.scrapers.autoscout24_nl import AutoScout24NLScraper

        filters = SearchFilters(
            price_max_eur=45000,
            countries=["NL", "B"],
        )
        url = AutoScout24NLScraper.get_search_url_static(page=1, filters=filters)

        assert "autoscout24.nl" in url
        assert "priceto=45000" in url
        assert "NL" in url and "B" in url


class TestAutoScout24JsonLdParsing:
    """Tests for JSON-LD structured data extraction."""

    def test_parse_json_ld_extracts_dealer_name(self, de_detail_html: str) -> None:
        """Dealer name should be extracted from JSON-LD offers.offeredBy.name."""
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        result = AutoScout24DEScraper.parse_json_ld_sync(de_detail_html)

        assert result is not None
        assert result["dealer_name"] == "Baum Automobile GmbH & Co. KG"

    def test_parse_json_ld_extracts_dealer_type_as_dealer(self, de_detail_html: str) -> None:
        """Dealer type 'AutoDealer' should be normalized to 'dealer'."""
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        result = AutoScout24DEScraper.parse_json_ld_sync(de_detail_html)

        assert result is not None
        assert result["dealer_type"] == "dealer"

    def test_parse_json_ld_extracts_location_city(self, de_detail_html: str) -> None:
        """Location city should be extracted from address.addressLocality."""
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        result = AutoScout24DEScraper.parse_json_ld_sync(de_detail_html)

        assert result is not None
        assert result["location_city"] == "Bad Neuenahr-Ahrweiler"

    def test_parse_json_ld_extracts_location_zip(self, de_detail_html: str) -> None:
        """Location zip should be extracted from address.postalCode."""
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        result = AutoScout24DEScraper.parse_json_ld_sync(de_detail_html)

        assert result is not None
        assert result["location_zip"] == "53474"

    def test_parse_json_ld_extracts_location_country(self, de_detail_html: str) -> None:
        """Location country should be extracted from address.addressCountry."""
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        result = AutoScout24DEScraper.parse_json_ld_sync(de_detail_html)

        assert result is not None
        assert result["location_country"] == "DE"

    def test_parse_json_ld_works_for_nl_site(self, nl_detail_html: str) -> None:
        """JSON-LD extraction should work for NL site with different dealer."""
        from i4_scout.scrapers.autoscout24_nl import AutoScout24NLScraper

        result = AutoScout24NLScraper.parse_json_ld_sync(nl_detail_html)

        assert result is not None
        assert result["dealer_name"] == "Van Hooff BMW"
        assert result["location_city"] == "VELDHOVEN"
        assert result["location_zip"] == "5504 DW"
        assert result["location_country"] == "NL"
        assert result["dealer_type"] == "dealer"

    def test_parse_json_ld_handles_missing_json_ld(self) -> None:
        """Should return None gracefully when no JSON-LD block exists."""
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        html = "<html><body><h1>No JSON-LD here</h1></body></html>"
        result = AutoScout24DEScraper.parse_json_ld_sync(html)

        assert result is None

    def test_parse_json_ld_handles_malformed_json(self) -> None:
        """Should return None gracefully when JSON-LD is malformed."""
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        html = '<script type="application/ld+json">{invalid json}</script>'
        result = AutoScout24DEScraper.parse_json_ld_sync(html)

        assert result is None

    def test_parse_json_ld_handles_missing_offered_by(self) -> None:
        """Should return None when Product has no offeredBy field."""
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        html = '''<script type="application/ld+json">
        {"@type": "Product", "offers": {"@type": "Offer", "price": 1000}}
        </script>'''
        result = AutoScout24DEScraper.parse_json_ld_sync(html)

        assert result is None

    def test_parse_json_ld_handles_missing_address(self) -> None:
        """Should return dealer info even when address is missing."""
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        html = '''<script type="application/ld+json">
        {"@type": "Product", "offers": {"@type": "Offer",
         "offeredBy": {"@type": "AutoDealer", "name": "Test Dealer"}}}
        </script>'''
        result = AutoScout24DEScraper.parse_json_ld_sync(html)

        assert result is not None
        assert result["dealer_name"] == "Test Dealer"
        assert result["dealer_type"] == "dealer"
        assert result["location_city"] is None
        assert result["location_zip"] is None
        assert result["location_country"] is None

    def test_parse_json_ld_normalizes_person_type_to_private(self) -> None:
        """Seller type 'Person' should be normalized to 'private'."""
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        html = '''<script type="application/ld+json">
        {"@type": "Product", "offers": {"@type": "Offer",
         "offeredBy": {"@type": "Person", "name": "John Doe",
          "address": {"addressLocality": "Berlin", "postalCode": "10115", "addressCountry": "DE"}}}}
        </script>'''
        result = AutoScout24DEScraper.parse_json_ld_sync(html)

        assert result is not None
        assert result["dealer_name"] == "John Doe"
        assert result["dealer_type"] == "private"

    def test_parse_json_ld_finds_product_among_multiple_blocks(self) -> None:
        """Should find and parse the Product JSON-LD block among others."""
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        html = '''
        <script type="application/ld+json">{"@type": "BreadcrumbList"}</script>
        <script type="application/ld+json">
        {"@type": "Product", "offers": {"@type": "Offer",
         "offeredBy": {"@type": "AutoDealer", "name": "Found Dealer",
          "address": {"addressLocality": "Munich"}}}}
        </script>
        <script type="application/ld+json">{"@type": "Organization"}</script>
        '''
        result = AutoScout24DEScraper.parse_json_ld_sync(html)

        assert result is not None
        assert result["dealer_name"] == "Found Dealer"
        assert result["location_city"] == "Munich"


class TestAutoScout24DetailParsingIntegration:
    """Integration tests for full detail page parsing with JSON-LD."""

    async def test_parse_listing_detail_includes_location_data(
        self, de_detail_html: str
    ) -> None:
        """parse_listing_detail should include location/dealer from JSON-LD."""
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        # Create scraper with mock browser
        scraper = AutoScout24DEScraper(None)  # type: ignore
        result = await scraper.parse_listing_detail(
            de_detail_html, "https://example.com/listing"
        )

        assert result.dealer_name == "Baum Automobile GmbH & Co. KG"
        assert result.dealer_type == "dealer"
        assert result.location_city == "Bad Neuenahr-Ahrweiler"
        assert result.location_zip == "53474"
        assert result.location_country == "DE"

    async def test_parse_listing_detail_includes_nl_location_data(
        self, nl_detail_html: str
    ) -> None:
        """parse_listing_detail should work for NL site."""
        from i4_scout.scrapers.autoscout24_nl import AutoScout24NLScraper

        scraper = AutoScout24NLScraper(None)  # type: ignore
        result = await scraper.parse_listing_detail(
            nl_detail_html, "https://example.com/listing"
        )

        assert result.dealer_name == "Van Hooff BMW"
        assert result.location_city == "VELDHOVEN"
        assert result.location_country == "NL"


class TestAutoScout24ColorParsing:
    """Tests for vehicle color extraction from detail pages."""

    def test_parse_colors_extracts_german_exterior_color(self, de_detail_html: str) -> None:
        """Exterior color (Außenfarbe) should be extracted from German detail page."""
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        result = AutoScout24DEScraper.parse_colors_sync(de_detail_html)

        assert result["exterior_color"] == "Grau"

    def test_parse_colors_extracts_german_interior_color(self, de_detail_html: str) -> None:
        """Interior color (Farbe der Innenausstattung) should be extracted from German detail page."""
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        result = AutoScout24DEScraper.parse_colors_sync(de_detail_html)

        assert result["interior_color"] == "Beige"

    def test_parse_colors_extracts_german_interior_material(self, de_detail_html: str) -> None:
        """Interior material (Innenausstattung) should be extracted from German detail page."""
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        result = AutoScout24DEScraper.parse_colors_sync(de_detail_html)

        assert result["interior_material"] == "Vollleder"

    def test_parse_colors_extracts_dutch_exterior_color(self, nl_detail_html: str) -> None:
        """Exterior color (Kleur) should be extracted from Dutch detail page."""
        from i4_scout.scrapers.autoscout24_nl import AutoScout24NLScraper

        result = AutoScout24NLScraper.parse_colors_sync(nl_detail_html)

        assert result["exterior_color"] == "Grijs"

    def test_parse_colors_extracts_dutch_interior_color(self, nl_detail_html: str) -> None:
        """Interior color (Kleur interieur) should be extracted from Dutch detail page."""
        from i4_scout.scrapers.autoscout24_nl import AutoScout24NLScraper

        result = AutoScout24NLScraper.parse_colors_sync(nl_detail_html)

        assert result["interior_color"] == "Zwart"

    def test_parse_colors_extracts_dutch_interior_material(self, nl_detail_html: str) -> None:
        """Interior material (Materiaal) should be extracted from Dutch detail page."""
        from i4_scout.scrapers.autoscout24_nl import AutoScout24NLScraper

        result = AutoScout24NLScraper.parse_colors_sync(nl_detail_html)

        assert result["interior_material"] == "Leder"

    def test_parse_colors_handles_missing_data(self) -> None:
        """Parser should return None for missing color fields."""
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        html = "<html><body><h1>No color data here</h1></body></html>"
        result = AutoScout24DEScraper.parse_colors_sync(html)

        assert result["exterior_color"] is None
        assert result["interior_color"] is None
        assert result["interior_material"] is None

    async def test_parse_listing_detail_includes_colors(self, de_detail_html: str) -> None:
        """parse_listing_detail should include color data from German page."""
        from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper

        scraper = AutoScout24DEScraper(None)  # type: ignore
        result = await scraper.parse_listing_detail(
            de_detail_html, "https://example.com/listing"
        )

        assert result.exterior_color == "Grau"
        assert result.interior_color == "Beige"
        assert result.interior_material == "Vollleder"

    async def test_parse_listing_detail_includes_nl_colors(self, nl_detail_html: str) -> None:
        """parse_listing_detail should include color data from Dutch page."""
        from i4_scout.scrapers.autoscout24_nl import AutoScout24NLScraper

        scraper = AutoScout24NLScraper(None)  # type: ignore
        result = await scraper.parse_listing_detail(
            nl_detail_html, "https://example.com/listing"
        )

        assert result.exterior_color == "Grijs"
        assert result.interior_color == "Zwart"
        assert result.interior_material == "Leder"
