"""Integration tests for the repository layer."""

import hashlib
from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from i4_scout.database.repository import ListingRepository
from i4_scout.models.db_models import Base, Listing, Option, ListingOption, PriceHistory
from i4_scout.models.pydantic_models import ListingCreate, Source


@pytest.fixture
def db_session():
    """Create an in-memory database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
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
        price=5500000,  # 55,000 EUR in cents
        price_text="55.000 €",
        mileage_km=15000,
        year=2023,
        first_registration=date(2023, 3, 1),
        location_city="Berlin",
        location_zip="10115",
        location_country="DE",
        dealer_name="BMW Berlin",
        dealer_type="dealer",
        description="Beautiful BMW i4 eDrive40 with full options",
        raw_options_text="HUD, Parking Assistant Plus, Driving Assistant Pro",
        photo_urls=["https://example.com/photo1.jpg", "https://example.com/photo2.jpg"],
        match_score=85.5,
        is_qualified=True,
    )


class TestListingRepository:
    """Tests for ListingRepository CRUD operations."""

    def test_create_listing(self, repository: ListingRepository, sample_listing_data: ListingCreate):
        """Should create a new listing in the database."""
        listing = repository.create_listing(sample_listing_data)

        assert listing.id is not None
        assert listing.source == Source.AUTOSCOUT24_DE.value
        assert listing.external_id == "12345"
        assert listing.title == "BMW i4 eDrive40 2023"
        assert listing.price == 5500000
        assert listing.mileage_km == 15000
        assert listing.is_qualified is True

    def test_get_listing_by_id(self, repository: ListingRepository, sample_listing_data: ListingCreate):
        """Should retrieve a listing by ID."""
        created = repository.create_listing(sample_listing_data)
        fetched = repository.get_listing_by_id(created.id)

        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.title == created.title

    def test_get_listing_by_id_not_found(self, repository: ListingRepository):
        """Should return None for non-existent ID."""
        result = repository.get_listing_by_id(99999)
        assert result is None

    def test_get_listing_by_url(self, repository: ListingRepository, sample_listing_data: ListingCreate):
        """Should retrieve a listing by URL."""
        created = repository.create_listing(sample_listing_data)
        fetched = repository.get_listing_by_url(sample_listing_data.url)

        assert fetched is not None
        assert fetched.id == created.id

    def test_get_listing_by_url_not_found(self, repository: ListingRepository):
        """Should return None for non-existent URL."""
        result = repository.get_listing_by_url("https://nonexistent.com/listing")
        assert result is None

    def test_get_listings_with_filters(self, repository: ListingRepository):
        """Should filter listings by source and qualification."""
        # Create multiple listings
        for i in range(5):
            data = ListingCreate(
                source=Source.AUTOSCOUT24_DE if i < 3 else Source.AUTOSCOUT24_NL,
                url=f"https://example.com/listing/{i}",
                title=f"Test Listing {i}",
                price=5000000 + i * 100000,
                is_qualified=i % 2 == 0,
            )
            repository.create_listing(data)

        # Filter by source
        de_listings = repository.get_listings(source=Source.AUTOSCOUT24_DE)
        assert len(de_listings) == 3

        nl_listings = repository.get_listings(source=Source.AUTOSCOUT24_NL)
        assert len(nl_listings) == 2

        # Filter by qualification
        qualified = repository.get_listings(qualified_only=True)
        assert len(qualified) == 3  # i=0, 2, 4

    def test_get_listings_with_pagination(self, repository: ListingRepository):
        """Should support limit and offset for pagination."""
        # Create 10 listings
        for i in range(10):
            data = ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url=f"https://example.com/listing/{i}",
                title=f"Test Listing {i}",
            )
            repository.create_listing(data)

        # Get first page
        page1 = repository.get_listings(limit=3, offset=0)
        assert len(page1) == 3

        # Get second page
        page2 = repository.get_listings(limit=3, offset=3)
        assert len(page2) == 3
        assert page1[0].id != page2[0].id

    def test_update_listing(self, repository: ListingRepository, sample_listing_data: ListingCreate):
        """Should update an existing listing."""
        created = repository.create_listing(sample_listing_data)
        original_price = created.price

        updated = repository.update_listing(
            created.id,
            price=4900000,
            match_score=90.0,
            is_qualified=True,
        )

        assert updated is not None
        assert updated.price == 4900000
        assert updated.price != original_price
        assert updated.match_score == 90.0

    def test_update_listing_not_found(self, repository: ListingRepository):
        """Should return None when updating non-existent listing."""
        result = repository.update_listing(99999, price=1000)
        assert result is None

    def test_delete_listing(self, repository: ListingRepository, sample_listing_data: ListingCreate):
        """Should delete a listing by ID."""
        created = repository.create_listing(sample_listing_data)
        listing_id = created.id

        result = repository.delete_listing(listing_id)
        assert result is True

        # Verify deleted
        fetched = repository.get_listing_by_id(listing_id)
        assert fetched is None

    def test_delete_listing_not_found(self, repository: ListingRepository):
        """Should return False when deleting non-existent listing."""
        result = repository.delete_listing(99999)
        assert result is False


class TestUpsertAndDedup:
    """Tests for upsert and deduplication logic."""

    def test_upsert_creates_new_listing(
        self, repository: ListingRepository, sample_listing_data: ListingCreate
    ):
        """upsert should create a new listing if URL doesn't exist."""
        listing, created = repository.upsert_listing(sample_listing_data)

        assert created is True
        assert listing.id is not None
        assert listing.title == sample_listing_data.title

    def test_upsert_updates_existing_listing(
        self, repository: ListingRepository, sample_listing_data: ListingCreate
    ):
        """upsert should update existing listing if URL exists."""
        # Create initial listing
        original, _ = repository.upsert_listing(sample_listing_data)
        original_id = original.id

        # Upsert with same URL but different data
        updated_data = ListingCreate(
            source=sample_listing_data.source,
            url=sample_listing_data.url,  # Same URL
            title=sample_listing_data.title,
            price=5000000,  # Changed price
            mileage_km=16000,  # Changed mileage
        )
        updated, created = repository.upsert_listing(updated_data)

        assert created is False
        assert updated.id == original_id  # Same listing
        assert updated.price == 5000000
        assert updated.mileage_km == 16000

    def test_upsert_records_price_history(
        self, repository: ListingRepository, sample_listing_data: ListingCreate
    ):
        """upsert should record price changes in history."""
        # Create initial listing
        original, _ = repository.upsert_listing(sample_listing_data)

        # Update with new price
        updated_data = ListingCreate(
            source=sample_listing_data.source,
            url=sample_listing_data.url,
            title=sample_listing_data.title,
            price=5000000,  # New price
        )
        repository.upsert_listing(updated_data)

        # Check price history
        history = repository.get_price_history(original.id)
        assert len(history) >= 1

    def test_compute_dedup_hash(self, repository: ListingRepository):
        """Should compute consistent dedup hash."""
        hash1 = repository.compute_dedup_hash(
            source=Source.AUTOSCOUT24_DE,
            title="BMW i4 eDrive40",
            price=5500000,
            mileage_km=15000,
            year=2023,
        )

        hash2 = repository.compute_dedup_hash(
            source=Source.AUTOSCOUT24_DE,
            title="BMW i4 eDrive40",
            price=5500000,
            mileage_km=15000,
            year=2023,
        )

        # Same inputs should produce same hash
        assert hash1 == hash2

        # Different inputs should produce different hash
        hash3 = repository.compute_dedup_hash(
            source=Source.AUTOSCOUT24_DE,
            title="BMW i4 eDrive40",
            price=5600000,  # Different price
            mileage_km=15000,
            year=2023,
        )
        assert hash1 != hash3

    def test_find_duplicate_by_attributes(self, repository: ListingRepository):
        """Should find potential duplicates by attributes."""
        data = ListingCreate(
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com/listing/1",
            title="BMW i4 eDrive40",
            price=5500000,
            mileage_km=15000,
            year=2023,
        )
        repository.create_listing(data)

        # Search for duplicate with same attributes
        duplicate = repository.find_duplicate(
            source=Source.AUTOSCOUT24_DE,
            title="BMW i4 eDrive40",
            price=5500000,
            mileage_km=15000,
            year=2023,
        )

        assert duplicate is not None
        assert duplicate.title == "BMW i4 eDrive40"


