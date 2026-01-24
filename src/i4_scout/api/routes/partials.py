"""HTMX partial routes for dynamic content updates."""

from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Query, Request, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select

from i4_scout.api.dependencies import (
    DbSession,
    DocumentServiceDep,
    ListingServiceDep,
    NoteServiceDep,
    OptionsConfigDep,
    TemplatesDep,
)
from i4_scout.database.repository import ListingRepository
from i4_scout.models.db_models import Listing
from i4_scout.models.pydantic_models import ListingStatus, Source
from i4_scout.services.job_service import JobService

router = APIRouter(prefix="/partials")


@router.get("/stats")
async def stats_partial(
    request: Request,
    session: DbSession,
    templates: TemplatesDep,
) -> HTMLResponse:
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
) -> HTMLResponse:
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
    session: DbSession,
    templates: TemplatesDep,
    source: str | None = Query(None),
    qualified_only: bool = Query(False),
    has_issue: bool | None = Query(None),
    has_price_change: bool | None = Query(None),
    recently_updated: bool | None = Query(None),
    status: str | None = Query(None),
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
    job_id: int | None = Query(None, description="Filter by scrape job ID"),
    job_status: str | None = Query(None, description="Filter by job processing status (new, updated, unchanged)"),
) -> HTMLResponse:
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

    # Convert status string to ListingStatus enum if provided
    status_enum = None
    if status:
        try:
            status_enum = ListingStatus(status)
        except ValueError:
            pass

    # Handle job_id filtering - when job_id is provided, get listings from that job
    if job_id is not None:
        repo = ListingRepository(session)
        job_listings_raw = repo.get_job_listings(job_id, job_status)
        # Convert to ListingRead for consistency with service
        from i4_scout.services.listing_service import ListingService
        listings = [
            ListingService(session)._to_listing_read(listing)
            for listing in job_listings_raw
        ]
        total = len(listings)
        # Apply pagination manually
        listings = listings[offset:offset + limit]
    else:
        listings, total = service.get_listings(
            source=source_enum,
            qualified_only=qualified_only,
            has_issue=has_issue,
            has_price_change=has_price_change,
            recently_updated=recently_updated,
            status=status_enum,
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
        "has_issue": has_issue,
        "has_price_change": has_price_change,
        "recently_updated": recently_updated,
        "status": status,
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
        "job_id": job_id,
        "job_status": job_status,
    }

    # Build the push URL with active filters
    push_url_params = []
    if source_val:
        push_url_params.append(f"source={source_val}")
    if qualified_only:
        push_url_params.append("qualified_only=true")
    if has_issue:
        push_url_params.append("has_issue=true")
    if has_price_change:
        push_url_params.append("has_price_change=true")
    if recently_updated:
        push_url_params.append("recently_updated=true")
    if status:
        push_url_params.append(f"status={status}")
    if min_score_val is not None:
        push_url_params.append(f"min_score={min_score_val}")
    if price_min_val is not None:
        push_url_params.append(f"price_min={price_min_val}")
    if price_max_val is not None:
        push_url_params.append(f"price_max={price_max_val}")
    if mileage_max_val is not None:
        push_url_params.append(f"mileage_max={mileage_max_val}")
    if year_min_val is not None:
        push_url_params.append(f"year_min={year_min_val}")
    if country_val:
        push_url_params.append(f"country={country_val}")
    if search_val:
        push_url_params.append(f"search={quote(search_val)}")
    if has_options_val:
        for opt in has_options_val:
            push_url_params.append(f"has_option={quote(opt)}")
    if options_match_val != "all":
        push_url_params.append(f"options_match={options_match_val}")
    if sort_by_val:
        push_url_params.append(f"sort_by={sort_by_val}")
    if sort_order != "desc":
        push_url_params.append(f"sort_order={sort_order}")
    if offset > 0:
        push_url_params.append(f"offset={offset}")
    if job_id is not None:
        push_url_params.append(f"job_id={job_id}")
    if job_status:
        push_url_params.append(f"job_status={job_status}")

    push_url = "/listings"
    if push_url_params:
        push_url = f"/listings?{'&'.join(push_url_params)}"

    response = templates.TemplateResponse(
        request=request,
        name="partials/listings_table.html",
        context={
            "listings": listings,
            "total": total,
            "count": len(listings),
            "limit": limit,
            "offset": offset,
            "filters": filters,
            "now": datetime.utcnow(),
        },
    )
    response.headers["HX-Push-Url"] = push_url
    return response


