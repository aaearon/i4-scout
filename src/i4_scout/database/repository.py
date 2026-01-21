"""Repository layer for database operations."""

import functools
import hashlib
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, TypeVar

from sqlalchemy import asc, desc, or_
from sqlalchemy import select as sa_select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Query, Session
from sqlalchemy.sql import extract
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from typing_extensions import ParamSpec

from i4_scout.models.db_models import (
    Listing,
    ListingDocument,
    ListingNote,
    ListingOption,
    Option,
    PriceHistory,
    ScrapeJob,
)
from i4_scout.models.pydantic_models import ListingCreate, ScrapeStatus, Source

P = ParamSpec("P")
R = TypeVar("R")

# Retry configuration for database operations
DB_RETRY_MAX_ATTEMPTS = 5
DB_RETRY_WAIT_MIN = 1  # seconds
DB_RETRY_WAIT_MAX = 8  # seconds
DB_RETRY_WAIT_MULTIPLIER = 2


def with_db_retry(func: Callable[P, R]) -> Callable[P, R]:
    """Decorator to retry database operations on SQLite lock errors.

    Retries on sqlalchemy.exc.OperationalError using exponential backoff.
    """

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        for attempt in Retrying(
            retry=retry_if_exception_type(OperationalError),
            stop=stop_after_attempt(DB_RETRY_MAX_ATTEMPTS),
            wait=wait_exponential(
                multiplier=DB_RETRY_WAIT_MULTIPLIER,
                min=DB_RETRY_WAIT_MIN,
                max=DB_RETRY_WAIT_MAX,
            ),
            reraise=True,
        ):
            with attempt:
                return func(*args, **kwargs)
        raise RuntimeError("Retry logic failed unexpectedly")

    return wrapper


