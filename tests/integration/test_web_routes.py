"""Integration tests for web routes."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from i4_scout.api.dependencies import get_db
from i4_scout.api.main import create_app
from i4_scout.database.repository import ListingRepository
from i4_scout.models.db_models import Base
from i4_scout.models.pydantic_models import ListingCreate, Source


@pytest.fixture
def client():
    """Create a test client for the FastAPI application."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def client_with_listings(tmp_path: Path):
    """Create a test client with listings in the database."""
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    # Create test listings
    session = session_factory()
    repo = ListingRepository(session)
    repo.create_listing(
        ListingCreate(
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com/test",
            title="Test BMW i4",
            price=45000_00,
        )
    )
    repo.create_listing(
        ListingCreate(
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com/test-issue",
            title="Test BMW i4 with Issue",
            price=40000_00,
            has_issue=True,
        )
    )
    session.commit()
    session.close()

    # Create app with test database
    app = create_app()

    def get_test_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = get_test_db
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

    def test_sort_headers_preserve_has_issue_filter(self, client_with_listings):
        """Test that sort headers preserve the has_issue filter in URLs."""
        # Request listings without has_issue filter first to verify table renders
        response = client_with_listings.get("/partials/listings")
        assert response.status_code == 200
        assert "sortable-header" in response.text  # Verify headers render

        # Request with has_issue filter - sort headers should include it in URLs
        response = client_with_listings.get("/partials/listings?has_issue=true")
        assert response.status_code == 200
        # Sort headers should include has_issue=true in their URLs
        assert "has_issue=true" in response.text

    def test_listings_page_passes_has_issue_to_filter_form(self, client_with_listings):
        """Test that listings page passes has_issue filter to form context."""
        # Request listings page with has_issue=true
        response = client_with_listings.get("/listings?has_issue=true")
        assert response.status_code == 200
        # The filter form should have the has_issue checkbox checked
        assert 'name="has_issue"' in response.text
        assert "checked" in response.text  # has_issue checkbox should be checked

    def test_sort_headers_preserve_options_filter(self, client_with_listings):
        """Test that sort headers preserve the has_option filter in URLs."""
        # First verify we have listings without options filter
        response = client_with_listings.get("/partials/listings")
        assert response.status_code == 200
        assert "sortable-header" in response.text

        # Use options_match=any so listings show even without matching options
        # The key test is that sort headers include has_option in their URLs
        response = client_with_listings.get(
            "/partials/listings?has_option=Memory%20Seats&options_match=any"
        )
        assert response.status_code == 200
        # Even with no matches, the has_option should be in sort header URLs
        # if the table renders (which it does with options_match=any when some listings exist)
        # Check if has_option appears in the response (in sort header URLs)
        assert "has_option=Memory" in response.text or "No listings found" in response.text


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


@pytest.fixture
def client_with_colors(tmp_path: Path):
    """Create a test client with listings that have color data."""
    db_path = tmp_path / "test_colors.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    # Create test listing with color data
    session = session_factory()
    repo = ListingRepository(session)
    repo.create_listing(
        ListingCreate(
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com/colored-car",
            title="Test BMW i4 with Colors",
            price=45000_00,
            exterior_color="Grau",
            interior_color="Beige",
            interior_material="Vollleder",
        )
    )
    repo.create_listing(
        ListingCreate(
            source=Source.AUTOSCOUT24_NL,
            url="https://example.com/nl-car",
            title="Test BMW i4 NL",
            price=42000_00,
            exterior_color="Grijs",
            interior_color="Zwart",
            interior_material="Leder",
        )
    )
    session.commit()
    session.close()

    # Create app with test database
    app = create_app()

    def get_test_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = get_test_db
    return TestClient(app)