@router.get("/listing/{listing_id}")
async def listing_detail_partial(
    request: Request,
    listing_id: int,
    service: ListingServiceDep,
    templates: TemplatesDep,
) -> HTMLResponse:
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


@router.get("/listing/{listing_id}/gallery")
async def listing_gallery_partial(
    request: Request,
    listing_id: int,
    service: ListingServiceDep,
    templates: TemplatesDep,
) -> HTMLResponse:
    """Return photo gallery HTML fragment."""
    listing = service.get_listing(listing_id)
    if listing is None:
        return HTMLResponse(
            content='<div class="empty-state"><p>Listing not found.</p></div>',
            status_code=200,
        )

    photo_urls = listing.photo_urls if listing.photo_urls else []

    return templates.TemplateResponse(
        request=request,
        name="components/photo_gallery.html",
        context={"listing_id": listing_id, "photo_urls": photo_urls},
    )


@router.get("/listing/{listing_id}/options-summary")
async def listing_options_summary_partial(
    request: Request,
    listing_id: int,
    service: ListingServiceDep,
    options_config: OptionsConfigDep,
    templates: TemplatesDep,
) -> HTMLResponse:
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
) -> HTMLResponse:
    """Return price history chart HTML fragment."""
    repo = ListingRepository(session)
    history = repo.get_price_history(listing_id)

    return templates.TemplateResponse(
        request=request,
        name="components/price_chart.html",
        context={"history": history, "enumerate": enumerate},
    )


@router.get("/scrape/active")
async def scrape_active_partial(
    request: Request,
    session: DbSession,
    templates: TemplatesDep,
) -> HTMLResponse:
    """Return active scrape progress banner HTML fragment."""
    from i4_scout.models.pydantic_models import ScrapeStatus

    service = JobService(session)
    # Get more jobs to ensure we don't miss a running one
    jobs = service.get_recent_jobs(limit=10)

    # Find the most recent running job (jobs are sorted newest first)
    # Only show RUNNING jobs, not PENDING (they haven't started yet)
    active_job = None
    for job in jobs:
        if job.status == ScrapeStatus.RUNNING:
            active_job = job
            break

    return templates.TemplateResponse(
        request=request,
        name="components/scrape_progress_banner.html",
        context={"active_job": active_job},
    )


@router.get("/scrape/active-status")
async def scrape_active_status_partial(
    request: Request,
    session: DbSession,
    templates: TemplatesDep,
) -> HTMLResponse:
    """Return detailed active job status HTML fragment for scrape page."""
    from i4_scout.models.pydantic_models import ScrapeStatus

    service = JobService(session)
    jobs = service.get_recent_jobs(limit=10)

    # Find the most recent running job
    active_job = None
    for job in jobs:
        if job.status == ScrapeStatus.RUNNING:
            active_job = job
            break

    return templates.TemplateResponse(
        request=request,
        name="components/active_job_status.html",
        context={"active_job": active_job},
    )


@router.get("/scrape/jobs")
async def scrape_jobs_partial(
    request: Request,
    session: DbSession,
    templates: TemplatesDep,
    limit: int = Query(20, ge=1, le=100),
) -> HTMLResponse:
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
) -> HTMLResponse:
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
) -> HTMLResponse:
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
) -> HTMLResponse:
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
) -> HTMLResponse:
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
) -> HTMLResponse:
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


