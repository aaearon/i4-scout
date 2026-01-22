"""Service layer for listing operations."""

from typing import Any

from sqlalchemy.orm import Session

from i4_scout.database.repository import ListingRepository
from i4_scout.models.pydantic_models import ListingRead, Source


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
        )

        # Convert ORM objects to Pydantic models
        listing_reads = [self._to_listing_read(listing) for listing in listings]

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
        return self._to_listing_read(listing)

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
        return self._to_listing_read(listing)

    def _to_listing_read(self, listing: Any) -> ListingRead:
        """Convert ORM Listing to ListingRead Pydantic model.

        Args:
            listing: ORM Listing object.

        Returns:
            ListingRead Pydantic model.
        """
        # Compute price change from eagerly-loaded history
        price_change = None
        price_change_count = 0
        if listing.price_history and len(listing.price_history) > 1:
            # Sort by recorded_at to get oldest (original) and newest (current)
            sorted_history = sorted(listing.price_history, key=lambda h: h.recorded_at)
            original_price = sorted_history[0].price
            current_price = sorted_history[-1].price
            price_change = current_price - original_price
            price_change_count = len(listing.price_history) - 1

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
            first_seen_at=listing.first_seen_at,
            last_seen_at=listing.last_seen_at,
            matched_options=listing.matched_options,
            document_count=len(listing.documents) if listing.documents else 0,
            notes_count=len(listing.notes) if listing.notes else 0,
            price_change=price_change,
            price_change_count=price_change_count,
        )