class TestPriceHistory:
    """Tests for price history tracking."""

    def test_record_price_change(
        self, repository: ListingRepository, sample_listing_data: ListingCreate
    ):
        """Should record price changes."""
        listing = repository.create_listing(sample_listing_data)

        repository.record_price_change(listing.id, 5500000)
        repository.record_price_change(listing.id, 5300000)
        repository.record_price_change(listing.id, 5100000)

        history = repository.get_price_history(listing.id)
        assert len(history) == 3
        prices = [h.price for h in history]
        assert 5500000 in prices
        assert 5300000 in prices
        assert 5100000 in prices

    def test_get_price_history_ordered(
        self, repository: ListingRepository, sample_listing_data: ListingCreate
    ):
        """Price history should be ordered by recorded_at descending."""
        listing = repository.create_listing(sample_listing_data)

        repository.record_price_change(listing.id, 5500000)
        repository.record_price_change(listing.id, 5300000)
        repository.record_price_change(listing.id, 5100000)

        history = repository.get_price_history(listing.id)
        # Most recent first
        assert history[0].price == 5100000
        assert history[-1].price == 5500000


class TestOptionAssociation:
    """Tests for associating options with listings."""

    def test_add_option_to_listing(
        self, repository: ListingRepository, db_session: Session, sample_listing_data: ListingCreate
    ):
        """Should associate an option with a listing."""
        # Create listing and option
        listing = repository.create_listing(sample_listing_data)
        option = Option(
            canonical_name="head_up_display",
            display_name="Head-Up Display",
            category="comfort",
        )
        db_session.add(option)
        db_session.commit()

        # Associate option
        listing_option = repository.add_option_to_listing(
            listing_id=listing.id,
            option_id=option.id,
            raw_text="HUD",
            confidence=0.95,
        )

        assert listing_option is not None
        assert listing_option.listing_id == listing.id
        assert listing_option.option_id == option.id
        assert listing_option.confidence == 0.95

    def test_get_listing_options(
        self, repository: ListingRepository, db_session: Session, sample_listing_data: ListingCreate
    ):
        """Should get all options for a listing."""
        # Create listing
        listing = repository.create_listing(sample_listing_data)

        # Create options
        option1 = Option(canonical_name="hud", display_name="HUD", category="comfort")
        option2 = Option(canonical_name="park_assist", display_name="Park Assist", category="safety")
        db_session.add_all([option1, option2])
        db_session.commit()

        # Associate options
        repository.add_option_to_listing(listing.id, option1.id, "HUD")
        repository.add_option_to_listing(listing.id, option2.id, "Parking Assistant")

        # Get options
        options = repository.get_listing_options(listing.id)
        assert len(options) == 2


