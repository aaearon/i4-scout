"""SQLAlchemy ORM models."""

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from i4_scout.models.pydantic_models import ScrapeStatus, Source


def utc_now() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class Listing(Base):
    """Car listing from any source."""

    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(Enum(Source), nullable=False, index=True)
    external_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)

    # Pricing
    price: Mapped[int | None] = mapped_column(Integer, nullable=True)  # EUR cents
    price_text: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Vehicle details
    mileage_km: Mapped[int | None] = mapped_column(Integer, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    first_registration: Mapped[date | None] = mapped_column(Date, nullable=True)
    vin: Mapped[str | None] = mapped_column(String(17), nullable=True)

    # Location
    location_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location_zip: Mapped[str | None] = mapped_column(String(20), nullable=True)
    location_country: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Dealer info
    dealer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    dealer_type: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Content
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_options_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_urls: Mapped[list[str]] = mapped_column(JSON, default=list)

    # Matching
    match_score: Mapped[float] = mapped_column(Float, default=0.0)
    is_qualified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    dedup_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # Timestamps
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    options: Mapped[list["ListingOption"]] = relationship(
        "ListingOption", back_populates="listing", cascade="all, delete-orphan"
    )
    price_history: Mapped[list["PriceHistory"]] = relationship(
        "PriceHistory", back_populates="listing", cascade="all, delete-orphan"
    )
    documents: Mapped[list["ListingDocument"]] = relationship(
        "ListingDocument", back_populates="listing", cascade="all, delete-orphan"
    )

    @property
    def matched_options(self) -> list[str]:
        """Get list of matched option names."""
        return [lo.option.canonical_name for lo in self.options if lo.option]

    def __repr__(self) -> str:
        return f"<Listing(id={self.id}, title='{self.title[:30]}...', price={self.price})>"


class Option(Base):
    """Canonical option/feature definition."""

    __tablename__ = "options"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    canonical_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_bundle: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    listing_options: Mapped[list["ListingOption"]] = relationship(
        "ListingOption", back_populates="option"
    )

    def __repr__(self) -> str:
        return f"<Option(id={self.id}, name='{self.canonical_name}')>"


class ListingDocument(Base):
    """Uploaded PDF document for a listing."""

    __tablename__ = "listing_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    listing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("listings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(
        String(255), nullable=False
    )  # UUID-based storage name
    original_filename: Mapped[str] = mapped_column(
        String(255), nullable=False
    )  # User-visible name
    file_path: Mapped[str] = mapped_column(
        String(500), nullable=False
    )  # Relative path from data/documents/
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(
        String(50), default="application/pdf", nullable=False
    )
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    options_found_json: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON list of all options found in PDF
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    listing: Mapped["Listing"] = relationship("Listing", back_populates="documents")
    options: Mapped[list["ListingOption"]] = relationship(
        "ListingOption", back_populates="document"
    )

    @property
    def options_found(self) -> list[str]:
        """Get list of options found in the PDF."""
        if not self.options_found_json:
            return []
        import json
        try:
            result = json.loads(self.options_found_json)
            return result if isinstance(result, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def __repr__(self) -> str:
        return f"<ListingDocument(id={self.id}, listing_id={self.listing_id}, filename='{self.original_filename}')>"


class ListingOption(Base):
    """Association between listings and matched options."""

    __tablename__ = "listing_options"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    listing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("listings.id", ondelete="CASCADE"), nullable=False
    )
    option_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("options.id", ondelete="CASCADE"), nullable=False
    )
    raw_text: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )  # Original text that matched
    confidence: Mapped[float] = mapped_column(Float, default=1.0)  # Match confidence 0-1

    # Source tracking for PDF enrichment
    source: Mapped[str] = mapped_column(
        String(20), default="scrape", nullable=False
    )  # 'scrape' or 'pdf'
    document_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("listing_documents.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    listing: Mapped["Listing"] = relationship("Listing", back_populates="options")
    option: Mapped["Option"] = relationship("Option", back_populates="listing_options")
    document: Mapped[Optional["ListingDocument"]] = relationship(
        "ListingDocument", back_populates="options"
    )


class PriceHistory(Base):
    """Price change tracking for listings."""

    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    listing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("listings.id", ondelete="CASCADE"), nullable=False
    )
    price: Mapped[int] = mapped_column(Integer, nullable=False)  # EUR cents
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )

    # Relationships
    listing: Mapped["Listing"] = relationship("Listing", back_populates="price_history")


class ScrapeSessionModel(Base):
    """Record of scraping sessions."""

    __tablename__ = "scrape_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(Enum(Source), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(ScrapeStatus), default=ScrapeStatus.PENDING, nullable=False
    )
    listings_found: Mapped[int] = mapped_column(Integer, default=0)
    listings_new: Mapped[int] = mapped_column(Integer, default=0)
    listings_updated: Mapped[int] = mapped_column(Integer, default=0)
    pages_scraped: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list[str]] = mapped_column(JSON, default=list)

    def __repr__(self) -> str:
        return f"<ScrapeSession(id={self.id}, source={self.source}, status={self.status})>"


class ScrapeJob(Base):
    """Background scrape job tracking for API-initiated scrapes."""

    __tablename__ = "scrape_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(ScrapeStatus), default=ScrapeStatus.PENDING, nullable=False
    )
    max_pages: Mapped[int] = mapped_column(Integer, default=50)
    search_filters_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Progress tracking
    current_page: Mapped[int] = mapped_column(Integer, default=0)
    total_found: Mapped[int] = mapped_column(Integer, default=0)
    new_listings: Mapped[int] = mapped_column(Integer, default=0)
    updated_listings: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<ScrapeJob(id={self.id}, source={self.source}, status={self.status})>"
