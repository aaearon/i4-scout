"""Tests for price change filter in repository."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from i4_scout.database.repository import ListingRepository
from i4_scout.models.db_models import Base
from i4_scout.models.pydantic_models import ListingCreate, Source


@pytest.fixture
def db_session():
    """Create an in-memory database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


@pytest.fixture
def repository(db_session: Session):
    """Create a repository instance with test session."""
    return ListingRepository(db_session)


class TestPriceChangeFilter:
    """Tests for price change filter functionality."""

    def test_has_price_change_filter_true(self, repository: ListingRepository):
        """Test has_price_change=True returns only listings with price changes."""
        # Create listing with price change
        listing_with_change = ListingCreate(
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com/listing-with-change",
            title="BMW i4 eDrive40 - Price Changed",
            price=45000,
        )
        listing1, _ = repository.upsert_listing(listing_with_change)
        repository.record_price_change(listing1.id, 47000)  # Add price change

        # Create listing without price change
        listing_no_change = ListingCreate(
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com/listing-no-change",
            title="BMW i4 eDrive40 - No Change",
            price=50000,
        )
        repository.upsert_listing(listing_no_change)

        # Filter for listings with price change
        listings = repository.get_listings(has_price_change=True)

        assert len(listings) == 1
        assert listings[0].id == listing1.id

    def test_has_price_change_filter_false(self, repository: ListingRepository):
        """Test has_price_change=False returns only listings without price changes."""
        # Create listing with price change
        listing_with_change = ListingCreate(
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com/listing-with-change",
            title="BMW i4 eDrive40 - Price Changed",
            price=45000,
        )
        listing1, _ = repository.upsert_listing(listing_with_change)
        repository.record_price_change(listing1.id, 47000)  # Add price change

        # Create listing without price change
        listing_no_change = ListingCreate(
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com/listing-no-change",
            title="BMW i4 eDrive40 - No Change",
            price=50000,
        )
        listing2, _ = repository.upsert_listing(listing_no_change)

        # Filter for listings without price change
        listings = repository.get_listings(has_price_change=False)

        assert len(listings) == 1
        assert listings[0].id == listing2.id

    def test_has_price_change_filter_none(self, repository: ListingRepository):
        """Test has_price_change=None returns all listings."""
        # Create listing with price change
        listing_with_change = ListingCreate(
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com/listing-with-change",
            title="BMW i4 eDrive40 - Price Changed",
            price=45000,
        )
        listing1, _ = repository.upsert_listing(listing_with_change)
        repository.record_price_change(listing1.id, 47000)

        # Create listing without price change
        listing_no_change = ListingCreate(
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com/listing-no-change",
            title="BMW i4 eDrive40 - No Change",
            price=50000,
        )
        repository.upsert_listing(listing_no_change)

        # No filter - should return all
        listings = repository.get_listings(has_price_change=None)

        assert len(listings) == 2

    def test_count_listings_with_price_change_filter(self, repository: ListingRepository):
        """Test count_listings respects has_price_change filter."""
        # Create listing with price change
        listing_with_change = ListingCreate(
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com/listing-with-change",
            title="BMW i4 eDrive40 - Price Changed",
            price=45000,
        )
        listing1, _ = repository.upsert_listing(listing_with_change)
        repository.record_price_change(listing1.id, 47000)

        # Create listing without price change
        listing_no_change = ListingCreate(
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com/listing-no-change",
            title="BMW i4 eDrive40 - No Change",
            price=50000,
        )
        repository.upsert_listing(listing_no_change)

        assert repository.count_listings(has_price_change=True) == 1
        assert repository.count_listings(has_price_change=False) == 1
        assert repository.count_listings(has_price_change=None) == 2

    def test_price_history_eager_loading(self, repository: ListingRepository):
        """Test price_history is eagerly loaded with get_listings."""
        # Create listing with multiple price changes
        listing_data = ListingCreate(
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com/listing",
            title="BMW i4 eDrive40",
            price=45000,
        )
        listing, _ = repository.upsert_listing(listing_data)
        repository.record_price_change(listing.id, 44000)  # Price drop
        repository.record_price_change(listing.id, 43000)  # Another drop

        # Get listings - price_history should be eagerly loaded
        listings = repository.get_listings()

        assert len(listings) == 1
        assert listings[0].price_history is not None
        assert len(listings[0].price_history) == 3  # Initial + 2 changes