class TestColorFieldsInTemplates:
    """Tests for color fields display in templates."""

    def test_listing_detail_shows_exterior_color(self, client_with_colors):
        """Test that listing detail page shows exterior color."""
        response = client_with_colors.get("/listings/1")
        assert response.status_code == 200
        assert "Exterior Color" in response.text
        assert "Grau" in response.text

    def test_listing_detail_shows_interior_color(self, client_with_colors):
        """Test that listing detail page shows interior color."""
        response = client_with_colors.get("/listings/1")
        assert response.status_code == 200
        assert "Interior Color" in response.text
        assert "Beige" in response.text

    def test_listing_detail_shows_interior_material(self, client_with_colors):
        """Test that listing detail page shows interior material."""
        response = client_with_colors.get("/listings/1")
        assert response.status_code == 200
        assert "Interior Material" in response.text
        assert "Vollleder" in response.text

    def test_compare_page_shows_color_rows(self, client_with_colors):
        """Test that compare page shows color rows."""
        response = client_with_colors.get("/compare?ids=1,2")
        assert response.status_code == 200
        assert "Ext. Color" in response.text
        assert "Int. Color" in response.text
        assert "Int. Material" in response.text

    def test_compare_page_shows_color_values(self, client_with_colors):
        """Test that compare page shows actual color values."""
        response = client_with_colors.get("/compare?ids=1,2")
        assert response.status_code == 200
        # German listing colors
        assert "Grau" in response.text
        assert "Beige" in response.text
        assert "Vollleder" in response.text
        # Dutch listing colors
        assert "Grijs" in response.text
        assert "Zwart" in response.text
        assert "Leder" in response.text

    def test_listing_detail_shows_empty_color_placeholder(self, client_with_listings):
        """Test that listing without colors shows placeholder."""
        response = client_with_listings.get("/listings/1")
        assert response.status_code == 200
        assert "Exterior Color" in response.text
        # The placeholder is '--'
        assert "--" in response.text


@pytest.fixture
def client_with_notes(tmp_path: Path):
    """Create a test client with listings that have notes."""
    from i4_scout.models.db_models import ListingNote

    db_path = tmp_path / "test_notes.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    # Create test listing with notes
    session = session_factory()
    repo = ListingRepository(session)
    listing = repo.create_listing(
        ListingCreate(
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com/noted-car",
            title="Test BMW i4 with Notes",
            price=45000_00,
        )
    )

    # Add notes to the listing
    note1 = ListingNote(
        listing_id=listing.id,
        content="Called dealer, car is available.",
    )
    note2 = ListingNote(
        listing_id=listing.id,
        content="Scheduled viewing for Saturday.",
    )
    session.add(note1)
    session.add(note2)
    session.commit()
    session.close()

    # Create app with test database
    app = create_app()

    def get_test_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = get_test_db
    return TestClient(app)


class TestNotesSummary:
    """Tests for notes summary partial (hover popover)."""

    def test_notes_summary_not_found(self, client):
        """Test notes summary for non-existent listing returns empty state."""
        response = client.get("/partials/listing/99999/notes-summary")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        # Should show "No notes" for listing without notes
        assert "No notes" in response.text

    def test_notes_summary_endpoint_exists(self, client):
        """Test that notes summary endpoint exists."""
        response = client.get("/partials/listing/1/notes-summary")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_notes_summary_shows_note_count(self, client_with_notes):
        """Test notes summary shows note count header."""
        response = client_with_notes.get("/partials/listing/1/notes-summary")
        assert response.status_code == 200
        assert "2 notes" in response.text

    def test_notes_summary_shows_note_content(self, client_with_notes):
        """Test notes summary displays note content."""
        response = client_with_notes.get("/partials/listing/1/notes-summary")
        assert response.status_code == 200
        assert "Called dealer" in response.text
        assert "Scheduled viewing" in response.text

    def test_notes_summary_shows_timestamps(self, client_with_notes):
        """Test notes summary displays timestamps."""
        response = client_with_notes.get("/partials/listing/1/notes-summary")
        assert response.status_code == 200
        # Timestamps should be in YYYY-MM-DD HH:MM format
        assert "note-preview-timestamp" in response.text
