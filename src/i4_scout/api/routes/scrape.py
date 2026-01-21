"""Scrape job API endpoints."""

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

from i4_scout.api.dependencies import DbSession, OptionsConfigDep
from i4_scout.api.schemas import ScrapeJobCreate, ScrapeJobListResponse, ScrapeJobResponse
from i4_scout.models.pydantic_models import OptionsConfig, ScrapeJobRead, Source
from i4_scout.services.job_service import JobService

router = APIRouter()


def _job_to_response(job: ScrapeJobRead) -> ScrapeJobResponse:
    """Convert ScrapeJobRead to ScrapeJobResponse."""
    return ScrapeJobResponse(
        id=job.id,
        source=job.source,
        status=job.status.value if hasattr(job.status, "value") else str(job.status),
        max_pages=job.max_pages,
        search_filters=job.search_filters,
        current_page=job.current_page,
        total_found=job.total_found,
        new_listings=job.new_listings,
        updated_listings=job.updated_listings,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        error_message=job.error_message,
    )


@router.post("", status_code=201, response_model=None)
async def create_scrape_job(
    http_request: Request,
    session: DbSession,
    options_config: OptionsConfigDep,
    background_tasks: BackgroundTasks,
    # Form parameters for HTMX requests
    source: str | None = Form(None),
    max_pages: int | None = Form(None),
) -> HTMLResponse | JSONResponse:
    """Create a new scrape job.

    Creates a scrape job and starts background execution.
    Returns immediately with job details - poll the status endpoint
    for progress updates.

    Accepts both form data (HTMX) and JSON body (API clients).
    For HTMX requests (HX-Request header), returns HTML success message
    and triggers jobCreated event to refresh the jobs list.

    Args:
        http_request: HTTP request object.

    Returns:
        Created job details (JSON) or success message (HTML for HTMX).
    """
    # Determine if this is a form submission or JSON request
    is_htmx = http_request.headers.get("HX-Request") == "true"

    if source is not None and max_pages is not None:
        # Form data from HTMX
        try:
            job_source = Source(source)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid source: {source}") from None
        job_max_pages = max_pages
        job_search_filters: dict[str, Any] | None = None
    else:
        # JSON body from API client
        from pydantic import ValidationError
        try:
            body = await http_request.json()
            request = ScrapeJobCreate(**body)
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=e.errors()) from None
        job_source = request.source
        job_max_pages = request.max_pages
        job_search_filters = request.search_filters

    service = JobService(session)

    job = service.create_job(
        source=job_source,
        max_pages=job_max_pages,
        search_filters=job_search_filters,
    )

    # Schedule background scraping
    background_tasks.add_task(
        run_scrape_job,
        job_id=job.id,
        source=job_source,
        max_pages=job_max_pages,
        search_filters=job_search_filters,
        options_config=options_config,
    )

    # Check if this is an HTMX request
    if is_htmx:
        html_content = f"""
        <div class="alert alert-success">
            Scrape job #{job.id} started for {job_source.value}.
            Scraping up to {job_max_pages} pages.
        </div>
        """
        return HTMLResponse(
            content=html_content,
            status_code=201,
            headers={"HX-Trigger": "jobCreated"},
        )

    response = _job_to_response(job)
    return JSONResponse(content=response.model_dump(mode="json"), status_code=201)


@router.get("", response_model=ScrapeJobListResponse)
async def list_scrape_jobs(
    session: DbSession,
    limit: int = Query(20, ge=1, le=100, description="Maximum jobs to return"),
) -> ScrapeJobListResponse:
    """List recent scrape jobs.

    Returns jobs sorted by creation date, newest first.

    Args:
        limit: Maximum number of jobs to return.

    Returns:
        List of scrape jobs.
    """
    service = JobService(session)
    jobs = service.get_recent_jobs(limit=limit)

    return ScrapeJobListResponse(
        jobs=[_job_to_response(job) for job in jobs],
        count=len(jobs),
    )


@router.get("/{job_id}", response_model=ScrapeJobResponse)
async def get_scrape_job(
    job_id: int,
    session: DbSession,
) -> ScrapeJobResponse:
    """Get scrape job status and progress.

    Args:
        job_id: Job ID to retrieve.

    Returns:
        Job details with current progress.

    Raises:
        HTTPException: 404 if job not found.
    """
    service = JobService(session)
    job = service.get_job(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return _job_to_response(job)


async def run_scrape_job(
    job_id: int,
    source: Source,
    max_pages: int,
    search_filters: dict[str, Any] | None,
    options_config: OptionsConfig,
) -> None:
    """Background task to execute a scrape job.

    This function runs in the background after job creation.
    It updates job progress throughout execution.

    Args:
        job_id: Job ID to execute.
        source: Source to scrape.
        max_pages: Maximum pages to scrape.
        search_filters: Optional search filter overrides.
        options_config: Options configuration for matching.
    """
    from i4_scout.config import load_search_filters, merge_search_filters
    from i4_scout.database.engine import get_session_factory
    from i4_scout.models.pydantic_models import ScrapeProgress, ScrapeStatus
    from i4_scout.services.job_service import JobService
    from i4_scout.services.scrape_service import ScrapeService

    session_factory = get_session_factory()
    session = session_factory()

    try:
        job_service = JobService(session)

        # Mark job as running
        job_service.update_status(job_id, status=ScrapeStatus.RUNNING)

        # Build search filters
        base_filters = load_search_filters()
        if search_filters:
            final_filters = merge_search_filters(base_filters, search_filters)
        else:
            final_filters = base_filters

        # Progress callback to update job
        def on_progress(progress: ScrapeProgress) -> None:
            job_service.update_progress(
                job_id,
                current_page=progress.page,
                total_found=progress.listings_found,
                new_listings=progress.new_count,
                updated_listings=progress.updated_count,
            )

        # Run the scrape
        scrape_service = ScrapeService(session, options_config)
        result = await scrape_service.run_scrape(
            source=source,
            max_pages=max_pages,
            search_filters=final_filters,
            headless=True,
            use_cache=True,
            progress_callback=on_progress,
        )

        # Mark job as completed
        job_service.complete_job(
            job_id,
            total_found=result.total_found,
            new_listings=result.new_listings,
            updated_listings=result.updated_listings,
        )

    except Exception as e:
        # Mark job as failed
        try:
            job_service = JobService(session)
            job_service.fail_job(job_id, error_message=str(e))
        except Exception:
            pass  # Best effort

    finally:
        session.close()
