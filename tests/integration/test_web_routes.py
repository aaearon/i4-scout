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