@router.patch("/listing/{listing_id}/issue")
async def toggle_issue_partial(
    request: Request,
    listing_id: int,
    service: ListingServiceDep,
) -> HTMLResponse:
    """Toggle issue flag and return updated button HTML fragment."""
    # Get the has_issue value from the request
    form_data = await request.form()
    has_issue_str = str(form_data.get("has_issue", "false"))
    has_issue = has_issue_str.lower() == "true"

    listing = service.set_issue(listing_id, has_issue=has_issue)
    if listing is None:
        return HTMLResponse(
            content='<button class="issue-toggle-btn" disabled>Error</button>',
            status_code=200,
        )

    # Return the updated button
    if listing.has_issue:
        return HTMLResponse(
            content=f'''<button
                type="button"
                id="issue-toggle-btn"
                class="issue-toggle-btn has-issue"
                hx-patch="/partials/listing/{listing_id}/issue"
                hx-swap="outerHTML"
                hx-vals='{{"has_issue": false}}'
                title="Clear issue flag"
            >&#x2713; Issue Marked</button>''',
            status_code=200,
        )
    else:
        return HTMLResponse(
            content=f'''<button
                type="button"
                id="issue-toggle-btn"
                class="issue-toggle-btn"
                hx-patch="/partials/listing/{listing_id}/issue"
                hx-swap="outerHTML"
                hx-vals='{{"has_issue": true}}'
                title="Mark as having an issue"
            >&#x26A0; Mark Issue</button>''',
            status_code=200,
        )


@router.get("/listing/{listing_id}/notes")
async def listing_notes_partial(
    request: Request,
    listing_id: int,
    note_service: NoteServiceDep,
    templates: TemplatesDep,
) -> HTMLResponse:
    """Return notes section HTML fragment."""
    notes = note_service.get_notes(listing_id)

    return templates.TemplateResponse(
        request=request,
        name="components/notes_section.html",
        context={"listing_id": listing_id, "notes": notes},
    )


@router.get("/listing/{listing_id}/notes-summary")
async def listing_notes_summary_partial(
    request: Request,
    listing_id: int,
    note_service: NoteServiceDep,
    templates: TemplatesDep,
) -> HTMLResponse:
    """Return notes summary HTML fragment for hover preview."""
    notes = note_service.get_notes(listing_id)

    return templates.TemplateResponse(
        request=request,
        name="components/notes_summary.html",
        context={"notes": notes},
    )


@router.post("/listing/{listing_id}/notes")
async def add_note_partial(
    request: Request,
    listing_id: int,
    note_service: NoteServiceDep,
    templates: TemplatesDep,
) -> HTMLResponse:
    """Add a note and return the new note HTML fragment."""
    from i4_scout.services.note_service import ListingNotFoundError

    form_data = await request.form()
    content = str(form_data.get("content", "")).strip()

    if not content:
        return HTMLResponse(content="", status_code=200)

    try:
        note = note_service.add_note(listing_id, content)
        # Return just the new note card to be prepended
        return HTMLResponse(
            content=f'''<div class="note-card" id="note-{note.id}">
                <div class="note-header">
                    <span class="note-timestamp">{note.created_at.strftime('%Y-%m-%d %H:%M')}</span>
                    <button
                        type="button"
                        class="note-delete-btn"
                        hx-delete="/partials/listing/{listing_id}/notes/{note.id}"
                        hx-target="#note-{note.id}"
                        hx-swap="outerHTML"
                        hx-confirm="Delete this note?"
                        title="Delete note"
                    >&#x2715;</button>
                </div>
                <div class="note-content">{note.content}</div>
            </div>''',
            status_code=200,
        )
    except ListingNotFoundError:
        return HTMLResponse(
            content='<div class="alert alert-error">Listing not found</div>',
            status_code=200,
        )


@router.delete("/listing/{listing_id}/notes/{note_id}")
async def delete_note_partial(
    listing_id: int,
    note_id: int,
    note_service: NoteServiceDep,
) -> HTMLResponse:
    """Delete a note and return empty content (note removed from DOM)."""
    from i4_scout.services.note_service import NoteNotFoundError

    try:
        note_service.delete_note(note_id)
        return HTMLResponse(content="", status_code=200)
    except NoteNotFoundError:
        return HTMLResponse(content="", status_code=200)


# ========== DASHBOARD WIDGET PARTIALS ==========


@router.get("/market-velocity")
async def market_velocity_partial(
    request: Request,
    session: DbSession,
    templates: TemplatesDep,
    days: int = Query(7, ge=1, le=90),
) -> HTMLResponse:
    """Return market velocity widget HTML fragment."""
    repo = ListingRepository(session)
    velocity = repo.get_market_velocity(days=days)

    return templates.TemplateResponse(
        request=request,
        name="components/market_velocity.html",
        context={"velocity": velocity, "days": days},
    )


