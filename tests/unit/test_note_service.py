"""Unit tests for NoteService."""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from i4_scout.database.repository import ListingRepository
from i4_scout.models.db_models import Base
from i4_scout.models.pydantic_models import ListingCreate, Source
from i4_scout.services.note_service import (
    ListingNotFoundError,
    NoteNotFoundError,
    NoteService,
)


@pytest.fixture
def db_session():
    """Create an in-memory database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


@pytest.fixture
def listing_repository(db_session: Session):
    """Create a ListingRepository instance."""
    return ListingRepository(db_session)


@pytest.fixture
def note_service(db_session: Session):
    """Create a NoteService instance."""
    return NoteService(db_session)


@pytest.fixture
def sample_listing(listing_repository: ListingRepository):
    """Create a sample listing for testing."""
    data = ListingCreate(
        source=Source.AUTOSCOUT24_DE,
        url="https://www.autoscout24.de/angebote/test-listing-12345",
        title="BMW i4 eDrive40 2023",
        price=5500000,
        mileage_km=15000,
        year=2023,
        first_registration=date(2023, 3, 1),
    )
    return listing_repository.create_listing(data)


class TestAddNote:
    """Tests for adding notes."""

    def test_add_note_returns_note_read(self, note_service: NoteService, sample_listing):
        """Should return ListingNoteRead on success."""
        note = note_service.add_note(sample_listing.id, "Test note content")

        assert note.id is not None
        assert note.listing_id == sample_listing.id
        assert note.content == "Test note content"
        assert note.created_at is not None

    def test_add_note_listing_not_found(self, note_service: NoteService):
        """Should raise ListingNotFoundError for invalid listing ID."""
        with pytest.raises(ListingNotFoundError) as exc_info:
            note_service.add_note(99999, "Test note")

        assert "99999" in str(exc_info.value)


class TestGetNotes:
    """Tests for getting notes."""

    def test_get_notes_returns_list(self, note_service: NoteService, sample_listing):
        """Should return list of ListingNoteRead."""
        note_service.add_note(sample_listing.id, "First note")
        note_service.add_note(sample_listing.id, "Second note")

        notes = note_service.get_notes(sample_listing.id)

        assert len(notes) == 2
        # Most recent first
        assert notes[0].content == "Second note"
        assert notes[1].content == "First note"

    def test_get_notes_empty(self, note_service: NoteService, sample_listing):
        """Should return empty list when no notes exist."""
        notes = note_service.get_notes(sample_listing.id)
        assert notes == []


class TestDeleteNote:
    """Tests for deleting notes."""

    def test_delete_note_success(self, note_service: NoteService, sample_listing):
        """Should delete a note successfully."""
        note = note_service.add_note(sample_listing.id, "Test note")

        result = note_service.delete_note(note.id)
        assert result is True

        # Verify deleted
        notes = note_service.get_notes(sample_listing.id)
        assert len(notes) == 0

    def test_delete_note_not_found(self, note_service: NoteService):
        """Should raise NoteNotFoundError for invalid note ID."""
        with pytest.raises(NoteNotFoundError) as exc_info:
            note_service.delete_note(99999)

        assert "99999" in str(exc_info.value)
