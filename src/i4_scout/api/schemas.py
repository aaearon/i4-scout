"""API response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from i4_scout.models.pydantic_models import ListingRead, Source


class PaginatedListings(BaseModel):
    """Paginated listings response."""

    listings: list[ListingRead]
    count: int = Field(description="Number of listings in this response")
    total: int = Field(description="Total number of listings matching filters")
    limit: int = Field(description="Maximum results per page")
    offset: int = Field(description="Number of results skipped")


class ListingFilters(BaseModel):
    """Query parameters for listing filters."""

    source: Source | None = None
    qualified_only: bool = False
    min_score: float | None = Field(None, ge=0, le=100)
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)


class PriceHistoryEntry(BaseModel):
    """Single price history entry."""

    price: int = Field(description="Price in EUR")
    recorded_at: datetime


class PriceHistoryResponse(BaseModel):
    """Price history response for a listing."""

    listing_id: int
    current_price: int | None
    history: list[PriceHistoryEntry]


class StatsResponse(BaseModel):
    """Aggregated statistics response."""

    total_listings: int
    qualified_listings: int
    listings_by_source: dict[str, int]
    average_price: float | None
    average_mileage: float | None
    average_score: float | None


class OptionConfigResponse(BaseModel):
    """Single option configuration."""

    name: str
    aliases: list[str]
    category: str | None = None
    is_bundle: bool = False
    bundle_contents: list[str]


class OptionsConfigResponse(BaseModel):
    """Options configuration response."""

    required: list[OptionConfigResponse]
    nice_to_have: list[OptionConfigResponse]
    dealbreakers: list[str]


class SearchFiltersResponse(BaseModel):
    """Search filters configuration response."""

    price_max_eur: int | None
    mileage_max_km: int | None
    year_min: int | None
    year_max: int | None
    countries: list[str]


class DeleteResponse(BaseModel):
    """Response for delete operations."""

    success: bool
    message: str


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str
