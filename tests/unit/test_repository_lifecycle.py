"""Tests for repository lifecycle methods."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from i4_scout.database.repository import ListingRepository
from i4_scout.models.db_models import Base, Listing
from i4_scout.models.pydantic_models import ListingCreate, ListingStatus, Source


@pytest.fixture
def session() -> Session:
    """Create an in-memory SQLite database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


@pytest.fixture
def repo(session: Session) -> ListingRepository:
    """Create a repository instance."""
    return ListingRepository(session)


@pytest.fixture
def sample_listings(repo: ListingRepository) -> list[Listing]:
    """Create sample listings for testing."""
    listings = []
    for i in range(3):
        listing = repo.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url=f"https://example.com/listing/{i}",
                title=f"Test BMW i4 #{i}",
                price=45000 + i * 1000,
            )
        )
        listings.append(listing)
    return listings


class TestGetActiveListingsBySource:
    """Test get_active_listings_by_source method."""

    def test_returns_active_listings(self, repo: ListingRepository, sample_listings: list[Listing]) -> None:
        """Should return only active listings for the source."""
        # All listings start as active
        active = repo.get_active_listings_by_source(Source.AUTOSCOUT24_DE)
        assert len(active) == 3

    def test_excludes_delisted_listings(self, repo: ListingRepository, sample_listings: list[Listing]) -> None:
        """Should exclude delisted listings."""
        # Mark one as delisted
        repo.update_listing_status(sample_listings[0].id, ListingStatus.DELISTED)

        active = repo.get_active_listings_by_source(Source.AUTOSCOUT24_DE)
        assert len(active) == 2
        assert sample_listings[0].id not in [l.id for l in active]

    def test_filters_by_source(self, repo: ListingRepository, sample_listings: list[Listing]) -> None:
        """Should only return listings for the specified source."""
        # Create listing for different source
        repo.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_NL,
                url="https://example.com/nl/listing/1",
                title="Dutch BMW i4",
            )
        )

        active_de = repo.get_active_listings_by_source(Source.AUTOSCOUT24_DE)
        active_nl = repo.get_active_listings_by_source(Source.AUTOSCOUT24_NL)

        assert len(active_de) == 3
        assert len(active_nl) == 1


class TestIncrementConsecutiveMisses:
    """Test increment_consecutive_misses method."""

    def test_increments_miss_count(self, repo: ListingRepository, sample_listings: list[Listing]) -> None:
        """Should increment consecutive_misses for specified listing IDs."""
        listing_ids = [sample_listings[0].id, sample_listings[1].id]
        repo.increment_consecutive_misses(listing_ids)

        # Refresh from DB
        l0 = repo.get_listing_by_id(sample_listings[0].id)
        l1 = repo.get_listing_by_id(sample_listings[1].id)
        l2 = repo.get_listing_by_id(sample_listings[2].id)

        assert l0 is not None and l0.consecutive_misses == 1
        assert l1 is not None and l1.consecutive_misses == 1
        assert l2 is not None and l2.consecutive_misses == 0  # Not incremented

    def test_increments_multiple_times(self, repo: ListingRepository, sample_listings: list[Listing]) -> None:
        """Should increment correctly on multiple calls."""
        listing_ids = [sample_listings[0].id]
        repo.increment_consecutive_misses(listing_ids)
        repo.increment_consecutive_misses(listing_ids)

        listing = repo.get_listing_by_id(sample_listings[0].id)
        assert listing is not None and listing.consecutive_misses == 2

    def test_empty_list_no_op(self, repo: ListingRepository, sample_listings: list[Listing]) -> None:
        """Should handle empty list gracefully."""
        repo.increment_consecutive_misses([])
        # No error should occur


class TestResetConsecutiveMisses:
    """Test reset_consecutive_misses method."""

    def test_resets_miss_count(self, repo: ListingRepository, sample_listings: list[Listing]) -> None:
        """Should reset consecutive_misses to 0 for specified listing IDs."""
        # First increment
        repo.increment_consecutive_misses([l.id for l in sample_listings])

        # Then reset one
        repo.reset_consecutive_misses([sample_listings[0].id])

        l0 = repo.get_listing_by_id(sample_listings[0].id)
        l1 = repo.get_listing_by_id(sample_listings[1].id)

        assert l0 is not None and l0.consecutive_misses == 0  # Reset
        assert l1 is not None and l1.consecutive_misses == 1  # Not reset

    def test_empty_list_no_op(self, repo: ListingRepository, sample_listings: list[Listing]) -> None:
        """Should handle empty list gracefully."""
        repo.reset_consecutive_misses([])
        # No error should occur


class TestUpdateListingStatus:
    """Test update_listing_status method."""

    def test_changes_status_to_delisted(self, repo: ListingRepository, sample_listings: list[Listing]) -> None:
        """Should update status to delisted."""
        result = repo.update_listing_status(sample_listings[0].id, ListingStatus.DELISTED)

        assert result is not None
        assert result.status == ListingStatus.DELISTED
        assert result.status_changed_at is not None

    def test_changes_status_back_to_active(self, repo: ListingRepository, sample_listings: list[Listing]) -> None:
        """Should update status back to active."""
        # First delist
        repo.update_listing_status(sample_listings[0].id, ListingStatus.DELISTED)

        # Then reactivate
        result = repo.update_listing_status(sample_listings[0].id, ListingStatus.ACTIVE)

        assert result is not None
        assert result.status == ListingStatus.ACTIVE

    def test_sets_status_changed_at(self, repo: ListingRepository, sample_listings: list[Listing]) -> None:
        """Should set status_changed_at when changing status."""
        before = datetime.now(timezone.utc)
        repo.update_listing_status(sample_listings[0].id, ListingStatus.DELISTED)
        after = datetime.now(timezone.utc)

        listing = repo.get_listing_by_id(sample_listings[0].id)
        assert listing is not None
        assert listing.status_changed_at is not None
        # Check timestamp is within range (allowing for some execution time)
        assert before <= listing.status_changed_at.replace(tzinfo=timezone.utc) <= after

    def test_returns_none_for_nonexistent(self, repo: ListingRepository) -> None:
        """Should return None for nonexistent listing."""
        result = repo.update_listing_status(99999, ListingStatus.DELISTED)
        assert result is None


class TestStatusFilter:
    """Test status filter in _apply_listing_filters."""

    def test_filter_active_only(self, repo: ListingRepository, sample_listings: list[Listing]) -> None:
        """Should filter to only active listings."""
        # Delist one
        repo.update_listing_status(sample_listings[0].id, ListingStatus.DELISTED)

        listings = repo.get_listings(status=ListingStatus.ACTIVE)
        assert len(listings) == 2

    def test_filter_delisted_only(self, repo: ListingRepository, sample_listings: list[Listing]) -> None:
        """Should filter to only delisted listings."""
        # Delist one
        repo.update_listing_status(sample_listings[0].id, ListingStatus.DELISTED)

        listings = repo.get_listings(status=ListingStatus.DELISTED)
        assert len(listings) == 1
        assert listings[0].id == sample_listings[0].id

    def test_no_filter_returns_all(self, repo: ListingRepository, sample_listings: list[Listing]) -> None:
        """Should return all listings when no status filter."""
        # Delist one
        repo.update_listing_status(sample_listings[0].id, ListingStatus.DELISTED)

        listings = repo.get_listings()
        assert len(listings) == 3