class ListingRepository:
    """Repository for Listing CRUD operations with deduplication support."""

    def __init__(self, session: Session) -> None:
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy session instance.
        """
        self._session = session

    # ========== CREATE ==========

    @with_db_retry
    def create_listing(self, data: ListingCreate) -> Listing:
        """Create a new listing in the database.

        Args:
            data: Listing data to create.

        Returns:
            Created Listing ORM object.
        """
        # Compute dedup hash
        dedup_hash = self.compute_dedup_hash(
            source=data.source,
            title=data.title,
            price=data.price,
            mileage_km=data.mileage_km,
            year=data.year,
        )

        listing = Listing(
            source=data.source,
            external_id=data.external_id,
            url=data.url,
            title=data.title,
            price=data.price,
            price_text=data.price_text,
            mileage_km=data.mileage_km,
            year=data.year,
            first_registration=data.first_registration,
            vin=data.vin,
            location_city=data.location_city,
            location_zip=data.location_zip,
            location_country=data.location_country,
            dealer_name=data.dealer_name,
            dealer_type=data.dealer_type,
            description=data.description,
            raw_options_text=data.raw_options_text,
            photo_urls=data.photo_urls,
            match_score=data.match_score,
            is_qualified=data.is_qualified,
            dedup_hash=dedup_hash,
            has_issue=data.has_issue,
        )

        self._session.add(listing)
        self._session.commit()
        self._session.refresh(listing)

        return listing

    @with_db_retry
    def bulk_create_listings(self, listings_data: list[ListingCreate]) -> list[Listing]:
        """Create multiple listings efficiently.

        Args:
            listings_data: List of listing data to create.

        Returns:
            List of created Listing ORM objects.
        """
        listings = []
        for data in listings_data:
            dedup_hash = self.compute_dedup_hash(
                source=data.source,
                title=data.title,
                price=data.price,
                mileage_km=data.mileage_km,
                year=data.year,
            )

            listing = Listing(
                source=data.source,
                external_id=data.external_id,
                url=data.url,
                title=data.title,
                price=data.price,
                price_text=data.price_text,
                mileage_km=data.mileage_km,
                year=data.year,
                first_registration=data.first_registration,
                vin=data.vin,
                location_city=data.location_city,
                location_zip=data.location_zip,
                location_country=data.location_country,
                dealer_name=data.dealer_name,
                dealer_type=data.dealer_type,
                description=data.description,
                raw_options_text=data.raw_options_text,
                photo_urls=data.photo_urls,
                match_score=data.match_score,
                is_qualified=data.is_qualified,
                dedup_hash=dedup_hash,
                has_issue=data.has_issue,
            )
            listings.append(listing)

        self._session.add_all(listings)
        self._session.commit()

        for listing in listings:
            self._session.refresh(listing)

        return listings

    # ========== READ ==========

    def get_listing_by_id(self, listing_id: int) -> Listing | None:
        """Get a listing by its ID.

        Args:
            listing_id: Listing ID.

        Returns:
            Listing if found, None otherwise.
        """
        return self._session.query(Listing).filter(Listing.id == listing_id).first()

    def get_listing_by_url(self, url: str) -> Listing | None:
        """Get a listing by its URL.

        Args:
            url: Listing URL.

        Returns:
            Listing if found, None otherwise.
        """
        return self._session.query(Listing).filter(Listing.url == url).first()

    def listing_exists_with_price(self, url: str, price: int | None) -> bool:
        """Check if a listing exists with the given URL and price.

        Used to skip fetching detail pages for unchanged listings.

        Args:
            url: Listing URL.
            price: Expected price (or None).

        Returns:
            True if listing exists with matching price, False otherwise.
        """
        listing = self.get_listing_by_url(url)
        if listing is None:
            return False
        return listing.price == price

    def _apply_listing_filters(
        self,
        query: Query[Listing],
        source: Source | None = None,
        qualified_only: bool = False,
        min_score: float | None = None,
        price_min: int | None = None,
        price_max: int | None = None,
        mileage_min: int | None = None,
        mileage_max: int | None = None,
        year_min: int | None = None,
        year_max: int | None = None,
        country: str | None = None,
        search: str | None = None,
        has_options: list[str] | None = None,
        options_match: str = "all",
        has_issue: bool | None = None,
    ) -> Query[Listing]:
        """Apply common filters to a listing query.

        Args:
            query: SQLAlchemy query to filter.
            source: Filter by source.
            qualified_only: Only return qualified listings.
            min_score: Minimum match score.
            price_min: Minimum price in EUR.
            price_max: Maximum price in EUR.
            mileage_min: Minimum mileage in km.
            mileage_max: Maximum mileage in km.
            year_min: Minimum model year.
            year_max: Maximum model year.
            country: Country code (D, NL, B, etc.).
            search: Text search in title and description.
            has_options: List of option names to filter by.
            options_match: "all" to require all options, "any" to require any.
            has_issue: Filter by issue status (True, False, or None for all).

        Returns:
            Filtered query.
        """
        if source is not None:
            query = query.filter(Listing.source == source)

        if qualified_only:
            query = query.filter(Listing.is_qualified.is_(True))

        if min_score is not None:
            query = query.filter(Listing.match_score >= min_score)

        if price_min is not None:
            query = query.filter(Listing.price >= price_min)

        if price_max is not None:
            query = query.filter(Listing.price <= price_max)

        if mileage_min is not None:
            query = query.filter(Listing.mileage_km >= mileage_min)

        if mileage_max is not None:
            query = query.filter(Listing.mileage_km <= mileage_max)

        # Filter by year from first_registration date
        if year_min is not None or year_max is not None:
            year_expr = extract("year", Listing.first_registration)
            if year_min is not None:
                query = query.filter(year_expr >= year_min)
            if year_max is not None:
                query = query.filter(year_expr <= year_max)

        if country is not None:
            query = query.filter(Listing.location_country == country)

        if search is not None:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Listing.title.ilike(search_pattern),
                    Listing.description.ilike(search_pattern),
                )
            )

        if has_options:
            if options_match == "all":
                # Require ALL options - intersect subqueries
                for option_name in has_options:
                    subq = (
                        sa_select(ListingOption.listing_id)
                        .join(Option)
                        .where(Option.canonical_name == option_name)
                    )
                    query = query.filter(Listing.id.in_(subq))
            else:
                # Require ANY option - single subquery with IN
                subq = (
                    sa_select(ListingOption.listing_id)
                    .join(Option)
                    .where(Option.canonical_name.in_(has_options))
                    .distinct()
                )
                query = query.filter(Listing.id.in_(subq))

        if has_issue is not None:
            query = query.filter(Listing.has_issue == has_issue)

        return query

    def get_listings(
        self,
        source: Source | None = None,
        qualified_only: bool = False,
        min_score: float | None = None,
        price_min: int | None = None,
        price_max: int | None = None,
        mileage_min: int | None = None,
        mileage_max: int | None = None,
        year_min: int | None = None,
        year_max: int | None = None,
        country: str | None = None,
        search: str | None = None,
        has_options: list[str] | None = None,
        options_match: str = "all",
        has_issue: bool | None = None,
        sort_by: str | None = None,
        sort_order: str = "desc",
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Listing]:
        """Get listings with optional filters.

        Args:
            source: Filter by source.
            qualified_only: Only return qualified listings.
            min_score: Minimum match score.
            price_min: Minimum price in EUR.
            price_max: Maximum price in EUR.
            mileage_min: Minimum mileage in km.
            mileage_max: Maximum mileage in km.
            year_min: Minimum model year.
            year_max: Maximum model year.
            country: Country code (D, NL, B, etc.).
            search: Text search in title and description.
            has_options: List of option names to filter by.
            options_match: "all" to require all options, "any" to require any.
            has_issue: Filter by issue status (True, False, or None for all).
            sort_by: Field to sort by (price, mileage, score, first_seen, last_seen).
            sort_order: Sort direction (asc, desc). Default: desc.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of matching Listing objects.
        """
        query = self._session.query(Listing)
        query = self._apply_listing_filters(
            query,
            source=source,
            qualified_only=qualified_only,
            min_score=min_score,
            price_min=price_min,
            price_max=price_max,
            mileage_min=mileage_min,
            mileage_max=mileage_max,
            year_min=year_min,
            year_max=year_max,
            country=country,
            search=search,
            has_options=has_options,
            options_match=options_match,
            has_issue=has_issue,
        )

        # Sorting
        sort_columns = {
            "price": Listing.price,
            "mileage": Listing.mileage_km,
            "score": Listing.match_score,
            "first_seen": Listing.first_seen_at,
            "last_seen": Listing.last_seen_at,
        }
        if sort_by and sort_by in sort_columns:
            col = sort_columns[sort_by]
            query = query.order_by(desc(col) if sort_order == "desc" else asc(col))
        else:
            # Default: most recently seen first
            query = query.order_by(desc(Listing.last_seen_at))

        if offset is not None:
            query = query.offset(offset)

        if limit is not None:
            query = query.limit(limit)

        return query.all()

    def count_listings(
        self,
        source: Source | None = None,
        qualified_only: bool = False,
        min_score: float | None = None,
        price_min: int | None = None,
        price_max: int | None = None,
        mileage_min: int | None = None,
        mileage_max: int | None = None,
        year_min: int | None = None,
        year_max: int | None = None,
        country: str | None = None,
        search: str | None = None,
        has_options: list[str] | None = None,
        options_match: str = "all",
        has_issue: bool | None = None,
    ) -> int:
        """Count listings with optional filters.

        Args:
            source: Filter by source.
            qualified_only: Only count qualified listings.
            min_score: Minimum match score.
            price_min: Minimum price in EUR.
            price_max: Maximum price in EUR.
            mileage_min: Minimum mileage in km.
            mileage_max: Maximum mileage in km.
            year_min: Minimum model year.
            year_max: Maximum model year.
            country: Country code (D, NL, B, etc.).
            search: Text search in title and description.
            has_options: List of option names to filter by.
            options_match: "all" to require all options, "any" to require any.
            has_issue: Filter by issue status (True, False, or None for all).

        Returns:
            Number of matching listings.
        """
        query = self._session.query(Listing)
        query = self._apply_listing_filters(
            query,
            source=source,
            qualified_only=qualified_only,
            min_score=min_score,
            price_min=price_min,
            price_max=price_max,
            mileage_min=mileage_min,
            mileage_max=mileage_max,
            year_min=year_min,
            year_max=year_max,
            country=country,
            search=search,
            has_options=has_options,
            options_match=options_match,
            has_issue=has_issue,
        )
        return query.count()

    # ========== UPDATE ==========

    @with_db_retry
    def update_listing(self, listing_id: int, **kwargs: Any) -> Listing | None:
        """Update a listing's attributes.

        Args:
            listing_id: Listing ID to update.
            **kwargs: Attributes to update.

        Returns:
            Updated Listing if found, None otherwise.
        """
        listing = self.get_listing_by_id(listing_id)
        if listing is None:
            return None

        for key, value in kwargs.items():
            if hasattr(listing, key):
                setattr(listing, key, value)

        listing.last_seen_at = datetime.now(timezone.utc)
        self._session.commit()
        self._session.refresh(listing)

        return listing

    @with_db_retry
    def toggle_issue(self, listing_id: int, has_issue: bool) -> Listing | None:
        """Set the issue flag for a listing.

        Args:
            listing_id: Listing ID to update.
            has_issue: New value for has_issue flag.

        Returns:
            Updated Listing if found, None otherwise.
        """
        listing = self.get_listing_by_id(listing_id)
        if listing is None:
            return None

        listing.has_issue = has_issue
        self._session.commit()
        self._session.refresh(listing)

        return listing

    # ========== DELETE ==========

    @with_db_retry
    def delete_listing(self, listing_id: int) -> bool:
        """Delete a listing by ID.

        Args:
            listing_id: Listing ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        listing = self.get_listing_by_id(listing_id)
        if listing is None:
            return False

        self._session.delete(listing)
        self._session.commit()
        return True

    # ========== UPSERT / DEDUP ==========

    @with_db_retry
    def upsert_listing(self, data: ListingCreate) -> tuple[Listing, bool]:
        """Create or update a listing based on URL.

        Args:
            data: Listing data.

        Returns:
            Tuple of (Listing, created) where created is True if new.
        """
        existing = self.get_listing_by_url(data.url)

        if existing is None:
            # Create new listing
            listing = self.create_listing(data)
            # Record initial price
            if data.price is not None:
                self.record_price_change(listing.id, data.price)
            return listing, True

        # Update existing listing
        old_price = existing.price

        # Update fields
        existing.external_id = data.external_id or existing.external_id
        existing.title = data.title or existing.title
        existing.price = data.price if data.price is not None else existing.price
        existing.price_text = data.price_text or existing.price_text
        existing.mileage_km = data.mileage_km if data.mileage_km is not None else existing.mileage_km
        existing.year = data.year if data.year is not None else existing.year
        existing.first_registration = data.first_registration or existing.first_registration
        existing.vin = data.vin or existing.vin
        existing.location_city = data.location_city or existing.location_city
        existing.location_zip = data.location_zip or existing.location_zip
        existing.location_country = data.location_country or existing.location_country
        existing.dealer_name = data.dealer_name or existing.dealer_name
        existing.dealer_type = data.dealer_type or existing.dealer_type
        existing.description = data.description or existing.description
        existing.raw_options_text = data.raw_options_text or existing.raw_options_text
        existing.match_score = data.match_score if data.match_score > 0 else existing.match_score
        existing.is_qualified = data.is_qualified

        if data.photo_urls:
            existing.photo_urls = data.photo_urls

        # Update dedup hash
        existing.dedup_hash = self.compute_dedup_hash(
            source=existing.source,  # type: ignore[arg-type]
            title=existing.title,
            price=existing.price,
            mileage_km=existing.mileage_km,
            year=existing.year,
        )

        existing.last_seen_at = datetime.now(timezone.utc)

        self._session.commit()
        self._session.refresh(existing)

        # Record price change if different
        if data.price is not None and old_price != data.price:
            self.record_price_change(existing.id, data.price)

        return existing, False

    def compute_dedup_hash(
        self,
        source: Source,
        title: str,
        price: int | None,
        mileage_km: int | None,
        year: int | None,
    ) -> str:
        """Compute a hash for deduplication based on key attributes.

        Args:
            source: Listing source.
            title: Listing title.
            price: Price in cents.
            mileage_km: Mileage in km.
            year: Model year.

        Returns:
            SHA256 hash string.
        """
        # Normalize values for consistent hashing
        source_val = source.value if isinstance(source, Source) else str(source)
        parts = [
            source_val,
            title.lower().strip() if title else "",
            str(price) if price is not None else "",
            str(mileage_km) if mileage_km is not None else "",
            str(year) if year is not None else "",
        ]
        combined = "|".join(parts)
        return hashlib.sha256(combined.encode()).hexdigest()

    def find_duplicate(
        self,
        source: Source,
        title: str,
        price: int | None,
        mileage_km: int | None,
        year: int | None,
    ) -> Listing | None:
        """Find a potential duplicate listing by attributes.

        Args:
            source: Listing source.
            title: Listing title.
            price: Price in cents.
            mileage_km: Mileage in km.
            year: Model year.

        Returns:
            Matching Listing if found, None otherwise.
        """
        dedup_hash = self.compute_dedup_hash(source, title, price, mileage_km, year)
        return self._session.query(Listing).filter(Listing.dedup_hash == dedup_hash).first()

    # ========== PRICE HISTORY ==========

    @with_db_retry
    def record_price_change(self, listing_id: int, price: int) -> PriceHistory:
        """Record a price change for a listing.

        Args:
            listing_id: Listing ID.
            price: New price in cents.

        Returns:
            Created PriceHistory record.
        """
        history = PriceHistory(
            listing_id=listing_id,
            price=price,
            recorded_at=datetime.now(timezone.utc),
        )
        self._session.add(history)
        self._session.commit()
        self._session.refresh(history)
        return history

    def get_price_history(self, listing_id: int) -> list[PriceHistory]:
        """Get price history for a listing.

        Args:
            listing_id: Listing ID.

        Returns:
            List of PriceHistory records, newest first.
        """
        return (
            self._session.query(PriceHistory)
            .filter(PriceHistory.listing_id == listing_id)
            .order_by(desc(PriceHistory.recorded_at))
            .all()
        )

    # ========== OPTIONS ==========

    @with_db_retry
    def add_option_to_listing(
        self,
        listing_id: int,
        option_id: int,
        raw_text: str | None = None,
        confidence: float = 1.0,
        source: str = "scrape",
        document_id: int | None = None,
    ) -> ListingOption:
        """Associate an option with a listing.

        Args:
            listing_id: Listing ID.
            option_id: Option ID.
            raw_text: Original text that matched.
            confidence: Match confidence (0-1).
            source: Source of the match ('scrape' or 'pdf').
            document_id: ID of the document if source is 'pdf'.

        Returns:
            Created ListingOption association.
        """
        listing_option = ListingOption(
            listing_id=listing_id,
            option_id=option_id,
            raw_text=raw_text,
            confidence=confidence,
            source=source,
            document_id=document_id,
        )
        self._session.add(listing_option)
        self._session.commit()
        self._session.refresh(listing_option)
        return listing_option

    def get_listing_options(self, listing_id: int) -> list[ListingOption]:
        """Get all options associated with a listing.

        Args:
            listing_id: Listing ID.

        Returns:
            List of ListingOption associations.
        """
        return (
            self._session.query(ListingOption)
            .filter(ListingOption.listing_id == listing_id)
            .all()
        )

    @with_db_retry
    def clear_listing_options(
        self,
        listing_id: int,
        source: str | None = None,
    ) -> int:
        """Remove option associations for a listing.

        Args:
            listing_id: Listing ID.
            source: If provided, only clear options from this source ('scrape' or 'pdf').
                    If None, clears all options.

        Returns:
            Number of associations deleted.
        """
        query = self._session.query(ListingOption).filter(
            ListingOption.listing_id == listing_id
        )
        if source is not None:
            query = query.filter(ListingOption.source == source)
        deleted = query.delete()
        self._session.commit()
        return deleted

    @with_db_retry
    def get_or_create_option(
        self,
        canonical_name: str,
        display_name: str | None = None,
        category: str | None = None,
        is_bundle: bool = False,
    ) -> tuple[Option, bool]:
        """Get an option by name or create it if it doesn't exist.

        Args:
            canonical_name: Canonical name for the option.
            display_name: Display name (defaults to canonical).
            category: Option category.
            is_bundle: Whether this is a package/bundle.

        Returns:
            Tuple of (Option, created) where created is True if new.
        """
        option = (
            self._session.query(Option)
            .filter(Option.canonical_name == canonical_name)
            .first()
        )

        if option is not None:
            return option, False

        option = Option(
            canonical_name=canonical_name,
            display_name=display_name or canonical_name,
            category=category,
            is_bundle=is_bundle,
        )
        self._session.add(option)
        self._session.commit()
        self._session.refresh(option)
        return option, True


