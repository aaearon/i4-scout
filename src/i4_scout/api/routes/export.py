"""Export API endpoints."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Query
from fastapi.responses import Response

from i4_scout.api.dependencies import DbSession
from i4_scout.database.repository import ListingRepository
from i4_scout.export.csv_exporter import export_to_csv
from i4_scout.export.json_exporter import export_to_json
from i4_scout.models.pydantic_models import Source

router = APIRouter()


@router.get("/listings")
async def export_listings(
    session: DbSession,
    format: Literal["csv", "json"] = Query("csv", description="Export format"),
    source: Source | None = Query(None, description="Filter by source"),
    qualified_only: bool = Query(False, description="Only qualified listings"),
    min_score: float | None = Query(None, ge=0, le=100, description="Minimum match score"),
    price_min: int | None = Query(None, ge=0, description="Minimum price in EUR"),
    price_max: int | None = Query(None, ge=0, description="Maximum price in EUR"),
    mileage_min: int | None = Query(None, ge=0, description="Minimum mileage in km"),
    mileage_max: int | None = Query(None, ge=0, description="Maximum mileage in km"),
    year_min: int | None = Query(None, ge=2015, le=2030, description="Minimum model year"),
    year_max: int | None = Query(None, ge=2015, le=2030, description="Maximum model year"),
    country: str | None = Query(None, max_length=5, description="Country code (D, NL, B, etc.)"),
    search: str | None = Query(
        None, min_length=2, max_length=100, description="Search in title and description"
    ),
    has_issue: bool | None = Query(None, description="Filter by issue status"),
) -> Response:
    """Export listings to CSV or JSON format.

    Returns a file download with all matching listings.
    Supports the same filters as the listings endpoint.
    """
    repo = ListingRepository(session)

    # Get listings with filters (no pagination for export)
    listings = repo.get_listings(
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
        has_issue=has_issue,
    )

    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if format == "csv":
        content = export_to_csv(listings)
        return Response(
            content=content,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="listings_{timestamp}.csv"'
            },
        )
    else:
        # JSON format
        content = export_to_json(listings)
        return Response(
            content=content,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="listings_{timestamp}.json"'
            },
        )
