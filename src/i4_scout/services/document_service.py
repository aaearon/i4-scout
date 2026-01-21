"""Service layer for document operations."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO

from sqlalchemy.orm import Session

from i4_scout.database.repository import DocumentRepository, ListingRepository
from i4_scout.enrichment.enricher import ListingEnricher
from i4_scout.enrichment.pdf_extractor import PDFExtractor
from i4_scout.models.pydantic_models import DocumentRead, EnrichmentResult, OptionsConfig

# Maximum file size: 10MB
MAX_FILE_SIZE = 10 * 1024 * 1024

# Default document storage directory
DEFAULT_DOCUMENTS_DIR = Path(__file__).parent.parent.parent.parent / "data" / "documents"


class DocumentServiceError(Exception):
    """Base exception for document service errors."""

    pass


class InvalidFileError(DocumentServiceError):
    """Raised when file validation fails."""

    pass


class ListingNotFoundError(DocumentServiceError):
    """Raised when listing doesn't exist."""

    pass


class DocumentNotFoundError(DocumentServiceError):
    """Raised when document doesn't exist."""

    pass


class DocumentService:
    """Service for document upload and processing operations."""

    # PDF magic bytes
    PDF_MAGIC = b"%PDF"

    def __init__(
        self,
        session: Session,
        options_config: OptionsConfig,
        documents_dir: Path | None = None,
    ) -> None:
        """Initialize with database session and config.

        Args:
            session: SQLAlchemy session instance.
            options_config: Configuration for option matching.
            documents_dir: Directory for document storage. Defaults to data/documents/.
        """
        self._session = session
        self._options_config = options_config
        self._documents_dir = documents_dir or DEFAULT_DOCUMENTS_DIR
        self._doc_repo = DocumentRepository(session)
        self._listing_repo = ListingRepository(session)
        self._enricher = ListingEnricher(options_config)

    def _ensure_documents_dir(self) -> None:
        """Ensure the documents directory exists."""
        self._documents_dir.mkdir(parents=True, exist_ok=True)

    def _validate_pdf(self, file_content: bytes, original_filename: str) -> None:
        """Validate that file is a valid PDF.

        Args:
            file_content: Raw file bytes.
            original_filename: Original filename.

        Raises:
            InvalidFileError: If validation fails.
        """
        # Check file size
        if len(file_content) > MAX_FILE_SIZE:
            raise InvalidFileError(
                f"File too large: {len(file_content)} bytes (max {MAX_FILE_SIZE} bytes)"
            )

        # Check magic bytes (PDF files start with %PDF)
        if not file_content.startswith(self.PDF_MAGIC):
            raise InvalidFileError("File is not a valid PDF (invalid magic bytes)")

        # Check extension (secondary check)
        if not original_filename.lower().endswith(".pdf"):
            raise InvalidFileError("File must have .pdf extension")

    def _get_file_path(self, listing_id: int) -> Path:
        """Get the storage path for a listing's document.

        Args:
            listing_id: Listing ID.

        Returns:
            Path to the document file.
        """
        return self._documents_dir / f"{listing_id}.pdf"

    def upload_document(
        self,
        listing_id: int,
        file_content: bytes,
        original_filename: str,
    ) -> DocumentRead:
        """Upload a PDF document for a listing.

        Replaces any existing document for the listing.

        Args:
            listing_id: ID of the listing.
            file_content: Raw PDF file bytes.
            original_filename: Original filename from upload.

        Returns:
            Created DocumentRead.

        Raises:
            ListingNotFoundError: If listing doesn't exist.
            InvalidFileError: If file validation fails.
        """
        # Verify listing exists
        listing = self._listing_repo.get_listing_by_id(listing_id)
        if listing is None:
            raise ListingNotFoundError(f"Listing {listing_id} not found")

        # Validate PDF
        self._validate_pdf(file_content, original_filename)

        # Delete existing document if present
        existing = self._doc_repo.get_document_for_listing(listing_id)
        if existing is not None:
            self._delete_document_file(existing.file_path)
            # Clear PDF-sourced options
            self._listing_repo.clear_listing_options(listing_id, source="pdf")
            self._doc_repo.delete_document(existing.id)

        # Create storage path
        self._ensure_documents_dir()
        filename = f"{listing_id}.pdf"
        file_path = self._get_file_path(listing_id)

        # Write file
        file_path.write_bytes(file_content)

        # Create database record
        document = self._doc_repo.create_document(
            listing_id=listing_id,
            filename=filename,
            original_filename=original_filename,
            file_path=str(file_path.relative_to(self._documents_dir.parent)),
            file_size_bytes=len(file_content),
            mime_type="application/pdf",
        )

        return self._to_document_read(document)

    def upload_document_from_file(
        self,
        listing_id: int,
        file_handle: BinaryIO,
        original_filename: str,
    ) -> DocumentRead:
        """Upload a PDF document from a file handle.

        Convenience method for API uploads.

        Args:
            listing_id: ID of the listing.
            file_handle: File handle to read from.
            original_filename: Original filename from upload.

        Returns:
            Created DocumentRead.
        """
        file_content = file_handle.read()
        return self.upload_document(listing_id, file_content, original_filename)

    def process_document(self, listing_id: int) -> EnrichmentResult:
        """Process the document for a listing.

        Extracts text, matches options, and updates listing score.

        Args:
            listing_id: ID of the listing.

        Returns:
            EnrichmentResult with matched options and score changes.

        Raises:
            DocumentNotFoundError: If no document exists for listing.
        """
        document = self._doc_repo.get_document_for_listing(listing_id)
        if document is None:
            raise DocumentNotFoundError(f"No document found for listing {listing_id}")

        listing = self._listing_repo.get_listing_by_id(listing_id)
        if listing is None:
            raise ListingNotFoundError(f"Listing {listing_id} not found")

        # Extract text from PDF
        file_path = self._documents_dir.parent / document.file_path
        extractor = PDFExtractor(file_path)
        pdf_text = extractor.extract_text()

        # Get current options (excluding any existing PDF options which we'll replace)
        existing_options = [
            lo.option.canonical_name
            for lo in listing.options
            if lo.source == "scrape" and lo.option
        ]

        # Perform enrichment
        result = self._enricher.enrich(
            listing_id=listing_id,
            document_id=document.id,
            pdf_text=pdf_text,
            existing_options=existing_options,
            current_score=listing.match_score,
            is_currently_qualified=listing.is_qualified,
        )

        # Update document with extracted text and all options found
        self._doc_repo.update_document(
            document_id=document.id,
            extracted_text=pdf_text,
            options_found_json=json.dumps(result.options_found),
            processed_at=datetime.now(timezone.utc),
        )

        # Clear existing PDF options and add new ones
        self._listing_repo.clear_listing_options(listing_id, source="pdf")

        for option_name in result.new_options_added:
            option, _ = self._listing_repo.get_or_create_option(option_name)
            self._listing_repo.add_option_to_listing(
                listing_id=listing_id,
                option_id=option.id,
                source="pdf",
                document_id=document.id,
            )

        # Update listing score
        self._listing_repo.update_listing(
            listing_id,
            match_score=result.score_after,
            is_qualified=result.is_qualified_after,
        )

        return result

    def get_document(self, listing_id: int) -> DocumentRead | None:
        """Get the document for a listing.

        Args:
            listing_id: Listing ID.

        Returns:
            DocumentRead if exists, None otherwise.
        """
        document = self._doc_repo.get_document_for_listing(listing_id)
        if document is None:
            return None
        return self._to_document_read(document)

    def get_document_path(self, listing_id: int) -> Path | None:
        """Get the file path for a listing's document.

        Args:
            listing_id: Listing ID.

        Returns:
            Path to file if exists, None otherwise.
        """
        document = self._doc_repo.get_document_for_listing(listing_id)
        if document is None:
            return None
        return self._documents_dir.parent / document.file_path

    def delete_document(self, listing_id: int) -> bool:
        """Delete the document for a listing.

        Also removes PDF-sourced options and recalculates score.

        Args:
            listing_id: Listing ID.

        Returns:
            True if deleted, False if not found.
        """
        document = self._doc_repo.get_document_for_listing(listing_id)
        if document is None:
            return False

        # Delete file
        self._delete_document_file(document.file_path)

        # Clear PDF-sourced options
        self._listing_repo.clear_listing_options(listing_id, source="pdf")

        # Delete database record
        self._doc_repo.delete_document(document.id)

        # Recalculate score with remaining options
        self._recalculate_listing_score(listing_id)

        return True

    def _delete_document_file(self, file_path: str) -> None:
        """Delete a document file from disk.

        Args:
            file_path: Relative path to the file.
        """
        full_path = self._documents_dir.parent / file_path
        if full_path.exists():
            os.remove(full_path)

    def _recalculate_listing_score(self, listing_id: int) -> None:
        """Recalculate listing score from remaining options.

        Args:
            listing_id: Listing ID.
        """
        listing = self._listing_repo.get_listing_by_id(listing_id)
        if listing is None:
            return

        # Get remaining matched options
        remaining_options = [
            lo.option.canonical_name for lo in listing.options if lo.option
        ]

        # Calculate new score
        scored_result = self._enricher.calculate_enriched_score(remaining_options, [])

        # Update listing
        self._listing_repo.update_listing(
            listing_id,
            match_score=scored_result.score,
            is_qualified=scored_result.is_qualified,
        )

    def _to_document_read(self, document: object) -> DocumentRead:
        """Convert ORM ListingDocument to DocumentRead Pydantic model.

        Args:
            document: ORM ListingDocument object.

        Returns:
            DocumentRead Pydantic model.
        """
        return DocumentRead.model_validate(document)
