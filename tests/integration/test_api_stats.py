"""Integration tests for stats API endpoints."""

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


class TestGetStats:
    """Tests for GET /api/stats endpoint."""

    def test_stats_empty(self, client: TestClient) -> None:
        """Returns zeros when no listings exist."""
        response = client.get("/api/stats")
        assert response.status_code == 200
        data = response.json()

        assert data["total_listings"] == 0
        assert data["qualified_listings"] == 0
        assert data["listings_by_source"] == {}
        assert data["average_price"] is None
        assert data["average_mileage"] is None
        assert data["average_score"] is None

    def test_stats_with_data(self, client: TestClient, sample_listings: list[int]) -> None:
        """Returns correct statistics for sample data."""
        response = client.get("/api/stats")
        assert response.status_code == 200
        data = response.json()

        assert data["total_listings"] == 3
        assert data["qualified_listings"] == 2

        # Check source breakdown
        assert data["listings_by_source"]["autoscout24_de"] == 2
        assert data["listings_by_source"]["autoscout24_nl"] == 1

        # Check averages (45000 + 48000 + 52000) / 3 = 48333.33
        assert data["average_price"] == pytest.approx(48333.33, rel=0.01)

        # Check mileage average (15000 + 20000 + 10000) / 3 = 15000
        assert data["average_mileage"] == pytest.approx(15000, rel=0.01)

        # Check score average (85 + 70 + 90) / 3 = 81.67
        assert data["average_score"] == pytest.approx(81.67, rel=0.01)
