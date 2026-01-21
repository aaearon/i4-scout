"""HTMX partial routes for dynamic content updates."""

from fastapi import APIRouter, Query, Request, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select

from i4_scout.api.dependencies import (
    DbSession,
    DocumentServiceDep,
    ListingServiceDep,
    OptionsConfigDep,
    TemplatesDep,
)
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
    min_score: str | None = Query(None),
    price_min: str | None = Query(None),
    price_max: str | None = Query(None),
    mileage_max: str | None = Query(None),
    year_min: str | None = Query(None),
    country: str | None = Query(None),
    search: str | None = Query(None),
    has_option: list[str] | None = Query(None),
    options_match: str = Query("all"),
    sort_by: str | None = Query(None),
    sort_order: str = Query("desc"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Return listings table HTML fragment."""
    # Convert empty strings to None for numeric params (HTML forms send empty strings)
    min_score_val = float(min_score) if min_score else None
    price_min_val = int(price_min) if price_min else None
    price_max_val = int(price_max) if price_max else None
    mileage_max_val = int(mileage_max) if mileage_max else None
    year_min_val = int(year_min) if year_min else None
    source_val = source if source else None
    country_val = country if country else None
    search_val = search if search else None
    sort_by_val = sort_by if sort_by else None

    # Clean options filter (remove empty strings from form submission)
    has_options_val = [o for o in (has_option or []) if o]
    options_match_val = options_match if options_match in ("all", "any") else "all"

    # Convert source string to Source enum if provided
    source_enum = None
    if source_val:
        try:
            source_enum = Source(source_val)
        except ValueError:
            pass

    listings, total = service.get_listings(
        source=source_enum,
        qualified_only=qualified_only,
        min_score=min_score_val,
        price_min=price_min_val,
        price_max=price_max_val,
        mileage_max=mileage_max_val,
        year_min=year_min_val,
        country=country_val,
        search=search_val,
        has_options=has_options_val if has_options_val else None,
        options_match=options_match_val,
        sort_by=sort_by_val,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
    )

    filters = {
        "source": source_val,
        "qualified_only": qualified_only,
        "min_score": min_score_val,
        "price_min": price_min_val,
        "price_max": price_max_val,
        "mileage_max": mileage_max_val,
        "year_min": year_min_val,
        "country": country_val,
        "search": search_val,
        "has_options": has_options_val,
        "options_match": options_match_val,
        "sort_by": sort_by_val,
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
    if listing is None:
        return HTMLResponse(
            content='<div class="empty-state"><p>Listing not found.</p></div>',
            status_code=200,
        )
    return templates.TemplateResponse(
        request=request,
        name="partials/listing_detail_content.html",
        context={"listing": listing},
    )


@router.get("/listing/{listing_id}/options-summary")
async def listing_options_summary_partial(
    request: Request,
    listing_id: int,
    service: ListingServiceDep,
    options_config: OptionsConfigDep,
    templates: TemplatesDep,
):
    """Return options summary HTML fragment for hover preview."""
    listing = service.get_listing(listing_id)
    if listing is None:
        return HTMLResponse(
            content='<div class="options-summary-empty">Not found</div>',
            status_code=200,
        )

    matched_set = set(listing.matched_options)
    options_status = {
        "required": [{"name": o.name, "has": o.name in matched_set} for o in options_config.required],
        "nice_to_have": [{"name": o.name, "has": o.name in matched_set} for o in options_config.nice_to_have],
    }

    return templates.TemplateResponse(
        request=request,
        name="components/options_summary.html",
        context={"options_status": options_status},
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


@router.get("/listing/{listing_id}/document")
async def listing_document_partial(
    request: Request,
    listing_id: int,
    service: DocumentServiceDep,
    templates: TemplatesDep,
):
    """Return document section HTML fragment."""
    document = service.get_document(listing_id)

    return templates.TemplateResponse(
        request=request,
        name="components/document_section.html",
        context={"listing_id": listing_id, "document": document},
    )


@router.post("/listing/{listing_id}/document")
async def upload_document_partial(
    request: Request,
    listing_id: int,
    file: UploadFile,
    service: DocumentServiceDep,
    templates: TemplatesDep,
):
    """Upload document and return updated HTML fragment."""
    from i4_scout.services.document_service import InvalidFileError, ListingNotFoundError

    error_message = None
    enrichment_result = None

    try:
        if not file.filename:
            error_message = "No filename provided"
        else:
            content = await file.read()
            service.upload_document(
                listing_id=listing_id,
                file_content=content,
                original_filename=file.filename,
            )
            enrichment_result = service.process_document(listing_id)
    except ListingNotFoundError as e:
        error_message = str(e)
    except InvalidFileError as e:
        error_message = str(e)
    except Exception as e:
        error_message = f"Upload failed: {e}"

    document = service.get_document(listing_id)

    return templates.TemplateResponse(
        request=request,
        name="components/document_section.html",
        context={
            "listing_id": listing_id,
            "document": document,
            "error_message": error_message,
            "enrichment_result": enrichment_result,
        },
    )


@router.delete("/listing/{listing_id}/document")
async def delete_document_partial(
    request: Request,
    listing_id: int,
    service: DocumentServiceDep,
    templates: TemplatesDep,
):
    """Delete document and return updated HTML fragment."""
    service.delete_document(listing_id)
    document = service.get_document(listing_id)

    return templates.TemplateResponse(
        request=request,
        name="components/document_section.html",
        context={"listing_id": listing_id, "document": document},
    )


@router.post("/listing/{listing_id}/document/reprocess")
async def reprocess_document_partial(
    request: Request,
    listing_id: int,
    service: DocumentServiceDep,
    templates: TemplatesDep,
):
    """Reprocess document and return updated HTML fragment."""
    from i4_scout.services.document_service import DocumentNotFoundError

    error_message = None
    enrichment_result = None

    try:
        enrichment_result = service.process_document(listing_id)
    except DocumentNotFoundError as e:
        error_message = str(e)
    except Exception as e:
        error_message = f"Reprocess failed: {e}"

    document = service.get_document(listing_id)

    return templates.TemplateResponse(
        request=request,
        name="components/document_section.html",
        context={
            "listing_id": listing_id,
            "document": document,
            "error_message": error_message,
            "enrichment_result": enrichment_result,
        },
    )
