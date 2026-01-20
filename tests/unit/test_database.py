"""Unit tests for database models and engine."""

import pytest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import select
from sqlalchemy.orm import Session

from car_scraper.database.engine import get_engine, get_session, init_db, reset_engine
from car_scraper.models.db_models import (
    Base,
    Listing,
    ListingOption,
    Option,
    PriceHistory,
    ScrapeSessionModel,
)
from car_scraper.models.pydantic_models import ScrapeStatus, Source


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        reset_engine()  # Clear any existing engine
        engine = init_db(db_path)
        yield engine, db_path
        reset_engine()


@pytest.fixture
def db_session(temp_db):
    """Get a database session for testing."""
    engine, _ = temp_db
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()


class TestDatabaseEngine:
    """Tests for database engine functions."""

    def test_init_db_creates_tables(self, temp_db):
        engine, db_path = temp_db
        assert db_path.exists()

        # Check that tables were created
        from sqlalchemy import inspect

        inspector = inspect(engine)
        tables = inspector.get_table_names()

        assert "listings" in tables
        assert "options" in tables
        assert "listing_options" in tables
        assert "price_history" in tables
        assert "scrape_sessions" in tables

    def test_get_session(self, temp_db):
        engine, _ = temp_db
        with get_session(engine) as session:
            assert isinstance(session, Session)


class TestListingModel:
    """Tests for Listing ORM model."""

    def test_create_listing(self, db_session: Session):
        listing = Listing(
            source=Source.AUTOSCOUT24_DE,
            url="https://www.autoscout24.de/angebote/123",
            title="BMW i4 eDrive40 Gran Coupe",
            price=4500000,
            mileage_km=15000,
            year=2023,
        )
        db_session.add(listing)
        db_session.commit()

        assert listing.id is not None
        assert listing.first_seen_at is not None

    def test_listing_defaults(self, db_session: Session):
        listing = Listing(
            source=Source.AUTOSCOUT24_NL,
            url="https://example.com",
            title="Test",
        )
        db_session.add(listing)
        db_session.commit()

        assert listing.match_score == 0.0
        assert listing.is_qualified is False
        assert listing.photo_urls == []

    def test_listing_repr(self, db_session: Session):
        listing = Listing(
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com",
            title="BMW i4 eDrive40 Very Long Title That Gets Truncated",
            price=4000000,
        )
        db_session.add(listing)
        db_session.commit()

        repr_str = repr(listing)
        assert "Listing" in repr_str
        assert str(listing.id) in repr_str

    def test_query_listings(self, db_session: Session):
        # Create multiple listings
        for i in range(3):
            listing = Listing(
                source=Source.AUTOSCOUT24_DE,
                url=f"https://example.com/{i}",
                title=f"Listing {i}",
                is_qualified=(i % 2 == 0),
            )
            db_session.add(listing)
        db_session.commit()

        # Query qualified listings
        stmt = select(Listing).where(Listing.is_qualified == True)
        qualified = db_session.execute(stmt).scalars().all()
        assert len(qualified) == 2


class TestOptionModel:
    """Tests for Option ORM model."""

    def test_create_option(self, db_session: Session):
        option = Option(
            canonical_name="head_up_display",
            display_name="Head-Up Display",
            category="driver_assistance",
        )
        db_session.add(option)
        db_session.commit()

        assert option.id is not None
        assert option.is_bundle is False


class TestListingOptionRelationship:
    """Tests for Listing-Option relationship."""

    def test_listing_with_options(self, db_session: Session):
        # Create option
        option = Option(
            canonical_name="hud",
            display_name="Head-Up Display",
        )
        db_session.add(option)

        # Create listing
        listing = Listing(
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com",
            title="Test Listing",
        )
        db_session.add(listing)
        db_session.commit()

        # Create association
        listing_option = ListingOption(
            listing_id=listing.id,
            option_id=option.id,
            raw_text="Head Up Display",
            confidence=0.95,
        )
        db_session.add(listing_option)
        db_session.commit()

        # Verify relationship
        db_session.refresh(listing)
        assert len(listing.options) == 1
        assert listing.options[0].option.canonical_name == "hud"


class TestPriceHistory:
    """Tests for PriceHistory model."""

    def test_price_history(self, db_session: Session):
        listing = Listing(
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com",
            title="Test",
            price=4500000,
        )
        db_session.add(listing)
        db_session.commit()

        # Add price history
        history = PriceHistory(
            listing_id=listing.id,
            price=4500000,
        )
        db_session.add(history)

        # Price drop
        history2 = PriceHistory(
            listing_id=listing.id,
            price=4300000,
        )
        db_session.add(history2)
        db_session.commit()

        db_session.refresh(listing)
        assert len(listing.price_history) == 2


class TestScrapeSessionModel:
    """Tests for ScrapeSessionModel."""

    def test_create_session(self, db_session: Session):
        session_model = ScrapeSessionModel(
            source=Source.AUTOSCOUT24_DE,
            status=ScrapeStatus.RUNNING,
        )
        db_session.add(session_model)
        db_session.commit()

        assert session_model.id is not None
        assert session_model.started_at is not None
        assert session_model.completed_at is None

    def test_complete_session(self, db_session: Session):
        session_model = ScrapeSessionModel(
            source=Source.AUTOSCOUT24_NL,
            status=ScrapeStatus.COMPLETED,
            completed_at=datetime.utcnow(),
            listings_found=50,
            listings_new=10,
            pages_scraped=5,
        )
        db_session.add(session_model)
        db_session.commit()

        assert session_model.listings_found == 50
