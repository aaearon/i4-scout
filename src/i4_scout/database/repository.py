"""Repository layer for database operations."""

import functools
import hashlib
from collections.abc import Callable
from datetime import datetime
from typing import Any, TypeVar

from sqlalchemy import desc
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from typing_extensions import ParamSpec

from i4_scout.models.db_models import Listing, ListingOption, Option, PriceHistory
from i4_scout.models.pydantic_models import ListingCreate, Source

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

    def get_listings(
        self,
        source: Source | None = None,
        qualified_only: bool = False,
        min_score: float | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Listing]:
        """Get listings with optional filters.

        Args:
            source: Filter by source.
            qualified_only: Only return qualified listings.
            min_score: Minimum match score.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of matching Listing objects.
        """
        query = self._session.query(Listing)

        if source is not None:
            query = query.filter(Listing.source == source)

        if qualified_only:
            query = query.filter(Listing.is_qualified.is_(True))

        if min_score is not None:
            query = query.filter(Listing.match_score >= min_score)

        # Order by last seen (most recent first)
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
    ) -> int:
        """Count listings with optional filters.

        Args:
            source: Filter by source.
            qualified_only: Only count qualified listings.

        Returns:
            Number of matching listings.
        """
        query = self._session.query(Listing)

        if source is not None:
            query = query.filter(Listing.source == source)

        if qualified_only:
            query = query.filter(Listing.is_qualified.is_(True))

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

        listing.last_seen_at = datetime.utcnow()
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
            source=existing.source,
            title=existing.title,
            price=existing.price,
            mileage_km=existing.mileage_km,
            year=existing.year,
        )

        existing.last_seen_at = datetime.utcnow()

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
            recorded_at=datetime.utcnow(),
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
    ) -> ListingOption:
        """Associate an option with a listing.

        Args:
            listing_id: Listing ID.
            option_id: Option ID.
            raw_text: Original text that matched.
            confidence: Match confidence (0-1).

        Returns:
            Created ListingOption association.
        """
        listing_option = ListingOption(
            listing_id=listing_id,
            option_id=option_id,
            raw_text=raw_text,
            confidence=confidence,
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
    def clear_listing_options(self, listing_id: int) -> int:
        """Remove all option associations for a listing.

        Args:
            listing_id: Listing ID.

        Returns:
            Number of associations deleted.
        """
        deleted = (
            self._session.query(ListingOption)
            .filter(ListingOption.listing_id == listing_id)
            .delete()
        )
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
