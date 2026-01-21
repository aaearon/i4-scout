"""Integration tests for notes API endpoints."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from i4_scout.api.dependencies import get_db
from i4_scout.api.main import create_app
from i4_scout.database.repository import ListingRepository
from i4_scout.models.db_models import Base
from i4_scout.models.pydantic_models import ListingCreate, Source


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
def sample_listing(session_factory):
    """Create a sample listing in the test database."""
    session = session_factory()
    repo = ListingRepository(session)
    listing = repo.create_listing(
        ListingCreate(
            source=Source.AUTOSCOUT24_DE,
            url="https://example.com/test-listing",
            title="Test BMW i4",
            price=5500000,
        )
    )
    session.close()
    return listing


@pytest.fixture
def client(session_factory, sample_listing):
    """Create test client with dependency overrides."""
    app = create_app()

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    return TestClient(app)


class TestNotesEndpoints:
    """Tests for notes API endpoints."""

    def test_list_notes_empty(self, client, sample_listing):
        """Should return empty list for listing with no notes."""
        response = client.get(f"/api/listings/{sample_listing.id}/notes")
        assert response.status_code == 200
        data = response.json()
        assert data["notes"] == []
        assert data["count"] == 0

    def test_add_note_success(self, client, sample_listing):
        """Should add a note to a listing."""
        response = client.post(
            f"/api/listings/{sample_listing.id}/notes",
            json={"content": "Test note content"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["listing_id"] == sample_listing.id
        assert data["content"] == "Test note content"
        assert "id" in data
        assert "created_at" in data

    def test_add_note_listing_not_found(self, client):
        """Should return 404 for non-existent listing."""
        response = client.post(
            "/api/listings/99999/notes",
            json={"content": "Test note"},
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_add_note_empty_content(self, client, sample_listing):
        """Should return 422 for empty content."""
        response = client.post(
            f"/api/listings/{sample_listing.id}/notes",
            json={"content": ""},
        )
        assert response.status_code == 422

    def test_list_notes_returns_notes(self, client, sample_listing):
        """Should return list of notes."""
        # Add some notes
        client.post(
            f"/api/listings/{sample_listing.id}/notes",
            json={"content": "First note"},
        )
        client.post(
            f"/api/listings/{sample_listing.id}/notes",
            json={"content": "Second note"},
        )

        response = client.get(f"/api/listings/{sample_listing.id}/notes")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        # Most recent first
        assert data["notes"][0]["content"] == "Second note"
        assert data["notes"][1]["content"] == "First note"

    def test_delete_note_success(self, client, sample_listing):
        """Should delete a note."""
        # Add a note
        add_response = client.post(
            f"/api/listings/{sample_listing.id}/notes",
            json={"content": "Note to delete"},
        )
        note_id = add_response.json()["id"]

        # Delete the note
        response = client.delete(f"/api/listings/{sample_listing.id}/notes/{note_id}")
        assert response.status_code == 204

        # Verify deleted
        list_response = client.get(f"/api/listings/{sample_listing.id}/notes")
        assert list_response.json()["count"] == 0

    def test_delete_note_not_found(self, client, sample_listing):
        """Should return 404 for non-existent note."""
        response = client.delete(f"/api/listings/{sample_listing.id}/notes/99999")
        assert response.status_code == 404
