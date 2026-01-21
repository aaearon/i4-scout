"""Statistics API endpoints."""

from fastapi import APIRouter
from sqlalchemy import func, select

from i4_scout.api.dependencies import DbSession
from i4_scout.api.schemas import StatsResponse
from i4_scout.models.db_models import Listing

router = APIRouter()


@router.get("", response_model=StatsResponse)
async def get_stats(
    session: DbSession,
) -> StatsResponse:
    """Get aggregated statistics about listings.

    Returns total counts, averages, and breakdowns by source.
    """
    # Total listings
    total_stmt = select(func.count(Listing.id))
    total_listings = session.execute(total_stmt).scalar() or 0

    # Qualified listings
    qualified_stmt = select(func.count(Listing.id)).where(Listing.is_qualified.is_(True))
    qualified_listings = session.execute(qualified_stmt).scalar() or 0

    # Listings by source
    source_stmt = select(Listing.source, func.count(Listing.id)).group_by(Listing.source)
    source_results = session.execute(source_stmt).all()
    listings_by_source = {str(row[0].value): row[1] for row in source_results}

    # Average price (only for listings with price)
    avg_price_stmt = select(func.avg(Listing.price)).where(Listing.price.isnot(None))
    avg_price = session.execute(avg_price_stmt).scalar()

    # Average mileage (only for listings with mileage)
    avg_mileage_stmt = select(func.avg(Listing.mileage_km)).where(Listing.mileage_km.isnot(None))
    avg_mileage = session.execute(avg_mileage_stmt).scalar()

    # Average score
    avg_score_stmt = select(func.avg(Listing.match_score))
    avg_score = session.execute(avg_score_stmt).scalar()

    return StatsResponse(
        total_listings=total_listings,
        qualified_listings=qualified_listings,
        listings_by_source=listings_by_source,
        average_price=round(avg_price, 2) if avg_price else None,
        average_mileage=round(avg_mileage, 2) if avg_mileage else None,
        average_score=round(avg_score, 2) if avg_score else None,
    )
