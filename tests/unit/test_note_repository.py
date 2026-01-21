"""Unit tests for NoteRepository."""

import time
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from i4_scout.database.repository import ListingRepository, NoteRepository
from i4_scout.models.db_models import Base
from i4_scout.models.pydantic_models import ListingCreate, Source


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
def note_repository(db_session: Session):
    """Create a NoteRepository instance."""
    return NoteRepository(db_session)


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


class TestCreateNote:
    """Tests for creating notes."""

    def test_create_note_success(self, note_repository: NoteRepository, sample_listing):
        """Should create a note for a listing."""
        note = note_repository.create_note(
            listing_id=sample_listing.id,
            content="Called dealer, car is still available."
        )

        assert note is not None
        assert note.id is not None
        assert note.listing_id == sample_listing.id
        assert note.content == "Called dealer, car is still available."
        assert note.created_at is not None

    def test_create_multiple_notes(self, note_repository: NoteRepository, sample_listing):
        """Should allow multiple notes per listing."""
        note1 = note_repository.create_note(sample_listing.id, "First note")
        note2 = note_repository.create_note(sample_listing.id, "Second note")
        note3 = note_repository.create_note(sample_listing.id, "Third note")

        assert note1.id != note2.id != note3.id
        assert note1.listing_id == note2.listing_id == note3.listing_id


class TestGetNotes:
    """Tests for retrieving notes."""

    def test_get_notes_returns_reverse_chronological(
        self, note_repository: NoteRepository, sample_listing
    ):
        """Notes should be returned in reverse chronological order."""
        # Create notes with slight delays to ensure different timestamps
        note1 = note_repository.create_note(sample_listing.id, "First note")
        time.sleep(0.01)  # Small delay to ensure different timestamps
        note2 = note_repository.create_note(sample_listing.id, "Second note")
        time.sleep(0.01)
        note3 = note_repository.create_note(sample_listing.id, "Third note")

        notes = note_repository.get_notes(sample_listing.id)

        assert len(notes) == 3
        # Most recent first
        assert notes[0].id == note3.id
        assert notes[1].id == note2.id
        assert notes[2].id == note1.id

    def test_get_notes_empty(self, note_repository: NoteRepository, sample_listing):
        """Should return empty list when listing has no notes."""
        notes = note_repository.get_notes(sample_listing.id)
        assert notes == []

    def test_get_notes_nonexistent_listing(self, note_repository: NoteRepository):
        """Should return empty list for non-existent listing."""
        notes = note_repository.get_notes(99999)
        assert notes == []


class TestGetNote:
    """Tests for retrieving a single note."""

    def test_get_note_success(self, note_repository: NoteRepository, sample_listing):
        """Should retrieve a note by ID."""
        created = note_repository.create_note(sample_listing.id, "Test note")

        fetched = note_repository.get_note(created.id)

        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.content == "Test note"

    def test_get_note_not_found(self, note_repository: NoteRepository):
        """Should return None for non-existent note."""
        result = note_repository.get_note(99999)
        assert result is None


class TestDeleteNote:
    """Tests for deleting notes."""

    def test_delete_note_success(self, note_repository: NoteRepository, sample_listing):
        """Should delete a note by ID."""
        note = note_repository.create_note(sample_listing.id, "Test note")
        note_id = note.id

        result = note_repository.delete_note(note_id)
        assert result is True

        # Verify deleted
        fetched = note_repository.get_note(note_id)
        assert fetched is None

    def test_delete_note_not_found(self, note_repository: NoteRepository):
        """Should return False when note doesn't exist."""
        result = note_repository.delete_note(99999)
        assert result is False


class TestNotesCascadeDelete:
    """Tests for cascade delete behavior."""

    def test_notes_cascade_delete_with_listing(
        self,
        db_session: Session,
        listing_repository: ListingRepository,
        note_repository: NoteRepository,
    ):
        """Notes should be deleted when listing is deleted."""
        # Create listing with notes
        listing = listing_repository.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com/cascade-test",
                title="Cascade Test",
            )
        )
        note1 = note_repository.create_note(listing.id, "Note 1")
        note2 = note_repository.create_note(listing.id, "Note 2")

        note1_id = note1.id
        note2_id = note2.id

        # Delete the listing
        listing_repository.delete_listing(listing.id)

        # Notes should be cascade deleted
        assert note_repository.get_note(note1_id) is None
        assert note_repository.get_note(note2_id) is None
