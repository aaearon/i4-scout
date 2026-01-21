"""Service layer for note operations."""

from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from i4_scout.database.repository import ListingRepository, NoteRepository
from i4_scout.models.pydantic_models import ListingNoteRead

if TYPE_CHECKING:
    from i4_scout.models.db_models import ListingNote


class ListingNotFoundError(Exception):
    """Raised when a listing is not found."""

    pass


class NoteNotFoundError(Exception):
    """Raised when a note is not found."""

    pass


class NoteService:
    """Service for note operations.

    Provides a clean interface for note CRUD operations,
    returning Pydantic models instead of ORM objects.
    """

    def __init__(self, session: Session) -> None:
        """Initialize with database session.

        Args:
            session: SQLAlchemy session instance.
        """
        self._session = session
        self._listing_repo = ListingRepository(session)
        self._note_repo = NoteRepository(session)

    def add_note(self, listing_id: int, content: str) -> ListingNoteRead:
        """Add a note to a listing.

        Args:
            listing_id: Listing ID.
            content: Note content.

        Returns:
            Created ListingNoteRead.

        Raises:
            ListingNotFoundError: If listing doesn't exist.
        """
        listing = self._listing_repo.get_listing_by_id(listing_id)
        if listing is None:
            raise ListingNotFoundError(f"Listing {listing_id} not found")

        note = self._note_repo.create_note(listing_id=listing_id, content=content)
        return self._to_note_read(note)

    def get_notes(self, listing_id: int) -> list[ListingNoteRead]:
        """Get all notes for a listing.

        Args:
            listing_id: Listing ID.

        Returns:
            List of ListingNoteRead, newest first.
        """
        notes = self._note_repo.get_notes(listing_id)
        return [self._to_note_read(note) for note in notes]

    def delete_note(self, note_id: int) -> bool:
        """Delete a note.

        Args:
            note_id: Note ID.

        Returns:
            True if deleted.

        Raises:
            NoteNotFoundError: If note doesn't exist.
        """
        note = self._note_repo.get_note(note_id)
        if note is None:
            raise NoteNotFoundError(f"Note {note_id} not found")

        return self._note_repo.delete_note(note_id)

    def _to_note_read(self, note: "ListingNote") -> ListingNoteRead:
        """Convert ORM ListingNote to ListingNoteRead Pydantic model.

        Args:
            note: ORM ListingNote object.

        Returns:
            ListingNoteRead Pydantic model.
        """
        return ListingNoteRead(
            id=note.id,
            listing_id=note.listing_id,
            content=note.content,
            created_at=note.created_at,
        )
