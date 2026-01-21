"""Integration tests for issue API endpoints."""

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
def test_engine(tmp_path: Path):
    """Create a test database engine."""
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session_factory(test_engine):
    """Create a session factory for the test database."""
    return sessionmaker(bind=test_engine)


@pytest.fixture
def sample_listing(session_factory):
    """Create a sample listing in the test database."""
    session = session_factory()
    repo = ListingRepository(session)
    listing = repo.create_listing(
        ListingCreate(
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com/test-listing",
            title="Test BMW i4",
            price=5500000,
        )
    )
    session.close()
    return listing


@pytest.fixture
def listing_with_issue(session_factory):
    """Create a listing with issue flag set."""
    session = session_factory()
    repo = ListingRepository(session)
    listing = repo.create_listing(
        ListingCreate(
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com/test-listing-issue",
            title="Test BMW i4 with Issue",
            price=5000000,
            has_issue=True,
        )
    )
    session.close()
    return listing


@pytest.fixture
def client(session_factory, sample_listing, listing_with_issue):
    """Create test client with dependency overrides."""
    app = create_app()

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    return TestClient(app)


class TestSetIssueEndpoint:
    """Tests for the PATCH /api/listings/{id}/issue endpoint."""

    def test_set_issue_to_true(self, client, sample_listing):
        """Should set has_issue to True."""
        response = client.patch(
            f"/api/listings/{sample_listing.id}/issue",
            json={"has_issue": True},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["has_issue"] is True
        assert data["id"] == sample_listing.id

    def test_set_issue_to_false(self, client, listing_with_issue):
        """Should set has_issue to False."""
        response = client.patch(
            f"/api/listings/{listing_with_issue.id}/issue",
            json={"has_issue": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["has_issue"] is False

    def test_set_issue_not_found(self, client):
        """Should return 404 for non-existent listing."""
        response = client.patch(
            "/api/listings/99999/issue",
            json={"has_issue": True},
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestFilterByIssue:
    """Tests for filtering listings by issue status."""

    def test_filter_has_issue_true(self, client, sample_listing, listing_with_issue):
        """Should filter listings with has_issue=True."""
        response = client.get("/api/listings", params={"has_issue": True})
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["listings"][0]["has_issue"] is True

    def test_filter_has_issue_false(self, client, sample_listing, listing_with_issue):
        """Should filter listings with has_issue=False."""
        response = client.get("/api/listings", params={"has_issue": False})
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["listings"][0]["has_issue"] is False

    def test_no_issue_filter_returns_all(self, client, sample_listing, listing_with_issue):
        """Should return all listings when has_issue filter is not set."""
        response = client.get("/api/listings")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2


class TestListingResponseIncludesHasIssue:
    """Tests for has_issue field in listing responses."""

    def test_single_listing_includes_has_issue(self, client, sample_listing):
        """Single listing response should include has_issue."""
        response = client.get(f"/api/listings/{sample_listing.id}")
        assert response.status_code == 200
        data = response.json()
        assert "has_issue" in data
        assert data["has_issue"] is False

    def test_listing_with_issue_shows_true(self, client, listing_with_issue):
        """Listing with issue should show has_issue=True."""
        response = client.get(f"/api/listings/{listing_with_issue.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["has_issue"] is True

    def test_listings_list_includes_has_issue(self, client, sample_listing, listing_with_issue):
        """Listings list should include has_issue for each listing."""
        response = client.get("/api/listings")
        assert response.status_code == 200
        data = response.json()
        for listing in data["listings"]:
            assert "has_issue" in listing
