"""HTMX partial routes for dynamic content updates."""

from fastapi import APIRouter, Query, Request
from sqlalchemy import func, select

from i4_scout.api.dependencies import DbSession, ListingServiceDep, TemplatesDep
from i4_scout.database.repository import ListingRepository
from i4_scout.models.db_models import Listing
from i4_scout.models.pydantic_models import Source
from i4_scout.services.job_service import JobService

router = APIRouter(prefix="/partials")


@router.get("/stats")
async def stats_partial(
    request: Request,
    session: DbSession,
    templates: TemplatesDep,
):
    """Return stats cards HTML fragment."""
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

    # Average price
    avg_price_stmt = select(func.avg(Listing.price)).where(Listing.price.isnot(None))
    avg_price = session.execute(avg_price_stmt).scalar()

    # Average mileage
    avg_mileage_stmt = select(func.avg(Listing.mileage_km)).where(Listing.mileage_km.isnot(None))
    avg_mileage = session.execute(avg_mileage_stmt).scalar()

    # Average score
    avg_score_stmt = select(func.avg(Listing.match_score))
    avg_score = session.execute(avg_score_stmt).scalar()

    stats = {
        "total_listings": total_listings,
        "qualified_listings": qualified_listings,
        "listings_by_source": listings_by_source,
        "average_price": round(avg_price, 2) if avg_price else None,
        "average_mileage": round(avg_mileage, 2) if avg_mileage else None,
        "average_score": round(avg_score, 2) if avg_score else None,
    }

    return templates.TemplateResponse(
        request=request,
        name="components/stats_cards.html",
        context={"stats": stats},
    )


@router.get("/recent-qualified")
async def recent_qualified_partial(
    request: Request,
    service: ListingServiceDep,
    templates: TemplatesDep,
):
    """Return recent qualified listings HTML fragment."""
    listings, _ = service.get_listings(
        qualified_only=True,
        sort_by="first_seen",
        sort_order="desc",
        limit=5,
    )

    return templates.TemplateResponse(
        request=request,
        name="partials/recent_qualified.html",
        context={"listings": listings},
    )


@router.get("/listings")
async def listings_partial(
    request: Request,
    service: ListingServiceDep,
    templates: TemplatesDep,
    source: str | None = Query(None),
    qualified_only: bool = Query(False),
    min_score: float | None = Query(None),
    price_min: int | None = Query(None),
    price_max: int | None = Query(None),
    mileage_max: int | None = Query(None),
    year_min: int | None = Query(None),
    country: str | None = Query(None),
    search: str | None = Query(None),
    sort_by: str | None = Query(None),
    sort_order: str = Query("desc"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Return listings table HTML fragment."""
    # Convert source string to Source enum if provided
    source_enum = None
    if source:
        try:
            source_enum = Source(source)
        except ValueError:
            pass

    listings, total = service.get_listings(
        source=source_enum,
        qualified_only=qualified_only,
        min_score=min_score,
        price_min=price_min,
        price_max=price_max,
        mileage_max=mileage_max,
        year_min=year_min,
        country=country,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
    )

    filters = {
        "source": source,
        "qualified_only": qualified_only,
        "min_score": min_score,
        "price_min": price_min,
        "price_max": price_max,
        "mileage_max": mileage_max,
        "year_min": year_min,
        "country": country,
        "search": search,
        "sort_by": sort_by,
        "sort_order": sort_order,
    }

    return templates.TemplateResponse(
        request=request,
        name="partials/listings_table.html",
        context={
            "listings": listings,
            "total": total,
            "count": len(listings),
            "limit": limit,
            "offset": offset,
            "filters": filters,
        },
    )


@router.get("/listing/{listing_id}")
async def listing_detail_partial(
    request: Request,
    listing_id: int,
    service: ListingServiceDep,
    templates: TemplatesDep,
):
    """Return listing detail HTML fragment (for modal loading)."""
    listing = service.get_listing(listing_id)
    return templates.TemplateResponse(
        request=request,
        name="partials/listing_detail_content.html",
        context={"listing": listing},
    )


@router.get("/listing/{listing_id}/price-chart")
async def listing_price_chart_partial(
    request: Request,
    listing_id: int,
    session: DbSession,
    templates: TemplatesDep,
):
    """Return price history chart HTML fragment."""
    repo = ListingRepository(session)
    history = repo.get_price_history(listing_id)

    return templates.TemplateResponse(
        request=request,
        name="components/price_chart.html",
        context={"history": history, "enumerate": enumerate},
    )


@router.get("/scrape/jobs")
async def scrape_jobs_partial(
    request: Request,
    session: DbSession,
    templates: TemplatesDep,
    limit: int = Query(20, ge=1, le=100),
):
    """Return scrape jobs list HTML fragment."""
    service = JobService(session)
    jobs = service.get_recent_jobs(limit=limit)

    return templates.TemplateResponse(
        request=request,
        name="partials/scrape_jobs_list.html",
        context={"jobs": jobs},
    )


@router.get("/scrape/job/{job_id}")
async def scrape_job_partial(
    request: Request,
    job_id: int,
    session: DbSession,
    templates: TemplatesDep,
):
    """Return single scrape job row HTML fragment."""
    service = JobService(session)
    job = service.get_job(job_id)

    if job is None:
        return templates.TemplateResponse(
            request=request,
            name="components/scrape_job_row.html",
            context={"job": None},
        )

    return templates.TemplateResponse(
        request=request,
        name="components/scrape_job_row.html",
        context={"job": job},
    )
