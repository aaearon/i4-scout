"""Tests for lifecycle tracking in scrape service."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from i4_scout.database.repository import ListingRepository
from i4_scout.models.db_models import Listing
from i4_scout.models.pydantic_models import ListingCreate, ListingStatus, OptionsConfig, Source
from i4_scout.services.scrape_service import ScrapeService


class TestLifecycleTracking:
    """Test lifecycle tracking after scrape."""

    @pytest.fixture
    def mock_repo(self) -> MagicMock:
        """Create a mock repository."""
        repo = MagicMock(spec=ListingRepository)
        repo.get_active_listings_by_source.return_value = []
        repo.increment_consecutive_misses.return_value = 0
        repo.reset_consecutive_misses.return_value = 0
        repo.mark_listings_at_delist_threshold.return_value = 0
        return repo

    @pytest.fixture
    def mock_options_config(self) -> OptionsConfig:
        """Create a minimal options config."""
        return OptionsConfig(required=[], nice_to_have=[], dealbreakers=[])

    @pytest.fixture
    def scrape_service(self, mock_repo: MagicMock, mock_options_config: OptionsConfig) -> ScrapeService:
        """Create scrape service with mock repo."""
        mock_session = MagicMock()
        service = ScrapeService(session=mock_session, options_config=mock_options_config)
        # Replace the repo with our mock
        service._repo = mock_repo
        return service

    def test_resets_misses_for_seen_listings(
        self, scrape_service: ScrapeService, mock_repo: MagicMock
    ) -> None:
        """Should reset consecutive_misses for listings seen in scrape."""
        # Existing active listings
        existing = [
            MagicMock(id=1, consecutive_misses=0, spec=Listing),
            MagicMock(id=2, consecutive_misses=0, spec=Listing),
            MagicMock(id=3, consecutive_misses=0, spec=Listing),
        ]
        mock_repo.get_active_listings_by_source.return_value = existing

        # Simulate seen listing IDs from scrape
        seen_ids = [1, 2]

        # Call lifecycle update
        scrape_service._update_lifecycle_after_scrape(
            source=Source.AUTOSCOUT24_DE,
            seen_listing_ids=seen_ids,
        )

        # Should reset misses for seen listings
        mock_repo.reset_consecutive_misses.assert_called_once_with([1, 2])

    def test_increments_misses_for_unseen_listings(
        self, scrape_service: ScrapeService, mock_repo: MagicMock
    ) -> None:
        """Should increment consecutive_misses for listings not seen in scrape."""
        # Existing active listings
        existing = [
            MagicMock(id=1, consecutive_misses=0, spec=Listing),
            MagicMock(id=2, consecutive_misses=0, spec=Listing),
            MagicMock(id=3, consecutive_misses=0, spec=Listing),
        ]
        mock_repo.get_active_listings_by_source.return_value = existing

        # Simulate seen listing IDs from scrape (missing id=3)
        seen_ids = [1, 2]

        # Call lifecycle update
        scrape_service._update_lifecycle_after_scrape(
            source=Source.AUTOSCOUT24_DE,
            seen_listing_ids=seen_ids,
        )

        # Should increment misses for unseen listing
        mock_repo.increment_consecutive_misses.assert_called_once_with([3])

    def test_calls_mark_listings_at_delist_threshold_for_unseen(
        self, scrape_service: ScrapeService, mock_repo: MagicMock
    ) -> None:
        """Should call mark_listings_at_delist_threshold with unseen listing IDs."""
        # Existing active listings
        listing1 = MagicMock(id=1, consecutive_misses=1, spec=Listing)
        listing2 = MagicMock(id=2, consecutive_misses=0, spec=Listing)

        mock_repo.get_active_listings_by_source.return_value = [listing1, listing2]

        # No listings seen - both will have misses incremented
        seen_ids: list[int] = []

        # Call lifecycle update
        scrape_service._update_lifecycle_after_scrape(
            source=Source.AUTOSCOUT24_DE,
            seen_listing_ids=seen_ids,
        )

        # Should call atomic delist method with all unseen listing IDs
        mock_repo.mark_listings_at_delist_threshold.assert_called_once_with([1, 2])

    def test_delist_threshold_only_called_for_unseen(
        self, scrape_service: ScrapeService, mock_repo: MagicMock
    ) -> None:
        """Should only pass unseen listing IDs to delist threshold method."""
        # Existing active listing
        listing = MagicMock(id=1, consecutive_misses=0, spec=Listing)
        mock_repo.get_active_listings_by_source.return_value = [listing]

        # Listing is seen - should not be checked for delisting
        seen_ids = [1]

        # Call lifecycle update
        scrape_service._update_lifecycle_after_scrape(
            source=Source.AUTOSCOUT24_DE,
            seen_listing_ids=seen_ids,
        )

        # Should call with empty list (no unseen listings)
        mock_repo.mark_listings_at_delist_threshold.assert_called_once_with([])

    def test_handles_empty_seen_list(
        self, scrape_service: ScrapeService, mock_repo: MagicMock
    ) -> None:
        """Should handle case when no listings are seen."""
        existing = [MagicMock(id=1, consecutive_misses=0, spec=Listing)]
        mock_repo.get_active_listings_by_source.return_value = existing

        # No listings seen
        seen_ids: list[int] = []

        # Call lifecycle update
        scrape_service._update_lifecycle_after_scrape(
            source=Source.AUTOSCOUT24_DE,
            seen_listing_ids=seen_ids,
        )

        # Should not call reset (no seen listings)
        mock_repo.reset_consecutive_misses.assert_called_once_with([])
        # Should increment for all active listings
        mock_repo.increment_consecutive_misses.assert_called_once_with([1])

    def test_handles_no_active_listings(
        self, scrape_service: ScrapeService, mock_repo: MagicMock
    ) -> None:
        """Should handle case when there are no active listings."""
        mock_repo.get_active_listings_by_source.return_value = []

        # Some new listings seen
        seen_ids = [1, 2, 3]

        # Call lifecycle update
        scrape_service._update_lifecycle_after_scrape(
            source=Source.AUTOSCOUT24_DE,
            seen_listing_ids=seen_ids,
        )

        # Should reset for seen listings (even if new)
        mock_repo.reset_consecutive_misses.assert_called_once_with([1, 2, 3])
        # Should not increment (no unseen)
        mock_repo.increment_consecutive_misses.assert_called_once_with([])
