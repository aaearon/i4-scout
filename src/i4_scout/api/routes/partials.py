"""HTMX partial routes for dynamic content updates."""

from fastapi import APIRouter, Request

from i4_scout.api.dependencies import TemplatesDep

router = APIRouter(prefix="/partials")


@router.get("/stats")
async def stats_partial(
    request: Request,
    templates: TemplatesDep,
):
    """Return stats cards HTML fragment."""
    return templates.TemplateResponse(
        request=request,
        name="components/stats_cards.html",
    )


@router.get("/recent-qualified")
async def recent_qualified_partial(
    request: Request,
    templates: TemplatesDep,
):
    """Return recent qualified listings HTML fragment."""
    return templates.TemplateResponse(
        request=request,
        name="components/listing_card.html",
    )
