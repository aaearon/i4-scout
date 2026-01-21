"""Integration tests for listings API endpoints."""

from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from i4_scout.api.dependencies import get_db
from i4_scout.api.main import create_app
from i4_scout.database.repository import ListingRepository
from i4_scout.models.db_models import Base, PriceHistory
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
def client(session_factory):
    """Create a test client with overridden database dependency."""
    app = create_app()

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


@pytest.fixture
def sample_listings(session_factory) -> list[int]:
    """Create sample listings and return their IDs."""
    session = session_factory()
    repo = ListingRepository(session)

    listings_data = [
        ListingCreate(
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com/listing1",
            title="BMW i4 eDrive40 - Test 1",
            price=45000,
            mileage_km=15000,
            match_score=85.0,
            is_qualified=True,
        ),
        ListingCreate(
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com/listing2",
            title="BMW i4 eDrive40 - Test 2",
            price=48000,
            mileage_km=20000,
            match_score=70.0,
            is_qualified=False,
        ),
        ListingCreate(
            source=Source.AUTOSCOUT24_NL,
            url="https://example.com/listing3",
            title="BMW i4 eDrive40 - Test 3",
            price=52000,
            mileage_km=10000,
            match_score=90.0,
            is_qualified=True,
        ),
    ]

    ids = []
    for data in listings_data:
        listing = repo.create_listing(data)
        ids.append(listing.id)

    session.close()
    return ids


class TestListListings:
    """Tests for GET /api/listings endpoint."""

    def test_list_empty(self, client: TestClient) -> None:
        """Returns empty list when no listings exist."""
        response = client.get("/api/listings")
        assert response.status_code == 200
        data = response.json()
        assert data["listings"] == []
        assert data["count"] == 0
        assert data["total"] == 0

    def test_list_all(self, client: TestClient, sample_listings: list[int]) -> None:
        """Returns all listings."""
        response = client.get("/api/listings")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 3
        assert data["total"] == 3
        assert len(data["listings"]) == 3

    def test_list_with_pagination(self, client: TestClient, sample_listings: list[int]) -> None:
        """Respects limit and offset parameters."""
        response = client.get("/api/listings?limit=2&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert data["total"] == 3
        assert data["limit"] == 2
        assert data["offset"] == 0

        # Second page
        response = client.get("/api/listings?limit=2&offset=2")
        data = response.json()
        assert data["count"] == 1
        assert data["total"] == 3

    def test_list_qualified_only(self, client: TestClient, sample_listings: list[int]) -> None:
        """Filters by qualified_only parameter."""
        response = client.get("/api/listings?qualified_only=true")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert data["total"] == 2
        assert all(listing["is_qualified"] for listing in data["listings"])

    def test_list_by_source(self, client: TestClient, sample_listings: list[int]) -> None:
        """Filters by source parameter."""
        response = client.get("/api/listings?source=autoscout24_nl")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["listings"][0]["source"] == "autoscout24_nl"

    def test_list_by_min_score(self, client: TestClient, sample_listings: list[int]) -> None:
        """Filters by min_score parameter."""
        response = client.get("/api/listings?min_score=80")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert all(listing["match_score"] >= 80 for listing in data["listings"])

    def test_list_combined_filters(self, client: TestClient, sample_listings: list[int]) -> None:
        """Applies multiple filters together."""
        response = client.get("/api/listings?source=autoscout24_de&qualified_only=true")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1


class TestGetListing:
    """Tests for GET /api/listings/{id} endpoint."""

    def test_get_existing(self, client: TestClient, sample_listings: list[int]) -> None:
        """Returns listing details for existing ID."""
        listing_id = sample_listings[0]
        response = client.get(f"/api/listings/{listing_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == listing_id
        assert data["title"] == "BMW i4 eDrive40 - Test 1"
        assert data["price"] == 45000

    def test_get_not_found(self, client: TestClient) -> None:
        """Returns 404 for non-existent listing."""
        response = client.get("/api/listings/9999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestGetPriceHistory:
    """Tests for GET /api/listings/{id}/price-history endpoint."""

    def test_get_price_history(
        self, client: TestClient, sample_listings: list[int], session_factory
    ) -> None:
        """Returns price history for a listing."""
        listing_id = sample_listings[0]

        # Add price history entries
        session = session_factory()
        history1 = PriceHistory(listing_id=listing_id, price=46000, recorded_at=datetime.utcnow())
        history2 = PriceHistory(listing_id=listing_id, price=45000, recorded_at=datetime.utcnow())
        session.add_all([history1, history2])
        session.commit()
        session.close()

        response = client.get(f"/api/listings/{listing_id}/price-history")
        assert response.status_code == 200
        data = response.json()
        assert data["listing_id"] == listing_id
        assert data["current_price"] == 45000
        assert len(data["history"]) == 2

    def test_price_history_not_found(self, client: TestClient) -> None:
        """Returns 404 for non-existent listing."""
        response = client.get("/api/listings/9999/price-history")
        assert response.status_code == 404


class TestDeleteListing:
    """Tests for DELETE /api/listings/{id} endpoint."""

    def test_delete_existing(self, client: TestClient, sample_listings: list[int]) -> None:
        """Deletes existing listing and returns success."""
        listing_id = sample_listings[0]
        response = client.delete(f"/api/listings/{listing_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify deletion
        response = client.get(f"/api/listings/{listing_id}")
        assert response.status_code == 404

    def test_delete_not_found(self, client: TestClient) -> None:
        """Returns 404 for non-existent listing."""
        response = client.delete("/api/listings/9999")
        assert response.status_code == 404
