"""Tests for repository dashboard methods."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from i4_scout.database.repository import ListingRepository
from i4_scout.models.db_models import Base, Listing, Option, PriceHistory
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


class TestGetListingsWithPriceDrops:
    """Test get_listings_with_price_drops method."""

    def test_returns_listings_with_price_drops(self, repo: ListingRepository, session: Session) -> None:
        """Should return listings where current price is lower than original."""
        # Create a listing
        listing = repo.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com/listing/1",
                title="BMW i4 with price drop",
                price=45000,
            )
        )

        # Record original price (first price history entry is created by upsert)
        # Manually add original price
        original_price = PriceHistory(
            listing_id=listing.id,
            price=50000,
            recorded_at=datetime.now(timezone.utc) - timedelta(days=5),
        )
        session.add(original_price)
        session.commit()

        # Update listing to current (lower) price
        listing.price = 45000
        session.commit()

        # Query
        results = repo.get_listings_with_price_drops(days=7, limit=10)

        assert len(results) == 1
        result_listing, original, current = results[0]
        assert result_listing.id == listing.id
        assert original == 50000
        assert current == 45000

    def test_excludes_price_increases(self, repo: ListingRepository, session: Session) -> None:
        """Should not return listings with price increases."""
        listing = repo.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com/listing/2",
                title="BMW i4 with price increase",
                price=55000,
            )
        )

        # Record original (lower) price
        original_price = PriceHistory(
            listing_id=listing.id,
            price=50000,
            recorded_at=datetime.now(timezone.utc) - timedelta(days=5),
        )
        session.add(original_price)
        session.commit()

        results = repo.get_listings_with_price_drops(days=7, limit=10)
        assert len(results) == 0

    def test_excludes_delisted_listings(self, repo: ListingRepository, session: Session) -> None:
        """Should not return delisted listings."""
        listing = repo.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com/listing/3",
                title="BMW i4 delisted",
                price=45000,
            )
        )

        original_price = PriceHistory(
            listing_id=listing.id,
            price=50000,
            recorded_at=datetime.now(timezone.utc) - timedelta(days=5),
        )
        session.add(original_price)
        listing.status = ListingStatus.DELISTED
        session.commit()

        results = repo.get_listings_with_price_drops(days=7, limit=10)
        assert len(results) == 0

    def test_empty_when_no_price_history(self, repo: ListingRepository) -> None:
        """Should return empty list when no listings have price history."""
        repo.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com/listing/4",
                title="BMW i4 no history",
                price=45000,
            )
        )

        results = repo.get_listings_with_price_drops(days=7, limit=10)
        assert len(results) == 0


class TestGetNearMissListings:
    """Test get_near_miss_listings method."""

    def test_returns_high_score_unqualified_listings(self, repo: ListingRepository) -> None:
        """Should return listings with high score but not qualified."""
        # Create an unqualified listing with high score
        repo.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com/listing/1",
                title="BMW i4 near miss",
                price=45000,
                match_score=85.0,
                is_qualified=False,
            )
        )

        results = repo.get_near_miss_listings(threshold=80.0, limit=10)

        assert len(results) == 1
        listing, matched_options = results[0]
        assert listing.match_score == 85.0
        assert listing.is_qualified is False

    def test_excludes_qualified_listings(self, repo: ListingRepository) -> None:
        """Should not return qualified listings even with high score."""
        repo.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com/listing/2",
                title="BMW i4 qualified",
                price=45000,
                match_score=90.0,
                is_qualified=True,
            )
        )

        results = repo.get_near_miss_listings(threshold=80.0, limit=10)
        assert len(results) == 0

    def test_excludes_low_score_listings(self, repo: ListingRepository) -> None:
        """Should not return listings below threshold."""
        repo.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com/listing/3",
                title="BMW i4 low score",
                price=45000,
                match_score=50.0,
                is_qualified=False,
            )
        )

        results = repo.get_near_miss_listings(threshold=80.0, limit=10)
        assert len(results) == 0

    def test_excludes_delisted_listings(self, repo: ListingRepository) -> None:
        """Should not return delisted listings."""
        listing = repo.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com/listing/4",
                title="BMW i4 delisted near miss",
                price=45000,
                match_score=85.0,
                is_qualified=False,
            )
        )
        repo.update_listing_status(listing.id, ListingStatus.DELISTED)

        results = repo.get_near_miss_listings(threshold=80.0, limit=10)
        assert len(results) == 0

    def test_orders_by_score_descending(self, repo: ListingRepository) -> None:
        """Should order results by score descending."""
        repo.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com/listing/5",
                title="BMW i4 score 82",
                match_score=82.0,
                is_qualified=False,
            )
        )
        repo.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com/listing/6",
                title="BMW i4 score 90",
                match_score=90.0,
                is_qualified=False,
            )
        )
        repo.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com/listing/7",
                title="BMW i4 score 85",
                match_score=85.0,
                is_qualified=False,
            )
        )

        results = repo.get_near_miss_listings(threshold=80.0, limit=10)

        assert len(results) == 3
        scores = [listing.match_score for listing, _ in results]
        assert scores == [90.0, 85.0, 82.0]


class TestGetMarketVelocity:
    """Test get_market_velocity method."""

    def test_counts_new_listings(self, repo: ListingRepository, session: Session) -> None:
        """Should count listings first seen within the window."""
        # Create listing from today
        repo.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com/listing/1",
                title="BMW i4 new",
            )
        )

        # Create listing from 10 days ago (outside window)
        old_listing = repo.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com/listing/2",
                title="BMW i4 old",
            )
        )
        old_listing.first_seen_at = datetime.now(timezone.utc) - timedelta(days=10)
        session.commit()

        velocity = repo.get_market_velocity(days=7)

        assert velocity["new"] == 1

    def test_counts_delisted_listings(self, repo: ListingRepository, session: Session) -> None:
        """Should count listings delisted within the window."""
        listing = repo.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com/listing/3",
                title="BMW i4 delisted",
            )
        )
        listing.status = ListingStatus.DELISTED
        listing.status_changed_at = datetime.now(timezone.utc) - timedelta(days=2)
        session.commit()

        velocity = repo.get_market_velocity(days=7)

        assert velocity["delisted"] == 1

    def test_calculates_net_change(self, repo: ListingRepository, session: Session) -> None:
        """Should calculate net = new - delisted."""
        # 2 new listings
        for i in range(2):
            repo.create_listing(
                ListingCreate(
                    source=Source.AUTOSCOUT24_DE,
                    url=f"https://example.com/listing/new/{i}",
                    title=f"BMW i4 new {i}",
                )
            )

        # 1 delisted listing
        delisted = repo.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com/listing/delisted",
                title="BMW i4 delisted",
            )
        )
        delisted.status = ListingStatus.DELISTED
        delisted.status_changed_at = datetime.now(timezone.utc)
        session.commit()

        velocity = repo.get_market_velocity(days=7)

        assert velocity["new"] == 3  # Including the delisted one which is also new
        assert velocity["delisted"] == 1
        assert velocity["net"] == 2

    def test_returns_active_and_qualified_totals(self, repo: ListingRepository) -> None:
        """Should return total active and qualified counts."""
        # Active qualified
        repo.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com/listing/q1",
                title="BMW i4 qualified",
                is_qualified=True,
            )
        )

        # Active not qualified
        repo.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com/listing/nq1",
                title="BMW i4 not qualified",
                is_qualified=False,
            )
        )

        # Delisted qualified (should not count)
        delisted = repo.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com/listing/dq",
                title="BMW i4 delisted qualified",
                is_qualified=True,
            )
        )
        repo.update_listing_status(delisted.id, ListingStatus.DELISTED)

        velocity = repo.get_market_velocity(days=7)

        assert velocity["active_total"] == 2
        assert velocity["qualified_count"] == 1


class TestGetOptionFrequency:
    """Test get_option_frequency method."""

    def test_returns_option_frequencies(self, repo: ListingRepository, session: Session) -> None:
        """Should return option counts and percentages."""
        # Create options
        opt1, _ = repo.get_or_create_option("M Sport Package")
        opt2, _ = repo.get_or_create_option("Laser Light")

        # Create listings with options
        listing1 = repo.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com/listing/1",
                title="BMW i4 #1",
            )
        )
        listing2 = repo.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com/listing/2",
                title="BMW i4 #2",
            )
        )

        # Add options to listings
        repo.add_option_to_listing(listing1.id, opt1.id)
        repo.add_option_to_listing(listing1.id, opt2.id)
        repo.add_option_to_listing(listing2.id, opt1.id)

        frequencies = repo.get_option_frequency()

        assert len(frequencies) == 2

        # M Sport Package should be first (2 listings = 100%)
        m_sport = next(f for f in frequencies if f["name"] == "M Sport Package")
        assert m_sport["count"] == 2
        assert m_sport["percentage"] == 100.0

        # Laser Light (1 listing = 50%)
        laser = next(f for f in frequencies if f["name"] == "Laser Light")
        assert laser["count"] == 1
        assert laser["percentage"] == 50.0

    def test_filters_by_status(self, repo: ListingRepository, session: Session) -> None:
        """Should only count options from active listings by default."""
        opt, _ = repo.get_or_create_option("Test Option")

        # Active listing
        active = repo.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com/listing/active",
                title="BMW i4 active",
            )
        )
        repo.add_option_to_listing(active.id, opt.id)

        # Delisted listing
        delisted = repo.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com/listing/delisted",
                title="BMW i4 delisted",
            )
        )
        repo.add_option_to_listing(delisted.id, opt.id)
        repo.update_listing_status(delisted.id, ListingStatus.DELISTED)

        frequencies = repo.get_option_frequency(status=ListingStatus.ACTIVE)

        assert len(frequencies) == 1
        assert frequencies[0]["count"] == 1
        assert frequencies[0]["percentage"] == 100.0

    def test_returns_empty_when_no_listings(self, repo: ListingRepository) -> None:
        """Should return empty list when no listings exist."""
        frequencies = repo.get_option_frequency()
        assert frequencies == []

    def test_returns_empty_when_no_options(self, repo: ListingRepository) -> None:
        """Should return empty list when listings have no options."""
        repo.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com/listing/no-options",
                title="BMW i4 no options",
            )
        )

        frequencies = repo.get_option_frequency()
        assert frequencies == []
