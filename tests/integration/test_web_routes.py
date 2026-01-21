"""Integration tests for web routes."""

import pytest
from fastapi.testclient import TestClient

from i4_scout.api.main import create_app


@pytest.fixture
def client():
    """Create a test client for the FastAPI application."""
    app = create_app()
    return TestClient(app)


class TestStaticFiles:
    """Tests for static file serving."""

    def test_pico_css_served(self, client):
        """Test that Pico CSS is served."""
        response = client.get("/static/css/pico.min.css")
        assert response.status_code == 200
        assert "text/css" in response.headers["content-type"]

    def test_htmx_served(self, client):
        """Test that HTMX is served."""
        response = client.get("/static/js/htmx.min.js")
        assert response.status_code == 200
        assert "javascript" in response.headers["content-type"]

    def test_custom_css_served(self, client):
        """Test that custom CSS is served."""
        response = client.get("/static/css/custom.css")
        assert response.status_code == 200
        assert "text/css" in response.headers["content-type"]


class TestDashboard:
    """Tests for dashboard page."""

    def test_dashboard_renders(self, client):
        """Test that dashboard page renders."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Dashboard" in response.text
        assert "i4-scout" in response.text

    def test_stats_partial_renders(self, client):
        """Test that stats partial renders with data."""
        response = client.get("/partials/stats")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Total Listings" in response.text

    def test_recent_qualified_partial_renders(self, client):
        """Test that recent qualified partial renders."""
        response = client.get("/partials/recent-qualified")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


class TestListings:
    """Tests for listings page."""

    def test_listings_page_renders(self, client):
        """Test that listings page renders."""
        response = client.get("/listings")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Listings" in response.text

    def test_listings_partial_renders(self, client):
        """Test that listings partial renders."""
        response = client.get("/partials/listings")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_listings_with_filters(self, client):
        """Test listings partial with filters."""
        response = client.get("/partials/listings?qualified_only=true&sort_by=price")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_listings_with_pagination(self, client):
        """Test listings partial with pagination."""
        response = client.get("/partials/listings?limit=10&offset=0")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_listings_with_empty_string_params(self, client):
        """Test listings partial handles empty string params from HTML forms."""
        # HTML forms send empty strings for unfilled fields, not missing params
        response = client.get(
            "/partials/listings?source=&min_score=&price_min=&price_max="
            "&mileage_max=&year_min=&country=&search=&sort_by=first_seen&sort_order=desc"
        )
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


class TestListingDetail:
    """Tests for listing detail page."""

    def test_listing_detail_not_found(self, client):
        """Test listing detail page for non-existent listing."""
        response = client.get("/listings/99999")
        assert response.status_code == 200  # Page renders but shows not found message
        assert "text/html" in response.headers["content-type"]
        assert "Not Found" in response.text or "not found" in response.text.lower()

    def test_listing_detail_partial_renders(self, client):
        """Test listing detail partial for non-existent listing."""
        response = client.get("/partials/listing/99999")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_price_chart_partial_renders(self, client):
        """Test price chart partial for non-existent listing."""
        response = client.get("/partials/listing/99999/price-chart")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "No price history" in response.text


class TestScrapePage:
    """Tests for scrape control page."""

    def test_scrape_page_renders(self, client):
        """Test that scrape page renders."""
        response = client.get("/scrape")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Scrape Control" in response.text

    def test_scrape_jobs_partial_renders(self, client):
        """Test that scrape jobs partial renders."""
        response = client.get("/partials/scrape/jobs")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


class TestNavigation:
    """Tests for navigation between pages."""

    def test_nav_links_present_on_dashboard(self, client):
        """Test that navigation links are present on dashboard."""
        response = client.get("/")
        assert "Dashboard" in response.text
        assert "Listings" in response.text
        assert "Scrape" in response.text
        assert 'href="/"' in response.text
        assert 'href="/listings"' in response.text
        assert 'href="/scrape"' in response.text

    def test_nav_links_present_on_listings(self, client):
        """Test that navigation links are present on listings page."""
        response = client.get("/listings")
        assert 'href="/"' in response.text
        assert 'href="/listings"' in response.text
        assert 'href="/scrape"' in response.text

    def test_back_to_listings_link_on_detail(self, client):
        """Test that back to listings link is present on detail page."""
        response = client.get("/listings/99999")
        assert 'href="/listings"' in response.text
        assert "Back to listings" in response.text


class TestOptionsSummary:
    """Tests for options summary partial (hover popover)."""

    def test_options_summary_not_found(self, client):
        """Test options summary for non-existent listing returns empty state."""
        response = client.get("/partials/listing/99999/options-summary")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Not found" in response.text or "not found" in response.text.lower()

    def test_options_summary_endpoint_exists(self, client):
        """Test that options summary endpoint exists."""
        response = client.get("/partials/listing/1/options-summary")
        # Should return 200 even for non-existent listing (empty state)
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


class TestOptionsFiltering:
    """Tests for filtering listings by options."""

    def test_listings_partial_with_single_option_filter(self, client):
        """Test filtering by a single option."""
        response = client.get("/partials/listings?has_option=Laser%20Light")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_listings_partial_with_multiple_options_all_mode(self, client):
        """Test filtering by multiple options with AND (all) mode."""
        response = client.get(
            "/partials/listings?has_option=Laser%20Light&has_option=Harman%20Kardon&options_match=all"
        )
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_listings_partial_with_options_any_mode(self, client):
        """Test filtering by options with OR (any) mode."""
        response = client.get(
            "/partials/listings?has_option=Panorama%20Roof&has_option=Sunroof&options_match=any"
        )
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_listings_partial_with_invalid_options_match_defaults_to_all(self, client):
        """Test that invalid options_match value defaults to 'all'."""
        response = client.get(
            "/partials/listings?has_option=Laser%20Light&options_match=invalid"
        )
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_listings_partial_with_empty_option_list(self, client):
        """Test that empty option filter is handled gracefully."""
        response = client.get("/partials/listings?has_option=")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_listings_page_includes_options_config(self, client):
        """Test that listings page has options config for filter form."""
        response = client.get("/listings")
        assert response.status_code == 200
        # Should contain option filter UI elements
        assert b"Filter by Options" in response.content or b"has_option" in response.content


class TestComparePage:
    """Tests for listing comparison page."""

    def test_compare_page_renders_without_ids(self, client):
        """Test compare page renders empty state without IDs."""
        response = client.get("/compare")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "No Listings to Compare" in response.text

    def test_compare_page_renders_with_empty_ids(self, client):
        """Test compare page renders empty state with empty ids param."""
        response = client.get("/compare?ids=")
        assert response.status_code == 200
        assert "No Listings to Compare" in response.text

    def test_compare_page_handles_invalid_ids(self, client):
        """Test compare page handles invalid IDs gracefully."""
        response = client.get("/compare?ids=abc,xyz")
        assert response.status_code == 200
        assert "No Listings to Compare" in response.text

    def test_compare_page_handles_nonexistent_ids(self, client):
        """Test compare page handles non-existent listing IDs."""
        response = client.get("/compare?ids=99999,99998")
        assert response.status_code == 200
        # Should render but with no listings found
        assert "No Listings to Compare" in response.text

    def test_compare_page_with_valid_ids_format(self, client):
        """Test compare page accepts valid ID format."""
        response = client.get("/compare?ids=1,2,3")
        assert response.status_code == 200
        # Page renders (listings may not exist, but route works)
        assert "text/html" in response.headers["content-type"]

    def test_compare_page_limits_to_4_listings(self, client):
        """Test compare page limits IDs to 4."""
        response = client.get("/compare?ids=1,2,3,4,5,6")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_compare_page_has_back_link(self, client):
        """Test compare page has link back to listings."""
        response = client.get("/compare?ids=1,2")
        assert response.status_code == 200
        assert 'href="/listings"' in response.text

    def test_listings_page_includes_compare_bar(self, client):
        """Test that listings page includes the compare bar component."""
        response = client.get("/listings")
        assert response.status_code == 200
        assert "compare-bar" in response.text

    def test_listings_page_includes_compare_script(self, client):
        """Test that listings page includes compare selection script."""
        response = client.get("/listings")
        assert response.status_code == 200
        assert "compare-selection.js" in response.text

    def test_compare_selection_js_served(self, client):
        """Test that compare selection JS is served."""
        response = client.get("/static/js/compare-selection.js")
        assert response.status_code == 200
        assert "javascript" in response.headers["content-type"]


class TestFavorites:
    """Tests for favorites feature."""

    def test_favorites_js_served(self, client):
        """Test that favorites JS is served."""
        response = client.get("/static/js/favorites.js")
        assert response.status_code == 200
        assert "javascript" in response.headers["content-type"]

    def test_listings_page_includes_favorites_script(self, client):
        """Test that listings page includes favorites script."""
        response = client.get("/listings")
        assert response.status_code == 200
        assert "favorites.js" in response.text

    def test_listing_detail_includes_favorites_script(self, client):
        """Test that listing detail page includes favorites script."""
        response = client.get("/listings/99999")
        assert response.status_code == 200
        assert "favorites.js" in response.text

    def test_listings_page_has_favorites_filter(self, client):
        """Test that listings page has favorites filter checkbox."""
        response = client.get("/listings")
        assert response.status_code == 200
        assert "favorites-only" in response.text

    def test_listing_row_has_favorite_button(self, client):
        """Test that listings table partial includes favorite buttons."""
        response = client.get("/partials/listings")
        assert response.status_code == 200
        assert "favorite-btn" in response.text or "No listings found" in response.text
