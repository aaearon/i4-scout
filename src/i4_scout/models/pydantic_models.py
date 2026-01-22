"""Pydantic models for data validation."""

from datetime import date, datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


def utc_now() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


class Source(str, Enum):
    """Supported scraping sources."""

    AUTOSCOUT24_DE = "autoscout24_de"
    AUTOSCOUT24_NL = "autoscout24_nl"
    MOBILE_DE = "mobile_de"


class ScrapeStatus(str, Enum):
    """Status of a scrape session."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class OptionConfig(BaseModel):
    """Configuration for a single option to match."""

    name: str = Field(..., description="Canonical name of the option")
    aliases: list[str] = Field(default_factory=list, description="Alternative names/translations")
    category: str | None = Field(None, description="Option category (e.g., 'safety', 'comfort')")
    is_bundle: bool = Field(False, description="Whether this is a package/bundle")
    bundle_contents: list[str] = Field(
        default_factory=list, description="Options included in this bundle"
    )

    model_config = ConfigDict(frozen=True)


class OptionsConfig(BaseModel):
    """User's complete options configuration."""

    required: list[OptionConfig] = Field(
        default_factory=list, description="Must-have options for qualification"
    )
    nice_to_have: list[OptionConfig] = Field(
        default_factory=list, description="Optional but preferred features"
    )
    dealbreakers: list[str] = Field(
        default_factory=list, description="Options that disqualify a listing"
    )

    model_config = ConfigDict(frozen=True)


class ScrapedListing(BaseModel):
    """Raw listing data from scraping."""

    source: Source
    external_id: str | None = Field(None, description="Site-specific listing ID")
    url: HttpUrl
    title: str
    price: int | None = Field(None, ge=0, description="Price in EUR cents")
    price_text: str | None = Field(None, description="Original price text")
    mileage_km: int | None = Field(None, ge=0)
    year: int | None = Field(None, ge=2020, le=2030)
    first_registration: str | None = Field(None, description="MM/YYYY format")
    vin: str | None = Field(None, max_length=17)
    location_city: str | None = None
    location_zip: str | None = None
    location_country: str | None = None
    dealer_name: str | None = None
    dealer_type: str | None = Field(None, description="dealer or private")
    exterior_color: str | None = None
    interior_color: str | None = None
    interior_material: str | None = None
    description: str | None = None
    raw_options_text: str | None = Field(None, description="Raw equipment text from listing")
    options_list: list[str] = Field(default_factory=list, description="Parsed option names")
    photo_urls: list[str] = Field(default_factory=list)
    scraped_at: datetime = Field(default_factory=utc_now)

    model_config = ConfigDict(frozen=True)


class ListingCreate(BaseModel):
    """Data required to create a listing in the database."""

    source: Source
    external_id: str | None = None
    url: str
    title: str
    price: int | None = None
    price_text: str | None = None
    mileage_km: int | None = None
    year: int | None = None
    first_registration: date | None = None
    vin: str | None = None
    location_city: str | None = None
    location_zip: str | None = None
    location_country: str | None = None
    dealer_name: str | None = None
    dealer_type: str | None = None
    exterior_color: str | None = None
    interior_color: str | None = None
    interior_material: str | None = None
    description: str | None = None
    raw_options_text: str | None = None
    photo_urls: list[str] = Field(default_factory=list)
    match_score: float = Field(0.0, ge=0, le=100)
    is_qualified: bool = False
    dedup_hash: str | None = None
    has_issue: bool = False


class ListingRead(ListingCreate):
    """Listing data as read from the database."""

    id: int
    first_seen_at: datetime
    last_seen_at: datetime
    matched_options: list[str] = Field(default_factory=list)
    document_count: int = Field(default=0, description="Number of uploaded documents")
    notes_count: int = Field(default=0, description="Number of notes")
    price_change: int | None = Field(
        default=None, description="Price change from original (negative=drop, positive=increase)"
    )
    price_change_count: int = Field(default=0, description="Number of price changes (excluding initial)")

    model_config = ConfigDict(from_attributes=True)