class DocumentRepository:
    """Repository for ListingDocument CRUD operations."""

    def __init__(self, session: Session) -> None:
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy session instance.
        """
        self._session = session

    @with_db_retry
    def create_document(
        self,
        listing_id: int,
        filename: str,
        original_filename: str,
        file_path: str,
        file_size_bytes: int,
        mime_type: str = "application/pdf",
    ) -> ListingDocument:
        """Create a new document record.

        Args:
            listing_id: ID of the listing.
            filename: UUID-based storage filename.
            original_filename: Original user-uploaded filename.
            file_path: Relative path from data/documents/.
            file_size_bytes: File size in bytes.
            mime_type: MIME type of the file.

        Returns:
            Created ListingDocument.
        """
        document = ListingDocument(
            listing_id=listing_id,
            filename=filename,
            original_filename=original_filename,
            file_path=file_path,
            file_size_bytes=file_size_bytes,
            mime_type=mime_type,
        )
        self._session.add(document)
        self._session.commit()
        self._session.refresh(document)
        return document

    def get_document(self, document_id: int) -> ListingDocument | None:
        """Get a document by ID.

        Args:
            document_id: Document ID.

        Returns:
            ListingDocument if found, None otherwise.
        """
        return (
            self._session.query(ListingDocument)
            .filter(ListingDocument.id == document_id)
            .first()
        )

    def get_document_for_listing(self, listing_id: int) -> ListingDocument | None:
        """Get the document for a listing (single PDF per listing).

        Args:
            listing_id: Listing ID.

        Returns:
            ListingDocument if exists, None otherwise.
        """
        return (
            self._session.query(ListingDocument)
            .filter(ListingDocument.listing_id == listing_id)
            .first()
        )

    @with_db_retry
    def update_document(
        self,
        document_id: int,
        extracted_text: str | None = None,
        options_found_json: str | None = None,
        processed_at: datetime | None = None,
    ) -> ListingDocument | None:
        """Update a document's extracted text and processing timestamp.

        Args:
            document_id: Document ID.
            extracted_text: Extracted text from PDF.
            options_found_json: JSON list of options found in PDF.
            processed_at: When the document was processed.

        Returns:
            Updated ListingDocument if found, None otherwise.
        """
        document = self.get_document(document_id)
        if document is None:
            return None

        if extracted_text is not None:
            document.extracted_text = extracted_text
        if options_found_json is not None:
            document.options_found_json = options_found_json
        if processed_at is not None:
            document.processed_at = processed_at

        self._session.commit()
        self._session.refresh(document)
        return document

    @with_db_retry
    def delete_document(self, document_id: int) -> bool:
        """Delete a document by ID.

        Args:
            document_id: Document ID.

        Returns:
            True if deleted, False if not found.
        """
        document = self.get_document(document_id)
        if document is None:
            return False

        self._session.delete(document)
        self._session.commit()
        return True

    @with_db_retry
    def delete_document_for_listing(self, listing_id: int) -> bool:
        """Delete the document for a listing.

        Args:
            listing_id: Listing ID.

        Returns:
            True if deleted, False if not found.
        """
        document = self.get_document_for_listing(listing_id)
        if document is None:
            return False

        self._session.delete(document)
        self._session.commit()
        return True


class ScrapeJobRepository:
    """Repository for ScrapeJob CRUD operations."""

    def __init__(self, session: Session) -> None:
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy session instance.
        """
        self._session = session

    @with_db_retry
    def create_job(
        self,
        source: Source,
        max_pages: int = 50,
        search_filters: dict[str, Any] | None = None,
    ) -> ScrapeJob:
        """Create a new scrape job.

        Args:
            source: Source to scrape.
            max_pages: Maximum number of pages to scrape.
            search_filters: Optional search filter parameters.

        Returns:
            Created ScrapeJob.
        """
        import json

        job = ScrapeJob(
            source=source.value,
            max_pages=max_pages,
            search_filters_json=json.dumps(search_filters) if search_filters else None,
        )
        self._session.add(job)
        self._session.commit()
        self._session.refresh(job)
        return job

    def get_job(self, job_id: int) -> ScrapeJob | None:
        """Get a job by ID.

        Args:
            job_id: Job ID.

        Returns:
            ScrapeJob if found, None otherwise.
        """
        return self._session.query(ScrapeJob).filter(ScrapeJob.id == job_id).first()

    def get_recent_jobs(self, limit: int = 20) -> list[ScrapeJob]:
        """Get recent jobs, newest first.

        Args:
            limit: Maximum number of jobs to return.

        Returns:
            List of ScrapeJob objects.
        """
        return (
            self._session.query(ScrapeJob)
            .order_by(desc(ScrapeJob.created_at))
            .limit(limit)
            .all()
        )

    @with_db_retry
    def update_status(self, job_id: int, status: ScrapeStatus) -> ScrapeJob | None:
        """Update job status.

        Args:
            job_id: Job ID.
            status: New status.

        Returns:
            Updated ScrapeJob if found, None otherwise.
        """
        job = self.get_job(job_id)
        if job is None:
            return None

        job.status = status
        if status == ScrapeStatus.RUNNING and job.started_at is None:
            job.started_at = datetime.now(timezone.utc)

        self._session.commit()
        self._session.refresh(job)
        return job

    @with_db_retry
    def update_progress(
        self,
        job_id: int,
        current_page: int | None = None,
        total_found: int | None = None,
        new_listings: int | None = None,
        updated_listings: int | None = None,
    ) -> ScrapeJob | None:
        """Update job progress.

        Args:
            job_id: Job ID.
            current_page: Current page being processed.
            total_found: Total listings found so far.
            new_listings: New listings created.
            updated_listings: Existing listings updated.

        Returns:
            Updated ScrapeJob if found, None otherwise.
        """
        job = self.get_job(job_id)
        if job is None:
            return None

        if current_page is not None:
            job.current_page = current_page
        if total_found is not None:
            job.total_found = total_found
        if new_listings is not None:
            job.new_listings = new_listings
        if updated_listings is not None:
            job.updated_listings = updated_listings

        self._session.commit()
        self._session.refresh(job)
        return job

    @with_db_retry
    def complete_job(
        self,
        job_id: int,
        total_found: int = 0,
        new_listings: int = 0,
        updated_listings: int = 0,
    ) -> ScrapeJob | None:
        """Mark job as completed.

        Args:
            job_id: Job ID.
            total_found: Total listings found.
            new_listings: New listings created.
            updated_listings: Existing listings updated.

        Returns:
            Updated ScrapeJob if found, None otherwise.
        """
        job = self.get_job(job_id)
        if job is None:
            return None

        job.status = ScrapeStatus.COMPLETED
        job.completed_at = datetime.now(timezone.utc)
        job.total_found = total_found
        job.new_listings = new_listings
        job.updated_listings = updated_listings

        self._session.commit()
        self._session.refresh(job)
        return job

    @with_db_retry
    def fail_job(self, job_id: int, error_message: str) -> ScrapeJob | None:
        """Mark job as failed.

        Args:
            job_id: Job ID.
            error_message: Error description.

        Returns:
            Updated ScrapeJob if found, None otherwise.
        """
        job = self.get_job(job_id)
        if job is None:
            return None

        job.status = ScrapeStatus.FAILED
        job.completed_at = datetime.now(timezone.utc)
        job.error_message = error_message

        self._session.commit()
        self._session.refresh(job)
        return job

    @with_db_retry
    def cleanup_old_jobs(self, days: int = 30) -> int:
        """Delete completed/failed jobs older than specified days.

        Args:
            days: Delete jobs older than this many days.

        Returns:
            Number of deleted jobs.
        """
        from datetime import timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        deleted = (
            self._session.query(ScrapeJob)
            .filter(
                ScrapeJob.created_at < cutoff,
                ScrapeJob.status.in_([ScrapeStatus.COMPLETED, ScrapeStatus.FAILED]),
            )
            .delete(synchronize_session=False)
        )
        self._session.commit()
        return deleted


