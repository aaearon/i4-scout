"""Tests for repository lifecycle methods."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from i4_scout.database.repository import ListingRepository, ScrapeJobRepository
from i4_scout.models.db_models import Base, Listing, ScrapeJob
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


class TestMarkListingsAtDelistThreshold:
    """Test mark_listings_at_delist_threshold method."""

    def test_marks_listings_with_two_misses(
        self, repo: ListingRepository, sample_listings: list[Listing]
    ) -> None:
        """Should mark listings with consecutive_misses >= 2 as delisted."""
        listing_ids = [sample_listings[0].id]
        # First miss
        repo.increment_consecutive_misses(listing_ids)
        # Second miss
        repo.increment_consecutive_misses(listing_ids)

        # Verify consecutive_misses is 2
        listing = repo.get_listing_by_id(sample_listings[0].id)
        assert listing is not None and listing.consecutive_misses == 2

        # Call the method
        count = repo.mark_listings_at_delist_threshold(listing_ids)

        assert count == 1
        listing = repo.get_listing_by_id(sample_listings[0].id)
        assert listing is not None
        assert listing.status == ListingStatus.DELISTED
        assert listing.status_changed_at is not None

    def test_does_not_mark_listings_with_one_miss(
        self, repo: ListingRepository, sample_listings: list[Listing]
    ) -> None:
        """Should not mark listings with consecutive_misses < 2."""
        listing_ids = [sample_listings[0].id]
        # Only one miss
        repo.increment_consecutive_misses(listing_ids)

        # Verify consecutive_misses is 1
        listing = repo.get_listing_by_id(sample_listings[0].id)
        assert listing is not None and listing.consecutive_misses == 1

        # Call the method
        count = repo.mark_listings_at_delist_threshold(listing_ids)

        assert count == 0
        listing = repo.get_listing_by_id(sample_listings[0].id)
        assert listing is not None
        assert listing.status == ListingStatus.ACTIVE

    def test_only_marks_active_listings(
        self, repo: ListingRepository, sample_listings: list[Listing]
    ) -> None:
        """Should only affect listings with ACTIVE status."""
        listing_ids = [sample_listings[0].id]
        # Two misses
        repo.increment_consecutive_misses(listing_ids)
        repo.increment_consecutive_misses(listing_ids)
        # Manually mark as delisted first
        repo.update_listing_status(sample_listings[0].id, ListingStatus.DELISTED)

        # Call again - should not double-mark
        count = repo.mark_listings_at_delist_threshold(listing_ids)
        assert count == 0

    def test_handles_empty_list(self, repo: ListingRepository) -> None:
        """Should handle empty list gracefully."""
        count = repo.mark_listings_at_delist_threshold([])
        assert count == 0

    def test_atomic_operation_preserves_consecutive_misses(
        self, repo: ListingRepository, sample_listings: list[Listing]
    ) -> None:
        """Should preserve consecutive_misses value when marking as delisted.

        This is the key test for the bug fix - ensures the atomic update
        doesn't overwrite consecutive_misses with stale values.
        """
        listing_id = sample_listings[0].id
        # Simulate two misses
        repo.increment_consecutive_misses([listing_id])
        repo.increment_consecutive_misses([listing_id])

        # Mark as delisted
        repo.mark_listings_at_delist_threshold([listing_id])

        # Verify consecutive_misses is still 2, not reset to a stale value
        listing = repo.get_listing_by_id(listing_id)
        assert listing is not None
        assert listing.consecutive_misses == 2
        assert listing.status == ListingStatus.DELISTED


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


class TestJobListingAssociation:
    """Tests for job-listing association tracking."""

    @pytest.fixture
    def job_repo(self, session: Session) -> ScrapeJobRepository:
        """Create a job repository instance."""
        return ScrapeJobRepository(session)

    @pytest.fixture
    def sample_job(self, job_repo: ScrapeJobRepository) -> ScrapeJob:
        """Create a sample scrape job."""
        return job_repo.create_job(
            source=Source.AUTOSCOUT24_DE,
            max_pages=10,
            search_filters=None,
        )

    def test_add_job_listing_association(
        self, repo: ListingRepository, sample_listings: list[Listing], sample_job: ScrapeJob
    ) -> None:
        """Should create job-listing association."""
        assoc = repo.add_job_listing_association(
            job_id=sample_job.id,
            listing_id=sample_listings[0].id,
            status="new",
        )

        assert assoc.scrape_job_id == sample_job.id
        assert assoc.listing_id == sample_listings[0].id
        assert assoc.status == "new"

    def test_get_job_listings_all(
        self, repo: ListingRepository, sample_listings: list[Listing], sample_job: ScrapeJob
    ) -> None:
        """Should return all listings for a job."""
        # Add associations
        repo.add_job_listing_association(sample_job.id, sample_listings[0].id, "new")
        repo.add_job_listing_association(sample_job.id, sample_listings[1].id, "updated")
        repo.add_job_listing_association(sample_job.id, sample_listings[2].id, "unchanged")

        listings = repo.get_job_listings(sample_job.id)
        assert len(listings) == 3

    def test_get_job_listings_filtered_by_status(
        self, repo: ListingRepository, sample_listings: list[Listing], sample_job: ScrapeJob
    ) -> None:
        """Should filter job listings by status."""
        # Add associations with different statuses
        repo.add_job_listing_association(sample_job.id, sample_listings[0].id, "new")
        repo.add_job_listing_association(sample_job.id, sample_listings[1].id, "updated")
        repo.add_job_listing_association(sample_job.id, sample_listings[2].id, "unchanged")

        new_listings = repo.get_job_listings(sample_job.id, status="new")
        assert len(new_listings) == 1
        assert new_listings[0].id == sample_listings[0].id

        updated_listings = repo.get_job_listings(sample_job.id, status="updated")
        assert len(updated_listings) == 1
        assert updated_listings[0].id == sample_listings[1].id

    def test_get_job_listings_empty(
        self, repo: ListingRepository, sample_job: ScrapeJob
    ) -> None:
        """Should return empty list for job with no listings."""
        listings = repo.get_job_listings(sample_job.id)
        assert len(listings) == 0

    def test_job_listing_association_idempotent(
        self, repo: ListingRepository, sample_listings: list[Listing], sample_job: ScrapeJob
    ) -> None:
        """Should return existing association when listing appears on multiple pages."""
        first = repo.add_job_listing_association(sample_job.id, sample_listings[0].id, "new")

        # Adding the same listing again returns existing association (first status wins)
        second = repo.add_job_listing_association(sample_job.id, sample_listings[0].id, "updated")

        assert second.id == first.id
        assert second.status == "new"  # First status preserved
