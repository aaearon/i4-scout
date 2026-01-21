"""Pydantic models for data validation."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


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
    category: Optional[str] = Field(None, description="Option category (e.g., 'safety', 'comfort')")
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
    external_id: Optional[str] = Field(None, description="Site-specific listing ID")
    url: HttpUrl
    title: str
    price: Optional[int] = Field(None, ge=0, description="Price in EUR cents")
    price_text: Optional[str] = Field(None, description="Original price text")
    mileage_km: Optional[int] = Field(None, ge=0)
    year: Optional[int] = Field(None, ge=2020, le=2030)
    first_registration: Optional[str] = Field(None, description="MM/YYYY format")
    vin: Optional[str] = Field(None, max_length=17)
    location_city: Optional[str] = None
    location_zip: Optional[str] = None
    location_country: Optional[str] = None
    dealer_name: Optional[str] = None
    dealer_type: Optional[str] = Field(None, description="dealer or private")
    description: Optional[str] = None
    raw_options_text: Optional[str] = Field(None, description="Raw equipment text from listing")
    options_list: list[str] = Field(default_factory=list, description="Parsed option names")
    photo_urls: list[str] = Field(default_factory=list)
    scraped_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class ListingCreate(BaseModel):
    """Data required to create a listing in the database."""

    source: Source
    external_id: Optional[str] = None
    url: str
    title: str
    price: Optional[int] = None
    price_text: Optional[str] = None
    mileage_km: Optional[int] = None
    year: Optional[int] = None
    first_registration: Optional[str] = None
    vin: Optional[str] = None
    location_city: Optional[str] = None
    location_zip: Optional[str] = None
    location_country: Optional[str] = None
    dealer_name: Optional[str] = None
    dealer_type: Optional[str] = None
    description: Optional[str] = None
    raw_options_text: Optional[str] = None
    photo_urls: list[str] = Field(default_factory=list)
    match_score: float = Field(0.0, ge=0, le=100)
    is_qualified: bool = False
    dedup_hash: Optional[str] = None


class ListingRead(ListingCreate):
    """Listing data as read from the database."""

    id: int
    first_seen_at: datetime
    last_seen_at: datetime
    matched_options: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ScrapeSession(BaseModel):
    """Metadata for a scraping session."""

    id: Optional[int] = None
    source: Source
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
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
    dealbreaker_found: Optional[str] = None
    score: float = Field(0.0, ge=0, le=100)
    is_qualified: bool = False


class SearchFilters(BaseModel):
    """Search criteria for filtering listings at source."""

    price_max_eur: Optional[int] = Field(None, description="Max price in EUR")
    mileage_max_km: Optional[int] = Field(None, description="Max mileage in km")
    year_min: Optional[int] = Field(None, description="Min first registration year")
    year_max: Optional[int] = Field(None, description="Max first registration year")
    countries: Optional[list[str]] = Field(
        None, description="Country codes to include (e.g., D, NL, B)"
    )
