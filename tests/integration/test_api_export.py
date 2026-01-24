"""Integration tests for export API endpoints."""

import json
from datetime import date
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
            title="BMW i4 eDrive40 M Sport - Test 1",
            price=45000,
            mileage_km=15000,
            year=2023,
            first_registration=date(2023, 6, 1),
            location_country="D",
            description="Beautiful M Sport package.",
            match_score=85.0,
            is_qualified=True,
        ),
        ListingCreate(
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com/listing2",
            title="BMW i4 eDrive40 - Test 2",
            price=48000,
            mileage_km=20000,
            year=2024,
            first_registration=date(2024, 3, 1),
            location_country="D",
            description="Full leather interior.",
            match_score=70.0,
            is_qualified=False,
        ),
        ListingCreate(
            source=Source.AUTOSCOUT24_NL,
            url="https://example.com/listing3",
            title="BMW i4 eDrive40 Premium - Test 3",
            price=52000,
            mileage_km=10000,
            year=2023,
            first_registration=date(2023, 11, 1),
            location_country="NL",
            description="Premium package.",
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


class TestExportCsv:
    """Tests for GET /api/export/listings?format=csv endpoint."""

    def test_export_csv_all_listings(
        self, client: TestClient, sample_listings: list[int]
    ) -> None:
        """Export all listings as CSV."""
        response = client.get("/api/export/listings?format=csv")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "attachment" in response.headers["content-disposition"]
        assert "listings_" in response.headers["content-disposition"]
        assert ".csv" in response.headers["content-disposition"]

        # Verify CSV content
        content = response.text
        lines = content.strip().split("\n")
        assert len(lines) == 4  # Header + 3 listings

        # Check header
        header = lines[0]
        assert "id" in header
        assert "title" in header
        assert "price" in header
        assert "source" in header

        # Check data
        assert "BMW i4" in content
        assert "45000" in content

    def test_export_csv_with_filters(
        self, client: TestClient, sample_listings: list[int]
    ) -> None:
        """Export filtered listings as CSV."""
        response = client.get("/api/export/listings?format=csv&qualified_only=true")

        assert response.status_code == 200

        content = response.text
        lines = content.strip().split("\n")
        # Header + 2 qualified listings
        assert len(lines) == 3

        # Qualified listings have scores 85 and 90
        assert "M Sport" in content or "Premium" in content

    def test_export_csv_with_price_filter(
        self, client: TestClient, sample_listings: list[int]
    ) -> None:
        """Export listings filtered by price range."""
        response = client.get("/api/export/listings?format=csv&price_max=46000")

        assert response.status_code == 200

        content = response.text
        lines = content.strip().split("\n")
        # Header + 1 listing (45000)
        assert len(lines) == 2
        assert "45000" in content

    def test_export_csv_empty_database(self, client: TestClient) -> None:
        """Export returns empty CSV with just header when no listings."""
        response = client.get("/api/export/listings?format=csv")

        assert response.status_code == 200

        content = response.text
        lines = content.strip().split("\n")
        # Just header, no data rows
        assert len(lines) == 1
        assert "id" in lines[0]

    def test_export_csv_content_disposition_header(
        self, client: TestClient, sample_listings: list[int]
    ) -> None:
        """Content-Disposition header has attachment with filename."""
        response = client.get("/api/export/listings?format=csv")

        assert response.status_code == 200
        cd = response.headers["content-disposition"]
        assert "attachment" in cd
        assert "filename=" in cd
        assert ".csv" in cd


class TestExportJson:
    """Tests for GET /api/export/listings?format=json endpoint."""

    def test_export_json_all_listings(
        self, client: TestClient, sample_listings: list[int]
    ) -> None:
        """Export all listings as JSON."""
        response = client.get("/api/export/listings?format=json")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert "attachment" in response.headers["content-disposition"]
        assert "listings_" in response.headers["content-disposition"]
        assert ".json" in response.headers["content-disposition"]

        data = response.json()
        assert "listings" in data
        assert "count" in data
        assert data["count"] == 3
        assert len(data["listings"]) == 3

    def test_export_json_with_filters(
        self, client: TestClient, sample_listings: list[int]
    ) -> None:
        """Export filtered listings as JSON."""
        response = client.get("/api/export/listings?format=json&source=autoscout24_nl")

        assert response.status_code == 200

        data = response.json()
        assert data["count"] == 1
        assert all(
            listing["source"] == "autoscout24_nl" for listing in data["listings"]
        )

    def test_export_json_with_min_score(
        self, client: TestClient, sample_listings: list[int]
    ) -> None:
        """Export listings filtered by minimum score."""
        response = client.get("/api/export/listings?format=json&min_score=80")

        assert response.status_code == 200

        data = response.json()
        # Scores: 85, 70, 90 - only 2 >= 80
        assert data["count"] == 2
        assert all(listing["match_score"] >= 80 for listing in data["listings"])

    def test_export_json_empty_database(self, client: TestClient) -> None:
        """Export returns empty JSON when no listings."""
        response = client.get("/api/export/listings?format=json")

        assert response.status_code == 200

        data = response.json()
        assert data["listings"] == []
        assert data["count"] == 0

    def test_export_json_content_disposition_header(
        self, client: TestClient, sample_listings: list[int]
    ) -> None:
        """Content-Disposition header has attachment with filename."""
        response = client.get("/api/export/listings?format=json")

        assert response.status_code == 200
        cd = response.headers["content-disposition"]
        assert "attachment" in cd
        assert "filename=" in cd
        assert ".json" in cd


class TestExportValidation:
    """Tests for export endpoint validation."""

    def test_export_invalid_format_returns_422(
        self, client: TestClient, sample_listings: list[int]
    ) -> None:
        """Invalid format parameter returns 422."""
        response = client.get("/api/export/listings?format=xml")

        assert response.status_code == 422

    def test_export_default_format_is_csv(
        self, client: TestClient, sample_listings: list[int]
    ) -> None:
        """Default format is CSV when not specified."""
        response = client.get("/api/export/listings")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
