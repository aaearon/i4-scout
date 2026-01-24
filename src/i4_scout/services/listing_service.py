"""Service layer for listing operations."""

from dataclasses import dataclass
from datetime import timezone
from typing import Any

from sqlalchemy.orm import Session

from i4_scout.database.repository import ListingRepository
from i4_scout.matching.scorer import calculate_score
from i4_scout.models.pydantic_models import (
    ListingRead,
    ListingStatus,
    MatchResult,
    OptionsConfig,
    Source,
)


@dataclass
class RecalculateResult:
    """Result of recalculating scores for all listings."""

    total_processed: int
    score_changed: int
    qualification_changed: int
    changes: list[dict[str, Any]]


class ListingService:
    """Service for listing operations.

    Provides a clean interface for listing CRUD operations,
    returning Pydantic models instead of ORM objects.
    """

    def __init__(self, session: Session) -> None:
        """Initialize with database session.

        Args:
            session: SQLAlchemy session instance.
        """
        self._session = session
        self._repo = ListingRepository(session)

    def get_listings(
        self,
        source: Source | None = None,
        qualified_only: bool = False,
        min_score: float | None = None,
        price_min: int | None = None,
        price_max: int | None = None,
        mileage_min: int | None = None,
        mileage_max: int | None = None,
        year_min: int | None = None,
        year_max: int | None = None,
        country: str | None = None,
        search: str | None = None,
        has_options: list[str] | None = None,
        options_match: str = "all",
        has_issue: bool | None = None,
        has_price_change: bool | None = None,
        recently_updated: bool | None = None,
        status: ListingStatus | None = None,
        sort_by: str | None = None,
        sort_order: str = "desc",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ListingRead], int]:
        """Get paginated listings with filters.

        Args:
            source: Filter by source.
            qualified_only: Only return qualified listings.
            min_score: Minimum match score.
            price_min: Minimum price in EUR.
            price_max: Maximum price in EUR.
            mileage_min: Minimum mileage in km.
            mileage_max: Maximum mileage in km.
            year_min: Minimum model year.
            year_max: Maximum model year.
            country: Country code (D, NL, B, etc.).
            search: Text search in title and description.
            has_options: List of option names to filter by.
            options_match: "all" to require all options, "any" to require any.
            has_issue: Filter by issue status (True, False, or None for all).
            has_price_change: Filter by price change status (True for listings with changes).
            recently_updated: Filter by recent price changes (True for listings with price changes within 24h).
            status: Filter by listing status (ACTIVE, DELISTED, or None for all).
            sort_by: Field to sort by (price, mileage, score, first_seen, last_seen).
            sort_order: Sort direction (asc, desc). Default: desc.
            limit: Maximum results to return.
            offset: Number of results to skip.

        Returns:
            Tuple of (list of ListingRead, total count).
        """
        listings = self._repo.get_listings(
            source=source,
            qualified_only=qualified_only,
            min_score=min_score,
            price_min=price_min,
            price_max=price_max,
            mileage_min=mileage_min,
            mileage_max=mileage_max,
            year_min=year_min,
            year_max=year_max,
            country=country,
            search=search,
            has_options=has_options,
            options_match=options_match,
            has_issue=has_issue,
            has_price_change=has_price_change,
            recently_updated=recently_updated,
            status=status,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset,
        )

        # Get total count (without pagination, but with all filters)
        total = self._repo.count_listings(
            source=source,
            qualified_only=qualified_only,
            min_score=min_score,
            price_min=price_min,
            price_max=price_max,
            mileage_min=mileage_min,
            mileage_max=mileage_max,
            year_min=year_min,
            year_max=year_max,
            country=country,
            search=search,
            has_options=has_options,
            options_match=options_match,
            has_issue=has_issue,
            has_price_change=has_price_change,
            recently_updated=recently_updated,
            status=status,
        )

        # Convert ORM objects to Pydantic models
        listing_reads = [self.to_listing_read(listing) for listing in listings]

        return listing_reads, total

    def get_listing(self, listing_id: int) -> ListingRead | None:
        """Get a single listing by ID.

        Args:
            listing_id: Listing ID.

        Returns:
            ListingRead if found, None otherwise.
        """
        listing = self._repo.get_listing_by_id(listing_id)
        if listing is None:
            return None
        return self.to_listing_read(listing)

    def delete_listing(self, listing_id: int) -> bool:
        """Delete a listing by ID.

        Args:
            listing_id: Listing ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        return self._repo.delete_listing(listing_id)

    def set_issue(self, listing_id: int, has_issue: bool) -> ListingRead | None:
        """Set the issue flag for a listing.

        Args:
            listing_id: Listing ID to update.
            has_issue: New value for has_issue flag.

        Returns:
            Updated ListingRead if found, None otherwise.
        """
        listing = self._repo.toggle_issue(listing_id, has_issue=has_issue)
        if listing is None:
            return None
        return self.to_listing_read(listing)

    def set_status(self, listing_id: int, status: ListingStatus) -> ListingRead | None:
        """Set the status for a listing.

        Args:
            listing_id: Listing ID to update.
            status: New status (ACTIVE or DELISTED).

        Returns:
            Updated ListingRead if found, None otherwise.
        """
        listing = self._repo.update_listing_status(listing_id, status)
        if listing is None:
            return None
        return self.to_listing_read(listing)

    def recalculate_scores(
        self,
        options_config: OptionsConfig,
    ) -> RecalculateResult:
        """Recalculate scores for all listings using current scoring weights.

        This is useful after changing scoring weights to update existing listings
        without re-scraping.

        Args:
            options_config: Configuration for option matching.

        Returns:
            RecalculateResult with counts and changes.
        """
        # Get all listings (no pagination)
        listings = self._repo.get_listings(limit=None)

        total_processed = 0
        score_changed = 0
        qualification_changed = 0
        changes: list[dict[str, Any]] = []

        # Build sets of required and nice_to_have option names for classification
        required_names = {opt.name for opt in options_config.required}
        nice_to_have_names = {opt.name for opt in options_config.nice_to_have}

        for listing in listings:
            old_score = listing.match_score
            old_qualified = listing.is_qualified

            # Get matched options for this listing
            matched_option_names = listing.matched_options

            # Classify matched options into required vs nice_to_have
            matched_required = [
                name for name in matched_option_names if name in required_names
            ]
            matched_nice_to_have = [
                name for name in matched_option_names if name in nice_to_have_names
            ]

            # Build MatchResult
            missing_required = [
                opt.name for opt in options_config.required
                if opt.name not in matched_option_names
            ]

            match_result = MatchResult(
                matched_required=matched_required,
                matched_nice_to_have=matched_nice_to_have,
                missing_required=missing_required,
                has_dealbreaker=False,  # Not rechecking dealbreakers
            )

            # Calculate new score
            scored_result = calculate_score(match_result, options_config)

            # Update listing if score or qualification changed
            score_diff = abs((scored_result.score or 0) - (old_score or 0))
            if score_diff > 0.001 or scored_result.is_qualified != old_qualified:
                self._repo.update_listing(
                    listing.id,
                    match_score=scored_result.score,
                    is_qualified=scored_result.is_qualified,
                )

                if score_diff > 0.001:
                    score_changed += 1

                if scored_result.is_qualified != old_qualified:
                    qualification_changed += 1

                changes.append({
                    "id": listing.id,
                    "title": listing.title[:50] if listing.title else "",
                    "old_score": round(old_score, 2) if old_score else 0,
                    "new_score": round(scored_result.score, 2),
                    "old_qualified": old_qualified,
                    "new_qualified": scored_result.is_qualified,
                })

            total_processed += 1

        return RecalculateResult(
            total_processed=total_processed,
            score_changed=score_changed,
            qualification_changed=qualification_changed,
            changes=changes,
        )

    def to_listing_read(self, listing: Any) -> ListingRead:
        """Convert ORM Listing to ListingRead Pydantic model.

        Args:
            listing: ORM Listing object.

        Returns:
            ListingRead Pydantic model.
        """
        # Compute price change from eagerly-loaded history
        price_change = None
        price_change_count = 0
        last_price_change_at = None
        if listing.price_history and len(listing.price_history) > 1:
            # Sort by recorded_at to get oldest (original) and newest (current)
            sorted_history = sorted(listing.price_history, key=lambda h: h.recorded_at)
            original_price = sorted_history[0].price
            current_price = sorted_history[-1].price
            price_change = current_price - original_price
            price_change_count = len(listing.price_history) - 1
            # The most recent price change is the last entry (after the initial)
            # Make timezone-aware (SQLite stores as naive UTC)
            recorded_at = sorted_history[-1].recorded_at
            last_price_change_at = recorded_at.replace(tzinfo=timezone.utc) if recorded_at else None

        return ListingRead(
            id=listing.id,
            source=listing.source,
            external_id=listing.external_id,
            url=listing.url,
            title=listing.title,
            price=listing.price,
            price_text=listing.price_text,
            mileage_km=listing.mileage_km,
            year=listing.year,
            first_registration=listing.first_registration,
            vin=listing.vin,
            location_city=listing.location_city,
            location_zip=listing.location_zip,
            location_country=listing.location_country,
            dealer_name=listing.dealer_name,
            dealer_type=listing.dealer_type,
            exterior_color=listing.exterior_color,
            interior_color=listing.interior_color,
            interior_material=listing.interior_material,
            description=listing.description,
            raw_options_text=listing.raw_options_text,
            photo_urls=listing.photo_urls or [],
            match_score=listing.match_score,
            is_qualified=listing.is_qualified,
            has_issue=listing.has_issue,
            status=listing.status,
            consecutive_misses=listing.consecutive_misses,
            status_changed_at=listing.status_changed_at,
            first_seen_at=listing.first_seen_at,
            last_seen_at=listing.last_seen_at,
            matched_options=listing.matched_options,
            document_count=len(listing.documents) if listing.documents else 0,
            notes_count=len(listing.notes) if listing.notes else 0,
            price_change=price_change,
            price_change_count=price_change_count,
            last_price_change_at=last_price_change_at,
        )
