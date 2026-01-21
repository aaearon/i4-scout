"""Integration tests for listings API endpoints."""

from datetime import date, datetime
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
    """Create sample listings and return their IDs.

    Creates 5 listings with varied attributes for comprehensive filter testing:
    - Listing 1: DE, D, 2023, 45000 EUR, 15000 km, M Sport in title, score=85
    - Listing 2: DE, D, 2024, 48000 EUR, 20000 km, leather in desc, score=70
    - Listing 3: NL, NL, 2023, 52000 EUR, 10000 km, Premium package, score=90
    - Listing 4: DE, B, 2024, 42000 EUR, 30000 km, HUD in desc, score=60
    - Listing 5: NL, NL, 2022, 38000 EUR, 45000 km, base model, score=50
    """
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
            description="Beautiful M Sport package with premium features.",
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
            description="Full leather interior, excellent condition.",
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
            description="Premium package with all options.",
            match_score=90.0,
            is_qualified=True,
        ),
        ListingCreate(
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com/listing4",
            title="BMW i4 eDrive40 - Test 4",
            price=42000,
            mileage_km=30000,
            year=2024,
            first_registration=date(2024, 8, 1),
            location_country="B",
            description="Equipped with HUD and driving assistant.",
            match_score=60.0,
            is_qualified=False,
        ),
        ListingCreate(
            source=Source.AUTOSCOUT24_NL,
            url="https://example.com/listing5",
            title="BMW i4 eDrive40 - Test 5",
            price=38000,
            mileage_km=45000,
            year=2022,
            first_registration=date(2022, 2, 1),
            location_country="NL",
            description="Base model, well maintained.",
            match_score=50.0,
            is_qualified=False,
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
        assert data["count"] == 5
        assert data["total"] == 5
        assert len(data["listings"]) == 5

    def test_list_with_pagination(self, client: TestClient, sample_listings: list[int]) -> None:
        """Respects limit and offset parameters."""
        response = client.get("/api/listings?limit=2&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert data["total"] == 5
        assert data["limit"] == 2
        assert data["offset"] == 0

        # Second page
        response = client.get("/api/listings?limit=2&offset=2")
        data = response.json()
        assert data["count"] == 2
        assert data["total"] == 5

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
        assert data["count"] == 2
        assert data["total"] == 2
        assert all(listing["source"] == "autoscout24_nl" for listing in data["listings"])

    def test_list_by_min_score(self, client: TestClient, sample_listings: list[int]) -> None:
        """Filters by min_score parameter."""
        response = client.get("/api/listings?min_score=80")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert data["total"] == 2
        assert all(listing["match_score"] >= 80 for listing in data["listings"])

    def test_list_combined_filters(self, client: TestClient, sample_listings: list[int]) -> None:
        """Applies multiple filters together."""
        response = client.get("/api/listings?source=autoscout24_de&qualified_only=true")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["total"] == 1


class TestGetListing:
    """Tests for GET /api/listings/{id} endpoint."""

    def test_get_existing(self, client: TestClient, sample_listings: list[int]) -> None:
        """Returns listing details for existing ID."""
        listing_id = sample_listings[0]
        response = client.get(f"/api/listings/{listing_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == listing_id
        assert data["title"] == "BMW i4 eDrive40 M Sport - Test 1"
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


class TestListListingsFilters:
    """Tests for new filter parameters on GET /api/listings endpoint."""

    def test_filter_by_price_min(self, client: TestClient, sample_listings: list[int]) -> None:
        """Filter listings by minimum price."""
        response = client.get("/api/listings?price_min=45000")
        assert response.status_code == 200
        data = response.json()
        # Prices: 38000, 42000, 45000, 48000, 52000
        # >= 45000: 45000, 48000, 52000 = 3 listings
        assert data["count"] == 3
        assert data["total"] == 3
        assert all(listing["price"] >= 45000 for listing in data["listings"])

    def test_filter_by_price_max(self, client: TestClient, sample_listings: list[int]) -> None:
        """Filter listings by maximum price."""
        response = client.get("/api/listings?price_max=45000")
        assert response.status_code == 200
        data = response.json()
        # Prices: 38000, 42000, 45000, 48000, 52000
        # <= 45000: 38000, 42000, 45000 = 3 listings
        assert data["count"] == 3
        assert data["total"] == 3
        assert all(listing["price"] <= 45000 for listing in data["listings"])

    def test_filter_by_price_range(self, client: TestClient, sample_listings: list[int]) -> None:
        """Filter listings by price range (min and max together)."""
        response = client.get("/api/listings?price_min=42000&price_max=48000")
        assert response.status_code == 200
        data = response.json()
        # Prices: 38000, 42000, 45000, 48000, 52000
        # 42000-48000: 42000, 45000, 48000 = 3 listings
        assert data["count"] == 3
        assert data["total"] == 3
        assert all(42000 <= listing["price"] <= 48000 for listing in data["listings"])

    def test_filter_by_mileage_min(self, client: TestClient, sample_listings: list[int]) -> None:
        """Filter listings by minimum mileage."""
        response = client.get("/api/listings?mileage_min=20000")
        assert response.status_code == 200
        data = response.json()
        # Mileages: 10000, 15000, 20000, 30000, 45000
        # >= 20000: 20000, 30000, 45000 = 3 listings
        assert data["count"] == 3
        assert data["total"] == 3
        assert all(listing["mileage_km"] >= 20000 for listing in data["listings"])

    def test_filter_by_mileage_max(self, client: TestClient, sample_listings: list[int]) -> None:
        """Filter listings by maximum mileage."""
        response = client.get("/api/listings?mileage_max=20000")
        assert response.status_code == 200
        data = response.json()
        # Mileages: 10000, 15000, 20000, 30000, 45000
        # <= 20000: 10000, 15000, 20000 = 3 listings
        assert data["count"] == 3
        assert data["total"] == 3
        assert all(listing["mileage_km"] <= 20000 for listing in data["listings"])

    def test_filter_by_mileage_range(
        self, client: TestClient, sample_listings: list[int]
    ) -> None:
        """Filter listings by mileage range (min and max together)."""
        response = client.get("/api/listings?mileage_min=15000&mileage_max=30000")
        assert response.status_code == 200
        data = response.json()
        # Mileages: 10000, 15000, 20000, 30000, 45000
        # 15000-30000: 15000, 20000, 30000 = 3 listings
        assert data["count"] == 3
        assert data["total"] == 3
        assert all(15000 <= listing["mileage_km"] <= 30000 for listing in data["listings"])

    def test_filter_by_year_min(self, client: TestClient, sample_listings: list[int]) -> None:
        """Filter listings by minimum year."""
        response = client.get("/api/listings?year_min=2024")
        assert response.status_code == 200
        data = response.json()
        # Years: 2022, 2023, 2023, 2024, 2024
        # >= 2024: 2 listings
        assert data["count"] == 2
        assert data["total"] == 2
        assert all(listing["year"] >= 2024 for listing in data["listings"])

    def test_filter_by_year_max(self, client: TestClient, sample_listings: list[int]) -> None:
        """Filter listings by maximum year."""
        response = client.get("/api/listings?year_max=2022")
        assert response.status_code == 200
        data = response.json()
        # Years: 2022, 2023, 2023, 2024, 2024
        # <= 2022: 1 listing
        assert data["count"] == 1
        assert data["total"] == 1
        assert all(listing["year"] <= 2022 for listing in data["listings"])

    def test_filter_by_year_range(self, client: TestClient, sample_listings: list[int]) -> None:
        """Filter listings by year range (min and max together)."""
        response = client.get("/api/listings?year_min=2023&year_max=2023")
        assert response.status_code == 200
        data = response.json()
        # Years: 2022, 2023, 2023, 2024, 2024
        # 2023 only: 2 listings
        assert data["count"] == 2
        assert data["total"] == 2
        assert all(listing["year"] == 2023 for listing in data["listings"])

    def test_filter_by_country(self, client: TestClient, sample_listings: list[int]) -> None:
        """Filter listings by country."""
        response = client.get("/api/listings?country=D")
        assert response.status_code == 200
        data = response.json()
        # Countries: D, D, NL, B, NL
        # D: 2 listings
        assert data["count"] == 2
        assert data["total"] == 2
        assert all(listing["location_country"] == "D" for listing in data["listings"])

    def test_filter_by_country_nl(self, client: TestClient, sample_listings: list[int]) -> None:
        """Filter listings by NL country."""
        response = client.get("/api/listings?country=NL")
        assert response.status_code == 200
        data = response.json()
        # Countries: D, D, NL, B, NL
        # NL: 2 listings
        assert data["count"] == 2
        assert data["total"] == 2
        assert all(listing["location_country"] == "NL" for listing in data["listings"])

    def test_filter_by_country_single_result(
        self, client: TestClient, sample_listings: list[int]
    ) -> None:
        """Filter listings by country with single result."""
        response = client.get("/api/listings?country=B")
        assert response.status_code == 200
        data = response.json()
        # Countries: D, D, NL, B, NL
        # B: 1 listing
        assert data["count"] == 1
        assert data["total"] == 1
        assert data["listings"][0]["location_country"] == "B"

    def test_search_in_title(self, client: TestClient, sample_listings: list[int]) -> None:
        """Search finds matches in title."""
        response = client.get("/api/listings?search=M Sport")
        assert response.status_code == 200
        data = response.json()
        # Title "M Sport" appears in listing 1
        assert data["count"] == 1
        assert data["total"] == 1
        assert "M Sport" in data["listings"][0]["title"]

    def test_search_in_description(self, client: TestClient, sample_listings: list[int]) -> None:
        """Search finds matches in description."""
        response = client.get("/api/listings?search=leather")
        assert response.status_code == 200
        data = response.json()
        # "leather" appears in listing 2 description
        assert data["count"] == 1
        assert data["total"] == 1
        assert "leather" in data["listings"][0]["description"].lower()

    def test_search_case_insensitive(
        self, client: TestClient, sample_listings: list[int]
    ) -> None:
        """Search is case-insensitive."""
        response = client.get("/api/listings?search=PREMIUM")
        assert response.status_code == 200
        data = response.json()
        # "Premium" appears in listing 1 desc and listing 3 title/desc
        assert data["count"] == 2
        assert data["total"] == 2

    def test_search_partial_match(self, client: TestClient, sample_listings: list[int]) -> None:
        """Search finds partial matches."""
        response = client.get("/api/listings?search=HUD")
        assert response.status_code == 200
        data = response.json()
        # "HUD" appears in listing 4 description
        assert data["count"] == 1
        assert data["total"] == 1

    def test_combined_filters(self, client: TestClient, sample_listings: list[int]) -> None:
        """Multiple filters work together."""
        response = client.get(
            "/api/listings?price_max=50000&year_min=2023&qualified_only=true"
        )
        assert response.status_code == 200
        data = response.json()
        # Price <= 50000: 38000, 42000, 45000, 48000 (not 52000)
        # Year >= 2023: 2023, 2023, 2024, 2024 (not 2022)
        # Qualified: only listings 1 and 3
        # Intersection: listing 1 (45000, 2023, qualified)
        assert data["count"] == 1
        assert data["total"] == 1
        assert data["listings"][0]["price"] <= 50000
        assert data["listings"][0]["year"] >= 2023
        assert data["listings"][0]["is_qualified"] is True


class TestListListingsSorting:
    """Tests for sorting parameters on GET /api/listings endpoint."""

    def test_sort_by_price_asc(self, client: TestClient, sample_listings: list[int]) -> None:
        """Sort by price ascending."""
        response = client.get("/api/listings?sort_by=price&sort_order=asc")
        assert response.status_code == 200
        data = response.json()
        prices = [listing["price"] for listing in data["listings"]]
        assert prices == sorted(prices)

    def test_sort_by_price_desc(self, client: TestClient, sample_listings: list[int]) -> None:
        """Sort by price descending."""
        response = client.get("/api/listings?sort_by=price&sort_order=desc")
        assert response.status_code == 200
        data = response.json()
        prices = [listing["price"] for listing in data["listings"]]
        assert prices == sorted(prices, reverse=True)

    def test_sort_by_mileage_asc(self, client: TestClient, sample_listings: list[int]) -> None:
        """Sort by mileage ascending."""
        response = client.get("/api/listings?sort_by=mileage&sort_order=asc")
        assert response.status_code == 200
        data = response.json()
        mileages = [listing["mileage_km"] for listing in data["listings"]]
        assert mileages == sorted(mileages)

    def test_sort_by_mileage_desc(self, client: TestClient, sample_listings: list[int]) -> None:
        """Sort by mileage descending."""
        response = client.get("/api/listings?sort_by=mileage&sort_order=desc")
        assert response.status_code == 200
        data = response.json()
        mileages = [listing["mileage_km"] for listing in data["listings"]]
        assert mileages == sorted(mileages, reverse=True)

    def test_sort_by_score_asc(self, client: TestClient, sample_listings: list[int]) -> None:
        """Sort by match score ascending."""
        response = client.get("/api/listings?sort_by=score&sort_order=asc")
        assert response.status_code == 200
        data = response.json()
        scores = [listing["match_score"] for listing in data["listings"]]
        assert scores == sorted(scores)

    def test_sort_by_score_desc(self, client: TestClient, sample_listings: list[int]) -> None:
        """Sort by match score descending."""
        response = client.get("/api/listings?sort_by=score&sort_order=desc")
        assert response.status_code == 200
        data = response.json()
        scores = [listing["match_score"] for listing in data["listings"]]
        assert scores == sorted(scores, reverse=True)

    def test_sort_default_is_last_seen_desc(
        self, client: TestClient, sample_listings: list[int]
    ) -> None:
        """Default sort is by last_seen descending (most recent first)."""
        response = client.get("/api/listings")
        assert response.status_code == 200
        data = response.json()
        # Last created should be first (listing 5)
        assert data["listings"][0]["title"] == "BMW i4 eDrive40 - Test 5"

    def test_combined_filters_and_sort(
        self, client: TestClient, sample_listings: list[int]
    ) -> None:
        """Filters and sorting work together."""
        response = client.get(
            "/api/listings?country=D&sort_by=price&sort_order=asc"
        )
        assert response.status_code == 200
        data = response.json()
        # Country D: listings 1 (45000) and 2 (48000)
        assert data["count"] == 2
        prices = [listing["price"] for listing in data["listings"]]
        assert prices == sorted(prices)
        assert all(listing["location_country"] == "D" for listing in data["listings"])

    def test_sort_with_pagination(
        self, client: TestClient, sample_listings: list[int]
    ) -> None:
        """Sorting works with pagination."""
        # Get first page sorted by price ascending
        response = client.get("/api/listings?sort_by=price&sort_order=asc&limit=2")
        assert response.status_code == 200
        data = response.json()
        prices_page1 = [listing["price"] for listing in data["listings"]]

        # Get second page
        response = client.get("/api/listings?sort_by=price&sort_order=asc&limit=2&offset=2")
        data = response.json()
        prices_page2 = [listing["price"] for listing in data["listings"]]

        # First page should have lowest prices
        assert max(prices_page1) <= min(prices_page2)
