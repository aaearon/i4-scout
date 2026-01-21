"""Tests for ScrapeJob model and repository methods."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from i4_scout.database.repository import ScrapeJobRepository
from i4_scout.models.db_models import Base, ScrapeJob
from i4_scout.models.pydantic_models import ScrapeStatus, Source


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
def repo(session: Session) -> ScrapeJobRepository:
    """Create a ScrapeJobRepository instance."""
    return ScrapeJobRepository(session)


class TestScrapeJobModel:
    """Tests for ScrapeJob ORM model."""

    def test_create_scrape_job(self, session: Session) -> None:
        """Can create a ScrapeJob with default values."""
        job = ScrapeJob(
            source=Source.AUTOSCOUT24_DE.value,
            max_pages=10,
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        assert job.id is not None
        assert job.source == Source.AUTOSCOUT24_DE.value
        assert job.status == ScrapeStatus.PENDING
        assert job.max_pages == 10
        assert job.current_page == 0
        assert job.total_found == 0
        assert job.new_listings == 0
        assert job.updated_listings == 0
        assert job.created_at is not None
        assert job.started_at is None
        assert job.completed_at is None
        assert job.error_message is None

    def test_scrape_job_with_search_filters(self, session: Session) -> None:
        """Can store search filters as JSON."""
        filters = {"price_max": 50000, "mileage_max": 40000}
        job = ScrapeJob(
            source=Source.AUTOSCOUT24_NL.value,
            max_pages=5,
            search_filters_json=json.dumps(filters),
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        assert job.search_filters_json is not None
        parsed = json.loads(job.search_filters_json)
        assert parsed["price_max"] == 50000
        assert parsed["mileage_max"] == 40000

    def test_scrape_job_status_transitions(self, session: Session) -> None:
        """Job status can be updated through lifecycle."""
        job = ScrapeJob(
            source=Source.AUTOSCOUT24_DE.value,
            max_pages=10,
        )
        session.add(job)
        session.commit()

        # Start job
        job.status = ScrapeStatus.RUNNING
        job.started_at = datetime.utcnow()
        session.commit()
        session.refresh(job)
        assert job.status == ScrapeStatus.RUNNING
        assert job.started_at is not None

        # Complete job
        job.status = ScrapeStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        job.total_found = 45
        job.new_listings = 12
        job.updated_listings = 8
        session.commit()
        session.refresh(job)

        assert job.status == ScrapeStatus.COMPLETED
        assert job.completed_at is not None
        assert job.total_found == 45
        assert job.new_listings == 12
        assert job.updated_listings == 8


class TestScrapeJobRepository:
    """Tests for ScrapeJobRepository."""

    def test_create_job(self, repo: ScrapeJobRepository) -> None:
        """Can create a job through repository."""
        job = repo.create_job(
            source=Source.AUTOSCOUT24_DE,
            max_pages=10,
        )

        assert job.id is not None
        assert job.source == Source.AUTOSCOUT24_DE.value
        assert job.status == ScrapeStatus.PENDING

    def test_create_job_with_search_filters(self, repo: ScrapeJobRepository) -> None:
        """Can create a job with search filters."""
        filters = {"price_max": 45000, "year_min": 2023}
        job = repo.create_job(
            source=Source.AUTOSCOUT24_NL,
            max_pages=5,
            search_filters=filters,
        )

        assert job.search_filters_json is not None
        parsed = json.loads(job.search_filters_json)
        assert parsed == filters

    def test_get_job(self, repo: ScrapeJobRepository) -> None:
        """Can retrieve a job by ID."""
        created = repo.create_job(source=Source.AUTOSCOUT24_DE, max_pages=10)
        fetched = repo.get_job(created.id)

        assert fetched is not None
        assert fetched.id == created.id

    def test_get_job_not_found(self, repo: ScrapeJobRepository) -> None:
        """Returns None for non-existent job."""
        result = repo.get_job(9999)
        assert result is None

    def test_get_recent_jobs(self, repo: ScrapeJobRepository) -> None:
        """Can list recent jobs."""
        # Create multiple jobs
        repo.create_job(source=Source.AUTOSCOUT24_DE, max_pages=5)
        repo.create_job(source=Source.AUTOSCOUT24_NL, max_pages=10)
        repo.create_job(source=Source.AUTOSCOUT24_DE, max_pages=15)

        jobs = repo.get_recent_jobs(limit=10)
        assert len(jobs) == 3

    def test_get_recent_jobs_limit(self, repo: ScrapeJobRepository) -> None:
        """Respects limit parameter."""
        for i in range(5):
            repo.create_job(source=Source.AUTOSCOUT24_DE, max_pages=i + 1)

        jobs = repo.get_recent_jobs(limit=3)
        assert len(jobs) == 3

    def test_update_status(self, repo: ScrapeJobRepository) -> None:
        """Can update job status."""
        job = repo.create_job(source=Source.AUTOSCOUT24_DE, max_pages=10)

        updated = repo.update_status(job.id, ScrapeStatus.RUNNING)
        assert updated is not None
        assert updated.status == ScrapeStatus.RUNNING
        assert updated.started_at is not None

    def test_update_progress(self, repo: ScrapeJobRepository) -> None:
        """Can update job progress."""
        job = repo.create_job(source=Source.AUTOSCOUT24_DE, max_pages=10)

        updated = repo.update_progress(
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

    def test_complete_job(self, repo: ScrapeJobRepository) -> None:
        """Can mark job as completed."""
        job = repo.create_job(source=Source.AUTOSCOUT24_DE, max_pages=10)
        repo.update_status(job.id, ScrapeStatus.RUNNING)

        completed = repo.complete_job(
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

    def test_fail_job(self, repo: ScrapeJobRepository) -> None:
        """Can mark job as failed with error message."""
        job = repo.create_job(source=Source.AUTOSCOUT24_DE, max_pages=10)
        repo.update_status(job.id, ScrapeStatus.RUNNING)

        failed = repo.fail_job(job.id, error_message="Connection timeout")

        assert failed is not None
        assert failed.status == ScrapeStatus.FAILED
        assert failed.completed_at is not None
        assert failed.error_message == "Connection timeout"

    def test_cleanup_old_jobs(self, repo: ScrapeJobRepository, session: Session) -> None:
        """Can delete jobs older than specified days."""
        # Create an old job by manually setting created_at
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
        recent_job = repo.create_job(source=Source.AUTOSCOUT24_NL, max_pages=5)

        # Cleanup jobs older than 7 days
        deleted_count = repo.cleanup_old_jobs(days=7)

        assert deleted_count == 1
        assert repo.get_job(old_job_id) is None
        assert repo.get_job(recent_job.id) is not None
