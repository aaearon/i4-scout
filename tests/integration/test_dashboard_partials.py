"""Integration tests for dashboard partial endpoints."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from i4_scout.api.dependencies import get_db
from i4_scout.api.main import create_app
from i4_scout.database.repository import ListingRepository
from i4_scout.models.db_models import Base, PriceHistory
from i4_scout.models.pydantic_models import ListingCreate, ListingStatus, Source


@pytest.fixture
def client_with_db(tmp_path: Path):
    """Create a test client with an in-memory database."""
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    app = create_app()

    def get_test_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = get_test_db

    # Return client and session_factory for test setup
    return TestClient(app), session_factory


class TestMarketVelocityPartial:
    """Test /partials/market-velocity endpoint."""

    def test_returns_html_fragment(self, client_with_db) -> None:
        """Should return HTML content."""
        client, _ = client_with_db
        response = client.get("/partials/market-velocity")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Market Pulse" in response.text

    def test_displays_velocity_stats(self, client_with_db) -> None:
        """Should display new, delisted, and net counts."""
        client, session_factory = client_with_db

        # Create a new listing
        session = session_factory()
        repo = ListingRepository(session)
        repo.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com/listing/1",
                title="BMW i4 test",
            )
        )
        session.commit()
        session.close()

        response = client.get("/partials/market-velocity")

        assert response.status_code == 200
        assert "New" in response.text
        assert "Delisted" in response.text
        assert "Net" in response.text

    def test_accepts_days_parameter(self, client_with_db) -> None:
        """Should accept custom days parameter."""
        client, _ = client_with_db
        response = client.get("/partials/market-velocity?days=30")

        assert response.status_code == 200
        assert "(30 days)" in response.text


class TestPriceDropsPartial:
    """Test /partials/price-drops endpoint."""

    def test_returns_html_fragment(self, client_with_db) -> None:
        """Should return HTML content."""
        client, _ = client_with_db
        response = client.get("/partials/price-drops")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Price Drops" in response.text

    def test_displays_empty_state(self, client_with_db) -> None:
        """Should display empty state when no price drops."""
        client, _ = client_with_db
        response = client.get("/partials/price-drops")

        assert response.status_code == 200
        assert "No price drops" in response.text

    def test_displays_price_drop_listings(self, client_with_db) -> None:
        """Should display listings with price drops."""
        client, session_factory = client_with_db

        session = session_factory()
        repo = ListingRepository(session)
        listing = repo.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com/listing/drop",
                title="BMW i4 Price Drop",
                price=45000,
            )
        )

        # Add original higher price
        original = PriceHistory(
            listing_id=listing.id,
            price=50000,
            recorded_at=datetime.now(timezone.utc) - timedelta(days=3),
        )
        session.add(original)
        session.commit()
        session.close()

        response = client.get("/partials/price-drops")

        assert response.status_code == 200
        assert "BMW i4 Price Drop" in response.text


class TestNearMissPartial:
    """Test /partials/near-miss endpoint."""

    def test_returns_html_fragment(self, client_with_db) -> None:
        """Should return HTML content."""
        client, _ = client_with_db
        response = client.get("/partials/near-miss")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Near-Miss" in response.text

    def test_displays_empty_state(self, client_with_db) -> None:
        """Should display empty state when no near-miss listings."""
        client, _ = client_with_db
        response = client.get("/partials/near-miss")

        assert response.status_code == 200
        assert "No near-miss listings found" in response.text

    def test_displays_near_miss_listings(self, client_with_db) -> None:
        """Should display high-score unqualified listings."""
        client, session_factory = client_with_db

        session = session_factory()
        repo = ListingRepository(session)
        repo.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com/listing/near",
                title="BMW i4 Near Miss",
                match_score=85.0,
                is_qualified=False,
            )
        )
        session.commit()
        session.close()

        response = client.get("/partials/near-miss")

        assert response.status_code == 200
        assert "BMW i4 Near Miss" in response.text
        assert "85%" in response.text

    def test_accepts_threshold_parameter(self, client_with_db) -> None:
        """Should accept custom threshold parameter."""
        client, _ = client_with_db
        response = client.get("/partials/near-miss?threshold=90")

        assert response.status_code == 200
        assert ">= 90%" in response.text


class TestFeatureRarityPartial:
    """Test /partials/feature-rarity endpoint."""

    def test_returns_html_fragment(self, client_with_db) -> None:
        """Should return HTML content."""
        client, _ = client_with_db
        response = client.get("/partials/feature-rarity")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Feature Rarity" in response.text

    def test_displays_empty_state(self, client_with_db) -> None:
        """Should display empty state when no option data."""
        client, _ = client_with_db
        response = client.get("/partials/feature-rarity")

        assert response.status_code == 200
        assert "No option data available" in response.text

    def test_displays_option_frequencies(self, client_with_db) -> None:
        """Should display option frequency data."""
        client, session_factory = client_with_db

        session = session_factory()
        repo = ListingRepository(session)

        # Create option that matches config
        opt, _ = repo.get_or_create_option("M Sport Package")

        listing = repo.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com/listing/opt",
                title="BMW i4 with options",
            )
        )
        repo.add_option_to_listing(listing.id, opt.id)
        session.commit()
        session.close()

        response = client.get("/partials/feature-rarity")

        assert response.status_code == 200
        assert "M Sport Package" in response.text


class TestFavoritesPartial:
    """Test /partials/favorites endpoint."""

    def test_returns_html_fragment(self, client_with_db) -> None:
        """Should return HTML content."""
        client, _ = client_with_db
        response = client.get("/partials/favorites")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_displays_empty_state_when_no_ids(self, client_with_db) -> None:
        """Should display empty state when no IDs provided."""
        client, _ = client_with_db
        response = client.get("/partials/favorites")

        assert response.status_code == 200
        assert "No favorites yet" in response.text

    def test_displays_favorite_listings(self, client_with_db) -> None:
        """Should display listings for provided IDs."""
        client, session_factory = client_with_db

        session = session_factory()
        repo = ListingRepository(session)
        listing = repo.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com/listing/fav",
                title="BMW i4 Favorite",
                price=45000,
            )
        )
        session.commit()
        listing_id = listing.id
        session.close()

        response = client.get(f"/partials/favorites?ids={listing_id}")

        assert response.status_code == 200
        assert "BMW i4 Favorite" in response.text

    def test_handles_invalid_ids(self, client_with_db) -> None:
        """Should handle invalid ID format gracefully."""
        client, _ = client_with_db
        response = client.get("/partials/favorites?ids=invalid,not-a-number")

        assert response.status_code == 200
        assert "No favorites yet" in response.text

    def test_handles_nonexistent_ids(self, client_with_db) -> None:
        """Should handle nonexistent listing IDs gracefully."""
        client, _ = client_with_db
        response = client.get("/partials/favorites?ids=99999,88888")

        assert response.status_code == 200
        assert "No favorites yet" in response.text
