"""Unit tests for ListingService."""


import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from i4_scout.database.repository import ListingRepository
from i4_scout.models.db_models import Base
from i4_scout.models.pydantic_models import ListingCreate, ListingRead, Source
from i4_scout.services.listing_service import ListingService


@pytest.fixture
def in_memory_session():
    """Create an in-memory SQLite session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def listing_service(in_memory_session):
    """Create a ListingService with an in-memory database."""
    return ListingService(in_memory_session)


@pytest.fixture
def sample_listing_data():
    """Sample listing data for testing."""
    return ListingCreate(
        source=Source.AUTOSCOUT24_DE,
        url="https://www.autoscout24.de/angebote/test-123",
        title="BMW i4 eDrive40 M Sport",
        price=45000,
        mileage_km=15000,
        year=2023,
        match_score=85.0,
        is_qualified=True,
    )


class TestListingServiceGetListings:
    """Tests for ListingService.get_listings()."""

    def test_get_listings_empty(self, listing_service):
        """Should return empty list and zero count when no listings."""
        listings, total = listing_service.get_listings()
        assert listings == []
        assert total == 0

    def test_get_listings_returns_listing_read(self, in_memory_session, sample_listing_data):
        """Should return ListingRead objects."""
        # Add a listing directly
        repo = ListingRepository(in_memory_session)
        repo.create_listing(sample_listing_data)

        service = ListingService(in_memory_session)
        listings, total = service.get_listings()

        assert len(listings) == 1
        assert total == 1
        assert isinstance(listings[0], ListingRead)
        assert listings[0].title == "BMW i4 eDrive40 M Sport"
        assert listings[0].price == 45000

    def test_get_listings_with_source_filter(self, in_memory_session):
        """Should filter by source."""
        repo = ListingRepository(in_memory_session)
        repo.create_listing(ListingCreate(
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com/de1",
            title="German Listing",
        ))
        repo.create_listing(ListingCreate(
            source=Source.AUTOSCOUT24_NL,
            url="https://example.com/nl1",
            title="Dutch Listing",
        ))

        service = ListingService(in_memory_session)

        de_listings, de_total = service.get_listings(source=Source.AUTOSCOUT24_DE)
        assert len(de_listings) == 1
        assert de_total == 1
        assert de_listings[0].title == "German Listing"

        nl_listings, nl_total = service.get_listings(source=Source.AUTOSCOUT24_NL)
        assert len(nl_listings) == 1
        assert nl_total == 1
        assert nl_listings[0].title == "Dutch Listing"

    def test_get_listings_qualified_only(self, in_memory_session):
        """Should filter by qualified status."""
        repo = ListingRepository(in_memory_session)
        repo.create_listing(ListingCreate(
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com/1",
            title="Qualified",
            is_qualified=True,
        ))
        repo.create_listing(ListingCreate(
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com/2",
            title="Not Qualified",
            is_qualified=False,
        ))

        service = ListingService(in_memory_session)

        qualified, total = service.get_listings(qualified_only=True)
        assert len(qualified) == 1
        assert total == 1
        assert qualified[0].title == "Qualified"

    def test_get_listings_min_score(self, in_memory_session):
        """Should filter by minimum score."""
        repo = ListingRepository(in_memory_session)
        repo.create_listing(ListingCreate(
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com/1",
            title="High Score",
            match_score=90.0,
        ))
        repo.create_listing(ListingCreate(
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com/2",
            title="Low Score",
            match_score=50.0,
        ))

        service = ListingService(in_memory_session)

        high, total = service.get_listings(min_score=70.0)
        assert len(high) == 1
        assert total == 1  # Total reflects filtered count (bug fix)
        assert high[0].title == "High Score"

    def test_get_listings_pagination(self, in_memory_session):
        """Should support limit and offset."""
        repo = ListingRepository(in_memory_session)
        for i in range(5):
            repo.create_listing(ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url=f"https://example.com/{i}",
                title=f"Listing {i}",
            ))

        service = ListingService(in_memory_session)

        # Get first page
        page1, total = service.get_listings(limit=2, offset=0)
        assert len(page1) == 2
        assert total == 5

        # Get second page
        page2, _ = service.get_listings(limit=2, offset=2)
        assert len(page2) == 2

        # Verify no overlap
        page1_ids = {listing.id for listing in page1}
        page2_ids = {listing.id for listing in page2}
        assert page1_ids.isdisjoint(page2_ids)


class TestListingServiceGetListing:
    """Tests for ListingService.get_listing()."""

    def test_get_listing_exists(self, in_memory_session, sample_listing_data):
        """Should return ListingRead when listing exists."""
        repo = ListingRepository(in_memory_session)
        created = repo.create_listing(sample_listing_data)

        service = ListingService(in_memory_session)
        listing = service.get_listing(created.id)

        assert listing is not None
        assert isinstance(listing, ListingRead)
        assert listing.id == created.id
        assert listing.title == sample_listing_data.title

    def test_get_listing_not_found(self, listing_service):
        """Should return None when listing doesn't exist."""
        listing = listing_service.get_listing(9999)
        assert listing is None


class TestListingServiceDeleteListing:
    """Tests for ListingService.delete_listing()."""

    def test_delete_listing_exists(self, in_memory_session, sample_listing_data):
        """Should return True when listing is deleted."""
        repo = ListingRepository(in_memory_session)
        created = repo.create_listing(sample_listing_data)

        service = ListingService(in_memory_session)
        result = service.delete_listing(created.id)

        assert result is True
        # Verify deleted
        assert repo.get_listing_by_id(created.id) is None

    def test_delete_listing_not_found(self, listing_service):
        """Should return False when listing doesn't exist."""
        result = listing_service.delete_listing(9999)
        assert result is False
