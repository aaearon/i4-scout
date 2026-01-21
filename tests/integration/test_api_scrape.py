"""Integration tests for scrape API endpoints."""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from i4_scout.api.dependencies import get_db
from i4_scout.api.main import create_app
from i4_scout.models.db_models import Base, ScrapeJob
from i4_scout.models.pydantic_models import ScrapeStatus, Source


# Mock the background task to prevent actual scraping
@pytest.fixture(autouse=True)
def mock_background_scrape():
    """Mock the background scrape task to prevent Playwright from launching."""
    with patch("i4_scout.api.routes.scrape.run_scrape_job") as mock:
        # Make it a coroutine that does nothing
        async def noop(*args, **kwargs):
            pass
        mock.side_effect = noop
        yield mock


@pytest.fixture
def test_engine(tmp_path: Path):
    """Create a test database engine."""
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session_factory(test_engine):
    """Create a session factory for the test database."""
    return sessionmaker(bind=test_engine)


@pytest.fixture
def client(session_factory):
    """Create a test client with overridden database dependency."""
    app = create_app()

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


@pytest.fixture
def sample_jobs(session_factory) -> list[int]:
    """Create sample scrape jobs and return their IDs."""
    session = session_factory()

    jobs = [
        ScrapeJob(
            source=Source.AUTOSCOUT24_DE.value,
            status=ScrapeStatus.COMPLETED,
            max_pages=10,
            total_found=45,
            new_listings=12,
            updated_listings=8,
            completed_at=datetime.utcnow(),
        ),
        ScrapeJob(
            source=Source.AUTOSCOUT24_NL.value,
            status=ScrapeStatus.RUNNING,
            max_pages=5,
            current_page=3,
            total_found=20,
            new_listings=5,
        ),
        ScrapeJob(
            source=Source.AUTOSCOUT24_DE.value,
            status=ScrapeStatus.FAILED,
            max_pages=10,
            error_message="Connection timeout",
            completed_at=datetime.utcnow(),
        ),
    ]

    ids = []
    for job in jobs:
        session.add(job)
        session.commit()
        session.refresh(job)
        ids.append(job.id)

    session.close()
    return ids


class TestCreateScrapeJob:
    """Tests for POST /api/scrape/jobs endpoint."""

    def test_create_job_basic(self, client: TestClient) -> None:
        """Can create a basic scrape job."""
        response = client.post(
            "/api/scrape/jobs",
            json={
                "source": "autoscout24_de",
                "max_pages": 5,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["source"] == "autoscout24_de"
        assert data["max_pages"] == 5
        assert data["status"] == "pending"
        assert data["id"] is not None

    def test_create_job_with_filters(self, client: TestClient) -> None:
        """Can create a job with search filters."""
        response = client.post(
            "/api/scrape/jobs",
            json={
                "source": "autoscout24_nl",
                "max_pages": 10,
                "search_filters": {
                    "price_max_eur": 50000,
                    "year_min": 2023,
                },
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["source"] == "autoscout24_nl"
        assert data["search_filters"]["price_max_eur"] == 50000
        assert data["search_filters"]["year_min"] == 2023

    def test_create_job_default_max_pages(self, client: TestClient) -> None:
        """Uses default max_pages if not specified."""
        response = client.post(
            "/api/scrape/jobs",
            json={"source": "autoscout24_de"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["max_pages"] == 50  # Default value

    def test_create_job_invalid_source(self, client: TestClient) -> None:
        """Returns 422 for invalid source."""
        response = client.post(
            "/api/scrape/jobs",
            json={"source": "invalid_source"},
        )
        assert response.status_code == 422


class TestListScrapeJobs:
    """Tests for GET /api/scrape/jobs endpoint."""

    def test_list_empty(self, client: TestClient) -> None:
        """Returns empty list when no jobs exist."""
        response = client.get("/api/scrape/jobs")
        assert response.status_code == 200
        data = response.json()
        assert data["jobs"] == []
        assert data["count"] == 0

    def test_list_all(self, client: TestClient, sample_jobs: list[int]) -> None:
        """Returns all jobs, newest first."""
        response = client.get("/api/scrape/jobs")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 3
        assert len(data["jobs"]) == 3

    def test_list_with_limit(self, client: TestClient, sample_jobs: list[int]) -> None:
        """Respects limit parameter."""
        response = client.get("/api/scrape/jobs?limit=2")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2


class TestGetScrapeJob:
    """Tests for GET /api/scrape/jobs/{id} endpoint."""

    def test_get_existing(self, client: TestClient, sample_jobs: list[int]) -> None:
        """Returns job details for existing ID."""
        job_id = sample_jobs[0]
        response = client.get(f"/api/scrape/jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == job_id
        assert data["source"] == "autoscout24_de"
        assert data["status"] == "completed"
        assert data["total_found"] == 45

    def test_get_running_job(self, client: TestClient, sample_jobs: list[int]) -> None:
        """Returns running job with progress."""
        job_id = sample_jobs[1]  # Running job
        response = client.get(f"/api/scrape/jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert data["current_page"] == 3
        assert data["total_found"] == 20

    def test_get_failed_job(self, client: TestClient, sample_jobs: list[int]) -> None:
        """Returns failed job with error message."""
        job_id = sample_jobs[2]  # Failed job
        response = client.get(f"/api/scrape/jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error_message"] == "Connection timeout"

    def test_get_not_found(self, client: TestClient) -> None:
        """Returns 404 for non-existent job."""
        response = client.get("/api/scrape/jobs/9999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestBackgroundScraping:
    """Tests for background scraping behavior."""

    def test_job_starts_background_task(self, client: TestClient) -> None:
        """Creating a job triggers background scraping."""
        # We can verify the job was created with pending status
        # Actual background execution is tested separately
        response = client.post(
            "/api/scrape/jobs",
            json={"source": "autoscout24_de", "max_pages": 1},
        )
        assert response.status_code == 201
        data = response.json()
        job_id = data["id"]

        # Job should be created with pending status initially
        # (background task updates it to running)
        assert data["status"] == "pending"

        # Verify we can fetch the job
        response = client.get(f"/api/scrape/jobs/{job_id}")
        assert response.status_code == 200
