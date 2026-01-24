"""Tests for listing lifecycle status enum and models."""

from datetime import datetime, timedelta, timezone

import pytest

from i4_scout.models.pydantic_models import ListingCreate, ListingRead, ListingStatus, Source


class TestListingStatusEnum:
    """Test ListingStatus enum."""

    def test_status_values(self) -> None:
        """Should have active and delisted status values."""
        assert ListingStatus.ACTIVE == "active"
        assert ListingStatus.DELISTED == "delisted"

    def test_status_is_string_enum(self) -> None:
        """Should be a string enum for JSON serialization."""
        assert isinstance(ListingStatus.ACTIVE, str)
        assert ListingStatus.ACTIVE.value == "active"


class TestListingCreateStatus:
    """Test status fields on ListingCreate."""

    def test_default_status_is_active(self) -> None:
        """New listings should default to active status."""
        listing = ListingCreate(
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com/listing/1",
            title="Test BMW i4",
        )
        assert listing.status == ListingStatus.ACTIVE

    def test_default_consecutive_misses_is_zero(self) -> None:
        """New listings should have zero consecutive misses."""
        listing = ListingCreate(
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com/listing/1",
            title="Test BMW i4",
        )
        assert listing.consecutive_misses == 0

    def test_can_set_status_explicitly(self) -> None:
        """Should be able to set status to delisted."""
        listing = ListingCreate(
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com/listing/1",
            title="Test BMW i4",
            status=ListingStatus.DELISTED,
        )
        assert listing.status == ListingStatus.DELISTED

    def test_can_set_consecutive_misses(self) -> None:
        """Should be able to set consecutive misses count."""
        listing = ListingCreate(
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com/listing/1",
            title="Test BMW i4",
            consecutive_misses=2,
        )
        assert listing.consecutive_misses == 2


class TestListingReadStatus:
    """Test status fields on ListingRead."""

    def test_has_status_fields(self) -> None:
        """ListingRead should have status, status_changed_at, and days_on_market."""
        now = datetime.now(timezone.utc)
        listing = ListingRead(
            id=1,
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com/listing/1",
            title="Test BMW i4",
            first_seen_at=now - timedelta(days=5),
            last_seen_at=now,
            status=ListingStatus.ACTIVE,
            status_changed_at=None,
            consecutive_misses=0,
        )
        assert listing.status == ListingStatus.ACTIVE
        assert listing.status_changed_at is None
        assert listing.consecutive_misses == 0

    def test_days_on_market_for_active_listing(self) -> None:
        """Active listing days_on_market calculated from first_seen_at to now."""
        now = datetime.now(timezone.utc)
        listing = ListingRead(
            id=1,
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com/listing/1",
            title="Test BMW i4",
            first_seen_at=now - timedelta(days=10),
            last_seen_at=now,
            status=ListingStatus.ACTIVE,
            status_changed_at=None,
            consecutive_misses=0,
        )
        # Days on market should be approximately 10
        assert listing.days_on_market >= 9
        assert listing.days_on_market <= 11

    def test_days_on_market_for_delisted_listing(self) -> None:
        """Delisted listing days_on_market calculated from first_seen_at to status_changed_at."""
        now = datetime.now(timezone.utc)
        listing = ListingRead(
            id=1,
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com/listing/1",
            title="Test BMW i4",
            first_seen_at=now - timedelta(days=30),
            last_seen_at=now - timedelta(days=5),
            status=ListingStatus.DELISTED,
            status_changed_at=now - timedelta(days=5),
            consecutive_misses=2,
        )
        # Days on market should be approximately 25 (from first_seen_at to status_changed_at)
        assert listing.days_on_market >= 24
        assert listing.days_on_market <= 26

    def test_status_with_from_attributes(self) -> None:
        """Should work with from_attributes for ORM mapping."""
        # This is tested implicitly by the model_config setting
        assert ListingRead.model_config.get("from_attributes") is True