class TestBulkOperations:
    """Tests for bulk database operations."""

    def test_bulk_create_listings(self, repository: ListingRepository):
        """Should create multiple listings efficiently."""
        listings_data = [
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url=f"https://example.com/listing/{i}",
                title=f"Test Listing {i}",
                price=5000000 + i * 100000,
            )
            for i in range(10)
        ]

        created = repository.bulk_create_listings(listings_data)
        assert len(created) == 10

        # Verify all created
        all_listings = repository.get_listings()
        assert len(all_listings) == 10

    def test_get_listings_count(self, repository: ListingRepository):
        """Should return correct count of listings."""
        for i in range(5):
            data = ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url=f"https://example.com/listing/{i}",
                title=f"Test Listing {i}",
                is_qualified=i % 2 == 0,
            )
            repository.create_listing(data)

        total = repository.count_listings()
        assert total == 5

        qualified = repository.count_listings(qualified_only=True)
        assert qualified == 3


class TestClearListingOptions:
    """Tests for clearing listing options."""

    def test_clear_listing_options_removes_all(
        self, repository: ListingRepository, db_session: Session, sample_listing_data: ListingCreate
    ):
        """Should remove all option associations for a listing."""
        # Create listing
        listing = repository.create_listing(sample_listing_data)

        # Create and associate multiple options
        option1, _ = repository.get_or_create_option("head_up_display")
        option2, _ = repository.get_or_create_option("parking_assistant")
        option3, _ = repository.get_or_create_option("driving_assistant_pro")

        repository.add_option_to_listing(listing.id, option1.id, "HUD")
        repository.add_option_to_listing(listing.id, option2.id, "Park Assist")
        repository.add_option_to_listing(listing.id, option3.id, "DAP")

        # Verify options are associated
        options = repository.get_listing_options(listing.id)
        assert len(options) == 3

        # Clear options
        deleted_count = repository.clear_listing_options(listing.id)
        assert deleted_count == 3

        # Verify options are cleared
        options = repository.get_listing_options(listing.id)
        assert len(options) == 0

    def test_clear_listing_options_returns_zero_for_no_options(
        self, repository: ListingRepository, sample_listing_data: ListingCreate
    ):
        """Should return 0 when listing has no options."""
        listing = repository.create_listing(sample_listing_data)

        deleted_count = repository.clear_listing_options(listing.id)
        assert deleted_count == 0

    def test_clear_listing_options_does_not_affect_other_listings(
        self, repository: ListingRepository, db_session: Session
    ):
        """Should only clear options for the specified listing."""
        # Create two listings
        listing1 = repository.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com/listing/1",
                title="Listing 1",
            )
        )
        listing2 = repository.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com/listing/2",
                title="Listing 2",
            )
        )

        # Create option and associate with both
        option, _ = repository.get_or_create_option("head_up_display")
        repository.add_option_to_listing(listing1.id, option.id, "HUD")
        repository.add_option_to_listing(listing2.id, option.id, "HUD")

        # Clear options for listing1 only
        repository.clear_listing_options(listing1.id)

        # Verify listing1 has no options but listing2 still does
        assert len(repository.get_listing_options(listing1.id)) == 0
        assert len(repository.get_listing_options(listing2.id)) == 1