@router.get("/price-drops")
async def price_drops_partial(
    request: Request,
    session: DbSession,
    templates: TemplatesDep,
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(5, ge=1, le=20),
) -> HTMLResponse:
    """Return price drops widget HTML fragment."""
    repo = ListingRepository(session)
    price_drops = repo.get_listings_with_price_drops(days=days, limit=limit)

    # Format for template: list of dicts with listing, original_price, current_price, drop_amount
    formatted = [
        {
            "listing": listing,
            "original_price": original,
            "current_price": current,
            "drop_amount": original - current,
        }
        for listing, original, current in price_drops
    ]

    return templates.TemplateResponse(
        request=request,
        name="components/price_drops.html",
        context={"price_drops": formatted, "days": days},
    )


@router.get("/near-miss")
async def near_miss_partial(
    request: Request,
    session: DbSession,
    options_config: OptionsConfigDep,
    templates: TemplatesDep,
    threshold: float = Query(70.0, ge=0, le=100),
    limit: int = Query(5, ge=1, le=20),
) -> HTMLResponse:
    """Return near-miss listings widget HTML fragment."""
    repo = ListingRepository(session)
    near_misses = repo.get_near_miss_listings(threshold=threshold, limit=limit)

    # Compute missing required options for each listing
    required_names = {opt.name for opt in options_config.required}
    formatted = []
    for listing, matched_options in near_misses:
        matched_set = set(matched_options)
        missing = [name for name in required_names if name not in matched_set]
        formatted.append({
            "listing": listing,
            "matched_options": matched_options,
            "missing_required": missing,
        })

    return templates.TemplateResponse(
        request=request,
        name="components/near_miss.html",
        context={"near_misses": formatted, "threshold": threshold},
    )


@router.get("/feature-rarity")
async def feature_rarity_partial(
    request: Request,
    session: DbSession,
    options_config: OptionsConfigDep,
    templates: TemplatesDep,
    limit: int = Query(10, ge=1, le=50),
) -> HTMLResponse:
    """Return feature rarity widget HTML fragment."""
    repo = ListingRepository(session)
    all_frequencies = repo.get_option_frequency()

    # Filter to only include options from config (required + nice-to-have)
    required_names = {opt.name for opt in options_config.required}
    nice_to_have_names = {opt.name for opt in options_config.nice_to_have}
    config_options = required_names | nice_to_have_names

    # Separate into rarest and most common
    frequencies = [f for f in all_frequencies if f["name"] in config_options]

    # Sort by percentage ascending for rarity view
    rarest = sorted(frequencies, key=lambda x: x["percentage"])[:limit]
    most_common = sorted(frequencies, key=lambda x: x["percentage"], reverse=True)[:limit]

    return templates.TemplateResponse(
        request=request,
        name="components/feature_rarity.html",
        context={
            "rarest": rarest,
            "most_common": most_common,
            "required_names": required_names,
            "nice_to_have_names": nice_to_have_names,
        },
    )


@router.get("/favorites")
async def favorites_partial(
    request: Request,
    service: ListingServiceDep,
    templates: TemplatesDep,
    ids: str = Query("", description="Comma-separated listing IDs"),
) -> HTMLResponse:
    """Return favorites widget HTML fragment.

    This endpoint is called from JS with localStorage favorite IDs.
    """
    if not ids:
        return templates.TemplateResponse(
            request=request,
            name="components/favorites.html",
            context={"listings": [], "empty": True},
        )

    # Parse IDs
    try:
        listing_ids = [int(x.strip()) for x in ids.split(",") if x.strip()]
    except ValueError:
        listing_ids = []

    if not listing_ids:
        return templates.TemplateResponse(
            request=request,
            name="components/favorites.html",
            context={"listings": [], "empty": True},
        )

    # Fetch listings
    listings = []
    for lid in listing_ids[:10]:  # Limit to 10 favorites
        listing = service.get_listing(lid)
        if listing:
            listings.append(listing)

    return templates.TemplateResponse(
        request=request,
        name="components/favorites.html",
        context={"listings": listings, "empty": len(listings) == 0},
    )
