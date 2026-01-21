"""Unit tests for issue toggle functionality in ListingRepository."""

from datetime import date

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


@pytest.fixture
def sample_listing_data() -> ListingCreate:
    """Create sample listing data for testing."""
    return ListingCreate(
        source=Source.AUTOSCOUT24_DE,
        external_id="12345",
        url="https://www.autoscout24.de/angebote/test-listing-12345",
        title="BMW i4 eDrive40 2023",
        price=5500000,
        mileage_km=15000,
        year=2023,
        first_registration=date(2023, 3, 1),
        is_qualified=True,
    )


class TestIssueToggle:
    """Tests for issue toggle functionality."""

    def test_new_listing_has_issue_false_by_default(
        self, repository: ListingRepository, sample_listing_data: ListingCreate
    ):
        """New listings should have has_issue=False by default."""
        listing = repository.create_listing(sample_listing_data)
        assert listing.has_issue is False

    def test_toggle_issue_to_true(
        self, repository: ListingRepository, sample_listing_data: ListingCreate
    ):
        """Should set has_issue to True."""
        listing = repository.create_listing(sample_listing_data)
        assert listing.has_issue is False

        updated = repository.toggle_issue(listing.id, has_issue=True)
        assert updated is not None
        assert updated.has_issue is True

    def test_toggle_issue_to_false(
        self, repository: ListingRepository, sample_listing_data: ListingCreate
    ):
        """Should set has_issue to False."""
        # Create listing with issue
        sample_listing_data.has_issue = True
        listing = repository.create_listing(sample_listing_data)
        assert listing.has_issue is True

        updated = repository.toggle_issue(listing.id, has_issue=False)
        assert updated is not None
        assert updated.has_issue is False

    def test_toggle_issue_not_found(self, repository: ListingRepository):
        """Should return None when listing not found."""
        result = repository.toggle_issue(99999, has_issue=True)
        assert result is None


class TestFilterByIssue:
    """Tests for filtering listings by issue status."""

    def test_filter_listings_with_issue(self, repository: ListingRepository):
        """Should filter listings that have issues."""
        # Create listings with and without issues
        for i in range(5):
            data = ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url=f"https://example.com/listing/{i}",
                title=f"Test Listing {i}",
                has_issue=(i % 2 == 0),  # 0, 2, 4 have issues
            )
            repository.create_listing(data)

        # Filter by has_issue=True
        listings_with_issues = repository.get_listings(has_issue=True)
        assert len(listings_with_issues) == 3

        for listing in listings_with_issues:
            assert listing.has_issue is True

    def test_filter_listings_without_issue(self, repository: ListingRepository):
        """Should filter listings that don't have issues."""
        # Create listings with and without issues
        for i in range(5):
            data = ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url=f"https://example.com/listing/{i}",
                title=f"Test Listing {i}",
                has_issue=(i % 2 == 0),  # 0, 2, 4 have issues
            )
            repository.create_listing(data)

        # Filter by has_issue=False
        listings_without_issues = repository.get_listings(has_issue=False)
        assert len(listings_without_issues) == 2

        for listing in listings_without_issues:
            assert listing.has_issue is False

    def test_filter_listings_no_issue_filter(self, repository: ListingRepository):
        """Should return all listings when has_issue filter is None."""
        # Create listings with and without issues
        for i in range(5):
            data = ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url=f"https://example.com/listing/{i}",
                title=f"Test Listing {i}",
                has_issue=(i % 2 == 0),
            )
            repository.create_listing(data)

        # No filter
        all_listings = repository.get_listings(has_issue=None)
        assert len(all_listings) == 5

    def test_count_listings_with_issue_filter(self, repository: ListingRepository):
        """Should count listings correctly with issue filter."""
        for i in range(5):
            data = ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url=f"https://example.com/listing/{i}",
                title=f"Test Listing {i}",
                has_issue=(i % 2 == 0),
            )
            repository.create_listing(data)

        assert repository.count_listings(has_issue=True) == 3
        assert repository.count_listings(has_issue=False) == 2
        assert repository.count_listings() == 5
