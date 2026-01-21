"""Tests for JobService."""

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from i4_scout.models.db_models import Base, ScrapeJob
from i4_scout.models.pydantic_models import ScrapeStatus, Source
from i4_scout.services.job_service import JobService


@pytest.fixture
def test_engine(tmp_path: Path):
    """Create a test database engine."""
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(test_engine):
    """Create a test database session."""
    session_local = sessionmaker(bind=test_engine)
    session = session_local()
    yield session
    session.close()


@pytest.fixture
def service(session: Session) -> JobService:
    """Create a JobService instance."""
    return JobService(session)


class TestJobServiceCreate:
    """Tests for job creation."""

    def test_create_job_basic(self, service: JobService) -> None:
        """Can create a basic scrape job."""
        job = service.create_job(
            source=Source.AUTOSCOUT24_DE,
            max_pages=10,
        )

        assert job.id is not None
        assert job.source == Source.AUTOSCOUT24_DE.value
        assert job.status == ScrapeStatus.PENDING
        assert job.max_pages == 10
        assert job.current_page == 0
        assert job.total_found == 0
        assert job.new_listings == 0
        assert job.updated_listings == 0

    def test_create_job_with_search_filters(self, service: JobService) -> None:
        """Can create a job with search filters."""
        filters = {"price_max_eur": 45000, "year_min": 2023}
        job = service.create_job(
            source=Source.AUTOSCOUT24_NL,
            max_pages=5,
            search_filters=filters,
        )

        assert job.search_filters is not None
        assert job.search_filters["price_max_eur"] == 45000
        assert job.search_filters["year_min"] == 2023


class TestJobServiceGet:
    """Tests for job retrieval."""

    def test_get_job_by_id(self, service: JobService) -> None:
        """Can retrieve a job by ID."""
        created = service.create_job(
            source=Source.AUTOSCOUT24_DE,
            max_pages=10,
        )
        fetched = service.get_job(created.id)

        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.source == Source.AUTOSCOUT24_DE.value

    def test_get_job_not_found(self, service: JobService) -> None:
        """Returns None for non-existent job."""
        result = service.get_job(9999)
        assert result is None

    def test_get_recent_jobs(self, service: JobService) -> None:
        """Can list recent jobs."""
        service.create_job(source=Source.AUTOSCOUT24_DE, max_pages=5)
        service.create_job(source=Source.AUTOSCOUT24_NL, max_pages=10)
        service.create_job(source=Source.AUTOSCOUT24_DE, max_pages=15)

        jobs = service.get_recent_jobs(limit=10)
        assert len(jobs) == 3
        # Most recent first
        assert jobs[0].max_pages == 15

    def test_get_recent_jobs_respects_limit(self, service: JobService) -> None:
        """Respects limit parameter."""
        for i in range(5):
            service.create_job(source=Source.AUTOSCOUT24_DE, max_pages=i + 1)

        jobs = service.get_recent_jobs(limit=3)
        assert len(jobs) == 3


class TestJobServiceStatusUpdates:
    """Tests for job status management."""

    def test_update_status_to_running(self, service: JobService) -> None:
        """Can start a job."""
        job = service.create_job(source=Source.AUTOSCOUT24_DE, max_pages=10)

        updated = service.update_status(job.id, ScrapeStatus.RUNNING)

        assert updated is not None
        assert updated.status == ScrapeStatus.RUNNING
        assert updated.started_at is not None

    def test_update_status_not_found(self, service: JobService) -> None:
        """Returns None for non-existent job."""
        result = service.update_status(9999, ScrapeStatus.RUNNING)
        assert result is None

    def test_update_progress(self, service: JobService) -> None:
        """Can update job progress."""
        job = service.create_job(source=Source.AUTOSCOUT24_DE, max_pages=10)
        service.update_status(job.id, ScrapeStatus.RUNNING)

        updated = service.update_progress(
            job.id,
            current_page=3,
            total_found=45,
            new_listings=12,
            updated_listings=8,
        )

        assert updated is not None
        assert updated.current_page == 3
        assert updated.total_found == 45
        assert updated.new_listings == 12
        assert updated.updated_listings == 8

    def test_update_progress_partial(self, service: JobService) -> None:
        """Can update only some progress fields."""
        job = service.create_job(source=Source.AUTOSCOUT24_DE, max_pages=10)
        service.update_status(job.id, ScrapeStatus.RUNNING)

        updated = service.update_progress(job.id, current_page=2)

        assert updated is not None
        assert updated.current_page == 2
        assert updated.total_found == 0  # Unchanged


class TestJobServiceCompletion:
    """Tests for job completion."""

    def test_complete_job(self, service: JobService) -> None:
        """Can mark job as completed."""
        job = service.create_job(source=Source.AUTOSCOUT24_DE, max_pages=10)
        service.update_status(job.id, ScrapeStatus.RUNNING)

        completed = service.complete_job(
            job.id,
            total_found=50,
            new_listings=20,
            updated_listings=10,
        )

        assert completed is not None
        assert completed.status == ScrapeStatus.COMPLETED
        assert completed.completed_at is not None
        assert completed.total_found == 50
        assert completed.new_listings == 20
        assert completed.updated_listings == 10

    def test_complete_job_not_found(self, service: JobService) -> None:
        """Returns None for non-existent job."""
        result = service.complete_job(9999)
        assert result is None

    def test_fail_job(self, service: JobService) -> None:
        """Can mark job as failed."""
        job = service.create_job(source=Source.AUTOSCOUT24_DE, max_pages=10)
        service.update_status(job.id, ScrapeStatus.RUNNING)

        failed = service.fail_job(job.id, error_message="Connection timeout")

        assert failed is not None
        assert failed.status == ScrapeStatus.FAILED
        assert failed.completed_at is not None
        assert failed.error_message == "Connection timeout"

    def test_fail_job_not_found(self, service: JobService) -> None:
        """Returns None for non-existent job."""
        result = service.fail_job(9999, error_message="Error")
        assert result is None


class TestJobServiceCleanup:
    """Tests for job cleanup."""

    def test_cleanup_old_jobs(self, service: JobService, session: Session) -> None:
        """Can delete old completed jobs."""
        # Create an old completed job
        old_job = ScrapeJob(
            source=Source.AUTOSCOUT24_DE.value,
            max_pages=10,
            status=ScrapeStatus.COMPLETED,
            created_at=datetime.utcnow() - timedelta(days=10),
            completed_at=datetime.utcnow() - timedelta(days=10),
        )
        session.add(old_job)
        session.commit()
        old_job_id = old_job.id

        # Create a recent job
        recent_job = service.create_job(source=Source.AUTOSCOUT24_NL, max_pages=5)

        # Cleanup jobs older than 7 days
        deleted_count = service.cleanup_old_jobs(days=7)

        assert deleted_count == 1
        assert service.get_job(old_job_id) is None
        assert service.get_job(recent_job.id) is not None

    def test_cleanup_keeps_pending_jobs(self, service: JobService, session: Session) -> None:
        """Does not delete old pending jobs."""
        # Create an old pending job
        old_pending = ScrapeJob(
            source=Source.AUTOSCOUT24_DE.value,
            max_pages=10,
            status=ScrapeStatus.PENDING,
            created_at=datetime.utcnow() - timedelta(days=10),
        )
        session.add(old_pending)
        session.commit()
        old_job_id = old_pending.id

        # Cleanup should not delete pending jobs
        deleted_count = service.cleanup_old_jobs(days=7)

        assert deleted_count == 0
        assert service.get_job(old_job_id) is not None