class NoteRepository:
    """Repository for ListingNote CRUD operations."""

    def __init__(self, session: Session) -> None:
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy session instance.
        """
        self._session = session

    @with_db_retry
    def create_note(self, listing_id: int, content: str) -> ListingNote:
        """Create a new note for a listing.

        Args:
            listing_id: ID of the listing.
            content: Note content.

        Returns:
            Created ListingNote.
        """
        note = ListingNote(
            listing_id=listing_id,
            content=content,
        )
        self._session.add(note)
        self._session.commit()
        self._session.refresh(note)
        return note

    def get_notes(self, listing_id: int) -> list[ListingNote]:
        """Get all notes for a listing in reverse chronological order.

        Args:
            listing_id: Listing ID.

        Returns:
            List of ListingNote objects, newest first.
        """
        return (
            self._session.query(ListingNote)
            .filter(ListingNote.listing_id == listing_id)
            .order_by(desc(ListingNote.created_at))
            .all()
        )

    def get_note(self, note_id: int) -> ListingNote | None:
        """Get a note by ID.

        Args:
            note_id: Note ID.

        Returns:
            ListingNote if found, None otherwise.
        """
        return (
            self._session.query(ListingNote)
            .filter(ListingNote.id == note_id)
            .first()
        )

    @with_db_retry
    def delete_note(self, note_id: int) -> bool:
        """Delete a note by ID.

        Args:
            note_id: Note ID.

        Returns:
            True if deleted, False if not found.
        """
        note = self.get_note(note_id)
        if note is None:
            return False

        self._session.delete(note)
        self._session.commit()
        return True