class ScrapeSession(BaseModel):
    """Metadata for a scraping session."""

    id: int | None = None
    source: Source
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    status: ScrapeStatus = ScrapeStatus.PENDING
    listings_found: int = 0
    listings_new: int = 0
    listings_updated: int = 0
    pages_scraped: int = 0
    errors: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class MatchResult(BaseModel):
    """Result of matching a listing against options config."""

    matched_required: list[str] = Field(default_factory=list)
    matched_nice_to_have: list[str] = Field(default_factory=list)
    missing_required: list[str] = Field(default_factory=list)
    has_dealbreaker: bool = False
    dealbreaker_found: str | None = None
    score: float = Field(default=0.0, ge=0, le=100)
    is_qualified: bool = False


class SearchFilters(BaseModel):
    """Search criteria for filtering listings at source."""

    price_max_eur: int | None = Field(None, description="Max price in EUR")
    mileage_max_km: int | None = Field(None, description="Max mileage in km")
    year_min: int | None = Field(None, description="Min first registration year")
    year_max: int | None = Field(None, description="Max first registration year")
    countries: list[str] | None = Field(
        None, description="Country codes to include (e.g., D, NL, B)"
    )


class ScrapeProgress(BaseModel):
    """Progress update during scraping."""

    page: int = Field(..., description="Current page being scraped")
    total_pages: int = Field(..., description="Total pages to scrape")
    listings_found: int = Field(..., description="Total listings found so far")
    new_count: int = Field(..., description="New listings created")
    updated_count: int = Field(..., description="Existing listings updated")
    skipped_count: int = Field(..., description="Listings skipped (unchanged)")
    current_listing: str | None = Field(None, description="Title of listing being processed")


class ScrapeResult(BaseModel):
    """Final result of a scrape operation."""

    total_found: int = Field(..., description="Total listings found")
    new_listings: int = Field(..., description="New listings created")
    updated_listings: int = Field(..., description="Existing listings updated")
    skipped_unchanged: int = Field(..., description="Listings skipped (price unchanged)")
    fetched_details: int = Field(..., description="Detail pages actually fetched")


class ScrapeJobRead(BaseModel):
    """Scrape job data as read from the database."""

    id: int
    source: str = Field(..., description="Source being scraped")
    status: ScrapeStatus = Field(..., description="Current job status")
    max_pages: int = Field(..., description="Maximum pages to scrape")
    search_filters: dict[str, object] | None = Field(None, description="Search filter parameters")

    # Progress tracking
    current_page: int = Field(0, description="Current page being processed")
    total_found: int = Field(0, description="Total listings found")
    new_listings: int = Field(0, description="New listings created")
    updated_listings: int = Field(0, description="Existing listings updated")

    # Timestamps
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Error tracking
    error_message: str | None = None

    model_config = ConfigDict(from_attributes=True)


class DocumentRead(BaseModel):
    """Listing document data as read from the database."""

    id: int
    listing_id: int
    filename: str = Field(..., description="UUID-based storage filename")
    original_filename: str = Field(..., description="Original user-uploaded filename")
    file_path: str = Field(..., description="Relative path from data/documents/")
    file_size_bytes: int = Field(..., ge=0, description="File size in bytes")
    mime_type: str = Field(default="application/pdf")
    extracted_text: str | None = Field(None, description="Extracted text from PDF")
    uploaded_at: datetime
    processed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class EnrichmentResult(BaseModel):
    """Result of enriching a listing with options from a PDF document."""

    listing_id: int
    document_id: int
    options_found: list[str] = Field(
        default_factory=list, description="All options found in the PDF"
    )
    new_options_added: list[str] = Field(
        default_factory=list, description="Options not previously matched on the listing"
    )
    score_before: float = Field(..., ge=0, le=100, description="Match score before enrichment")
    score_after: float = Field(..., ge=0, le=100, description="Match score after enrichment")
    is_qualified_before: bool = Field(..., description="Qualification status before enrichment")
    is_qualified_after: bool = Field(..., description="Qualification status after enrichment")


class ListingNoteCreate(BaseModel):
    """Data required to create a note for a listing."""

    content: str = Field(..., min_length=1, description="Note content")


class ListingNoteRead(BaseModel):
    """Note data as read from the database."""

    id: int
    listing_id: int
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
