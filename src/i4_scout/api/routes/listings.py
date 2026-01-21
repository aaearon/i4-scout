"""Listings API endpoints."""

from fastapi import APIRouter, HTTPException, Query

from i4_scout.api.dependencies import DbSession, ListingServiceDep
from i4_scout.api.schemas import (
    DeleteResponse,
    PaginatedListings,
    PriceHistoryEntry,
    PriceHistoryResponse,
)
from i4_scout.database.repository import ListingRepository
from i4_scout.models.pydantic_models import ListingRead, Source

router = APIRouter()


@router.get("", response_model=PaginatedListings)
async def list_listings(
    service: ListingServiceDep,
    source: Source | None = Query(None, description="Filter by source"),
    qualified_only: bool = Query(False, description="Only qualified listings"),
    min_score: float | None = Query(None, ge=0, le=100, description="Minimum match score"),
    limit: int = Query(20, ge=1, le=100, description="Results per page"),
    offset: int = Query(0, ge=0, description="Results to skip"),
) -> PaginatedListings:
    """Get paginated listings with optional filters.

    Returns a paginated list of car listings with support for filtering
    by source, qualification status, and minimum match score.
    """
    listings, total = service.get_listings(
        source=source,
        qualified_only=qualified_only,
        min_score=min_score,
        limit=limit,
        offset=offset,
    )

    return PaginatedListings(
        listings=listings,
        count=len(listings),
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{listing_id}", response_model=ListingRead)
async def get_listing(
    listing_id: int,
    service: ListingServiceDep,
) -> ListingRead:
    """Get a single listing by ID.

    Args:
        listing_id: The listing ID to retrieve.

    Returns:
        The listing details.

    Raises:
        HTTPException: 404 if listing not found.
    """
    listing = service.get_listing(listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail=f"Listing {listing_id} not found")
    return listing


@router.get("/{listing_id}/price-history", response_model=PriceHistoryResponse)
async def get_price_history(
    listing_id: int,
    session: DbSession,
) -> PriceHistoryResponse:
    """Get price history for a listing.

    Args:
        listing_id: The listing ID.

    Returns:
        Price history with current price and historical entries.

    Raises:
        HTTPException: 404 if listing not found.
    """
    repo = ListingRepository(session)

    # Verify listing exists
    listing = repo.get_listing_by_id(listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail=f"Listing {listing_id} not found")

    # Get price history
    history = repo.get_price_history(listing_id)

    return PriceHistoryResponse(
        listing_id=listing_id,
        current_price=listing.price,
        history=[
            PriceHistoryEntry(price=entry.price, recorded_at=entry.recorded_at)
            for entry in history
        ],
    )


@router.delete("/{listing_id}", response_model=DeleteResponse)
async def delete_listing(
    listing_id: int,
    service: ListingServiceDep,
) -> DeleteResponse:
    """Delete a listing by ID.

    Args:
        listing_id: The listing ID to delete.

    Returns:
        Success status and message.

    Raises:
        HTTPException: 404 if listing not found.
    """
    success = service.delete_listing(listing_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Listing {listing_id} not found")

    return DeleteResponse(success=True, message=f"Listing {listing_id} deleted")
