"""Web routes for HTML pages."""

from fastapi import APIRouter, Query, Request

from i4_scout.api.dependencies import TemplatesDep

router = APIRouter()


@router.get("/")
async def dashboard(
    request: Request,
    templates: TemplatesDep,
):
    """Render the dashboard page."""
    return templates.TemplateResponse(
        request=request,
        name="pages/dashboard.html",
    )


@router.get("/listings")
async def listings_page(
    request: Request,
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
):
    """Render the listings page."""
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
        name="pages/listings.html",
        context={"filters": filters},
    )


@router.get("/listings/{listing_id}")
async def listing_detail_page(
    request: Request,
    listing_id: int,
    templates: TemplatesDep,
):
    """Render the listing detail page."""
    return templates.TemplateResponse(
        request=request,
        name="pages/listing_detail.html",
        context={"listing_id": listing_id},
    )


@router.get("/scrape")
async def scrape_page(
    request: Request,
    templates: TemplatesDep,
):
    """Render the scrape control page."""
    return templates.TemplateResponse(
        request=request,
        name="pages/scrape.html",
    )
