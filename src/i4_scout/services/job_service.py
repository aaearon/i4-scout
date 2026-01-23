"""Service layer for scrape job management."""

import json
from typing import Any

from sqlalchemy.orm import Session

from i4_scout.database.repository import ScrapeJobRepository
from i4_scout.models.db_models import ScrapeJob
from i4_scout.models.pydantic_models import ScrapeJobRead, ScrapeStatus, Source


class JobService:
    """Service for scrape job operations.

    Provides a clean interface for job management, wrapping the repository
    and converting between ORM models and Pydantic models.
    """

    def __init__(self, session: Session) -> None:
        """Initialize with database session.

        Args:
            session: SQLAlchemy session instance.
        """
        self._session = session
        self._repo = ScrapeJobRepository(session)

    def _to_pydantic(self, job: ScrapeJob) -> ScrapeJobRead:
        """Convert ORM model to Pydantic model.

        Args:
            job: ScrapeJob ORM instance.

        Returns:
            ScrapeJobRead Pydantic model.
        """
        search_filters = None
        if job.search_filters_json:
            search_filters = json.loads(job.search_filters_json)

        # Handle status which may be enum or string
        status = job.status
        if isinstance(status, str):
            status = ScrapeStatus(status)

        return ScrapeJobRead(
            id=job.id,
            source=job.source,
            status=status,
            max_pages=job.max_pages,
            search_filters=search_filters,
            current_page=job.current_page,
            total_found=job.total_found,
            new_listings=job.new_listings,
            updated_listings=job.updated_listings,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            error_message=job.error_message,
        )

    def create_job(
        self,
        source: Source,
        max_pages: int = 50,
        search_filters: dict[str, Any] | None = None,
    ) -> ScrapeJobRead:
        """Create a new scrape job.

        Args:
            source: Source to scrape.
            max_pages: Maximum number of pages to scrape.
            search_filters: Optional search filter parameters.

        Returns:
            Created job as ScrapeJobRead.
        """
        job = self._repo.create_job(
            source=source,
            max_pages=max_pages,
            search_filters=search_filters,
        )
        return self._to_pydantic(job)

    def get_job(self, job_id: int) -> ScrapeJobRead | None:
        """Get a job by ID.

        Args:
            job_id: Job ID.

        Returns:
            ScrapeJobRead if found, None otherwise.
        """
        job = self._repo.get_job(job_id)
        if job is None:
            return None
        return self._to_pydantic(job)

    def get_recent_jobs(self, limit: int = 20) -> list[ScrapeJobRead]:
        """Get recent jobs, newest first.

        Args:
            limit: Maximum number of jobs to return.

        Returns:
            List of ScrapeJobRead objects.
        """
        jobs = self._repo.get_recent_jobs(limit=limit)
        return [self._to_pydantic(job) for job in jobs]

    def update_status(self, job_id: int, status: ScrapeStatus) -> ScrapeJobRead | None:
        """Update job status.

        Args:
            job_id: Job ID.
            status: New status.

        Returns:
            Updated ScrapeJobRead if found, None otherwise.
        """
        job = self._repo.update_status(job_id, status)
        if job is None:
            return None
        return self._to_pydantic(job)

    def update_progress(
        self,
        job_id: int,
        current_page: int | None = None,
        total_found: int | None = None,
        new_listings: int | None = None,
        updated_listings: int | None = None,
    ) -> ScrapeJobRead | None:
        """Update job progress.

        Args:
            job_id: Job ID.
            current_page: Current page being processed.
            total_found: Total listings found so far.
            new_listings: New listings created.
            updated_listings: Existing listings updated.

        Returns:
            Updated ScrapeJobRead if found, None otherwise.
        """
        job = self._repo.update_progress(
            job_id,
            current_page=current_page,
            total_found=total_found,
            new_listings=new_listings,
            updated_listings=updated_listings,
        )
        if job is None:
            return None
        return self._to_pydantic(job)

    def complete_job(
        self,
        job_id: int,
        total_found: int = 0,
        new_listings: int = 0,
        updated_listings: int = 0,
    ) -> ScrapeJobRead | None:
        """Mark job as completed.

        Args:
            job_id: Job ID.
            total_found: Total listings found.
            new_listings: New listings created.
            updated_listings: Existing listings updated.

        Returns:
            Updated ScrapeJobRead if found, None otherwise.
        """
        job = self._repo.complete_job(
            job_id,
            total_found=total_found,
            new_listings=new_listings,
            updated_listings=updated_listings,
        )
        if job is None:
            return None
        return self._to_pydantic(job)

    def fail_job(self, job_id: int, error_message: str) -> ScrapeJobRead | None:
        """Mark job as failed.

        Args:
            job_id: Job ID.
            error_message: Error description.

        Returns:
            Updated ScrapeJobRead if found, None otherwise.
        """
        job = self._repo.fail_job(job_id, error_message=error_message)
        if job is None:
            return None
        return self._to_pydantic(job)

    def cancel_job(self, job_id: int) -> ScrapeJobRead | None:
        """Mark job as cancelled.

        Args:
            job_id: Job ID.

        Returns:
            Updated ScrapeJobRead if found, None otherwise.
        """
        job = self._repo.cancel_job(job_id)
        if job is None:
            return None
        return self._to_pydantic(job)

    def cleanup_old_jobs(self, days: int = 30) -> int:
        """Delete completed/failed jobs older than specified days.

        Args:
            days: Delete jobs older than this many days.

        Returns:
            Number of deleted jobs.
        """
        return self._repo.cleanup_old_jobs(days=days)
