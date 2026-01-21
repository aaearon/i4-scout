"""API routes for document operations."""

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse

from i4_scout.api.dependencies import DocumentServiceDep
from i4_scout.models.pydantic_models import DocumentRead, EnrichmentResult
from i4_scout.services.document_service import (
    DocumentNotFoundError,
    InvalidFileError,
    ListingNotFoundError,
)

router = APIRouter()


@router.post(
    "/{listing_id}/document",
    response_model=EnrichmentResult,
    summary="Upload and process PDF document",
    responses={
        404: {"description": "Listing not found"},
        400: {"description": "Invalid file"},
    },
)
async def upload_document(
    listing_id: int,
    file: UploadFile,
    service: DocumentServiceDep,
) -> EnrichmentResult:
    """Upload a PDF document for a listing and process it.

    Extracts options from the PDF and updates the listing's match score.
    Replaces any existing document for the listing.
    """
    try:
        # Validate filename
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        # Read file content
        content = await file.read()

        # Upload document
        service.upload_document(
            listing_id=listing_id,
            file_content=content,
            original_filename=file.filename,
        )

        # Process document
        result = service.process_document(listing_id)
        return result

    except ListingNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except InvalidFileError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get(
    "/{listing_id}/document",
    response_model=DocumentRead,
    summary="Get document metadata",
    responses={404: {"description": "Document not found"}},
)
async def get_document(
    listing_id: int,
    service: DocumentServiceDep,
) -> DocumentRead:
    """Get metadata for a listing's document."""
    document = service.get_document(listing_id)
    if document is None:
        raise HTTPException(
            status_code=404,
            detail=f"No document found for listing {listing_id}",
        )
    return document


@router.get(
    "/{listing_id}/document/download",
    summary="Download PDF document",
    responses={404: {"description": "Document not found"}},
)
async def download_document(
    listing_id: int,
    service: DocumentServiceDep,
) -> FileResponse:
    """Download the PDF document for a listing."""
    document = service.get_document(listing_id)
    if document is None:
        raise HTTPException(
            status_code=404,
            detail=f"No document found for listing {listing_id}",
        )

    file_path = service.get_document_path(listing_id)
    if file_path is None or not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Document file not found on disk",
        )

    return FileResponse(
        path=file_path,
        filename=document.original_filename,
        media_type="application/pdf",
    )


@router.delete(
    "/{listing_id}/document",
    summary="Delete document",
    responses={404: {"description": "Document not found"}},
)
async def delete_document(
    listing_id: int,
    service: DocumentServiceDep,
) -> dict[str, str]:
    """Delete the document for a listing.

    Also removes PDF-sourced options and recalculates the listing's score.
    """
    deleted = service.delete_document(listing_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"No document found for listing {listing_id}",
        )
    return {"status": "deleted"}


@router.post(
    "/{listing_id}/document/reprocess",
    response_model=EnrichmentResult,
    summary="Reprocess document",
    responses={404: {"description": "Document not found"}},
)
async def reprocess_document(
    listing_id: int,
    service: DocumentServiceDep,
) -> EnrichmentResult:
    """Re-extract options from the document.

    Useful if options configuration has changed.
    """
    try:
        result = service.process_document(listing_id)
        return result
    except DocumentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ListingNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
