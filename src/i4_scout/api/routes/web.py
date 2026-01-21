"""Web routes for HTML pages."""

from fastapi import APIRouter, Request

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
):
    """Render the listings page."""
    return templates.TemplateResponse(
        request=request,
        name="pages/listings.html",
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