class TestGetOrCreateOption:
    """Tests for get_or_create_option."""

    def test_get_or_create_option_creates_new(self, repository: ListingRepository):
        """Should create new option when it doesn't exist."""
        option, created = repository.get_or_create_option(
            canonical_name="head_up_display",
            display_name="Head-Up Display",
            category="comfort",
        )

        assert created is True
        assert option.id is not None
        assert option.canonical_name == "head_up_display"
        assert option.display_name == "Head-Up Display"
        assert option.category == "comfort"

    def test_get_or_create_option_returns_existing(self, repository: ListingRepository):
        """Should return existing option without creating duplicate."""
        # Create first
        option1, created1 = repository.get_or_create_option("head_up_display")
        assert created1 is True

        # Try to create again
        option2, created2 = repository.get_or_create_option("head_up_display")
        assert created2 is False
        assert option2.id == option1.id

    def test_get_or_create_option_defaults_display_name(self, repository: ListingRepository):
        """Should use canonical_name as display_name if not provided."""
        option, _ = repository.get_or_create_option("head_up_display")

        assert option.display_name == "head_up_display"


class TestListingExistsWithPrice:
    """Tests for listing_exists_with_price method."""

    def test_listing_exists_with_same_price_returns_true(
        self, repository: ListingRepository, sample_listing_data: ListingCreate
    ):
        """Should return True when listing exists with the same price."""
        repository.create_listing(sample_listing_data)

        result = repository.listing_exists_with_price(
            url=sample_listing_data.url,
            price=sample_listing_data.price,
        )

        assert result is True

    def test_listing_exists_with_different_price_returns_false(
        self, repository: ListingRepository, sample_listing_data: ListingCreate
    ):
        """Should return False when listing exists with different price."""
        repository.create_listing(sample_listing_data)

        result = repository.listing_exists_with_price(
            url=sample_listing_data.url,
            price=5000000,  # Different price
        )

        assert result is False

    def test_listing_does_not_exist_returns_false(self, repository: ListingRepository):
        """Should return False when listing URL doesn't exist."""
        result = repository.listing_exists_with_price(
            url="https://nonexistent.com/listing",
            price=5500000,
        )

        assert result is False

    def test_listing_exists_with_none_price_returns_true_if_stored_price_is_none(
        self, repository: ListingRepository
    ):
        """Should return True when both prices are None."""
        data = ListingCreate(
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com/listing-no-price",
            title="Test Listing",
            price=None,
        )
        repository.create_listing(data)

        result = repository.listing_exists_with_price(url=data.url, price=None)

        assert result is True

    def test_listing_exists_with_none_price_returns_false_if_stored_has_price(
        self, repository: ListingRepository, sample_listing_data: ListingCreate
    ):
        """Should return False when stored has price but checking with None."""
        repository.create_listing(sample_listing_data)

        result = repository.listing_exists_with_price(
            url=sample_listing_data.url,
            price=None,
        )

        assert result is False


class TestMatchedOptionsProperty:
    """Tests for the matched_options property on Listing."""

    def test_matched_options_returns_option_names(
        self, repository: ListingRepository, db_session: Session, sample_listing_data: ListingCreate
    ):
        """matched_options property should return list of canonical names."""
        listing = repository.create_listing(sample_listing_data)

        # Create and associate options
        option1, _ = repository.get_or_create_option("head_up_display")
        option2, _ = repository.get_or_create_option("parking_assistant")

        repository.add_option_to_listing(listing.id, option1.id)
        repository.add_option_to_listing(listing.id, option2.id)

        # Refresh to load relationships
        db_session.refresh(listing)

        # Check matched_options property
        assert "head_up_display" in listing.matched_options
        assert "parking_assistant" in listing.matched_options
        assert len(listing.matched_options) == 2

    def test_matched_options_empty_when_no_options(
        self, repository: ListingRepository, sample_listing_data: ListingCreate
    ):
        """matched_options should return empty list when no options."""
        listing = repository.create_listing(sample_listing_data)

        assert listing.matched_options == []
