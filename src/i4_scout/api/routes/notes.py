"""Notes API endpoints."""

from fastapi import APIRouter, HTTPException

from i4_scout.api.dependencies import NoteServiceDep
from i4_scout.api.schemas import (
    NoteCreateRequest,
    NoteListResponse,
    NoteResponse,
)
from i4_scout.services.note_service import ListingNotFoundError, NoteNotFoundError

router = APIRouter()


@router.get("/{listing_id}/notes", response_model=NoteListResponse)
async def list_notes(
    listing_id: int,
    service: NoteServiceDep,
) -> NoteListResponse:
    """Get all notes for a listing.

    Returns notes in reverse chronological order (newest first).

    Args:
        listing_id: The listing ID.

    Returns:
        List of notes for the listing.
    """
    notes = service.get_notes(listing_id)
    return NoteListResponse(
        notes=[
            NoteResponse(
                id=note.id,
                listing_id=note.listing_id,
                content=note.content,
                created_at=note.created_at,
            )
            for note in notes
        ],
        count=len(notes),
    )


@router.post("/{listing_id}/notes", response_model=NoteResponse, status_code=201)
async def create_note(
    listing_id: int,
    request: NoteCreateRequest,
    service: NoteServiceDep,
) -> NoteResponse:
    """Add a note to a listing.

    Args:
        listing_id: The listing ID.
        request: Request body containing the note content.

    Returns:
        The created note.

    Raises:
        HTTPException: 404 if listing not found.
    """
    try:
        note = service.add_note(listing_id, content=request.content)
        return NoteResponse(
            id=note.id,
            listing_id=note.listing_id,
            content=note.content,
            created_at=note.created_at,
        )
    except ListingNotFoundError:
        raise HTTPException(status_code=404, detail=f"Listing {listing_id} not found") from None


@router.delete("/{listing_id}/notes/{note_id}", status_code=204)
async def delete_note(
    listing_id: int,
    note_id: int,
    service: NoteServiceDep,
) -> None:
    """Delete a note.

    Args:
        listing_id: The listing ID (for URL consistency).
        note_id: The note ID to delete.

    Raises:
        HTTPException: 404 if note not found.
    """
    try:
        service.delete_note(note_id)
    except NoteNotFoundError:
        raise HTTPException(status_code=404, detail=f"Note {note_id} not found") from None
