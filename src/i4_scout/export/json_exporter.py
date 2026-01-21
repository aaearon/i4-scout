"""JSON export functionality for listings."""

import json
from pathlib import Path
from typing import Any, TextIO

from i4_scout.models.db_models import Listing
from i4_scout.models.pydantic_models import ListingRead


def listing_to_dict(listing: Listing) -> dict[str, Any]:
    """Convert a Listing ORM object to a JSON-serializable dictionary.

    Uses ListingRead Pydantic model for consistent serialization.

    Args:
        listing: Listing ORM object.

    Returns:
        Dictionary representation of the listing.
    """
    # Convert ORM object to Pydantic model
    listing_read = ListingRead(
        id=listing.id,
        source=listing.source,
        external_id=listing.external_id,
        url=listing.url,
        title=listing.title,
        price=listing.price,
        price_text=listing.price_text,
        mileage_km=listing.mileage_km,
        year=listing.year,
        first_registration=listing.first_registration,
        vin=listing.vin,
        location_city=listing.location_city,
        location_zip=listing.location_zip,
        location_country=listing.location_country,
        dealer_name=listing.dealer_name,
        dealer_type=listing.dealer_type,
        description=listing.description,
        raw_options_text=listing.raw_options_text,
        photo_urls=listing.photo_urls or [],
        match_score=listing.match_score,
        is_qualified=listing.is_qualified,
        first_seen_at=listing.first_seen_at,
        last_seen_at=listing.last_seen_at,
        matched_options=listing.matched_options,
    )

    # Use Pydantic's model_dump with JSON-compatible serialization
    data: dict[str, Any] = listing_read.model_dump()

    # Convert source enum to string value
    if data.get("source"):
        data["source"] = data["source"].value

    # Convert datetime objects to ISO format strings
    if data.get("first_seen_at"):
        data["first_seen_at"] = data["first_seen_at"].isoformat()
    if data.get("last_seen_at"):
        data["last_seen_at"] = data["last_seen_at"].isoformat()

    return data


def export_to_json(
    listings: list[Listing],
    output: Path | TextIO | None = None,
    indent: int = 2,
) -> str:
    """Export listings to JSON format.

    Args:
        listings: List of Listing ORM objects.
        output: Optional file path or file-like object. If None, returns string.
        indent: JSON indentation level.

    Returns:
        JSON string if output is None, empty string otherwise.
    """
    # Prepare data using Pydantic serialization
    data = {
        "count": len(listings),
        "listings": [listing_to_dict(listing) for listing in listings],
    }

    if output is None:
        # Return as string
        return json.dumps(data, indent=indent, ensure_ascii=False)

    if isinstance(output, Path):
        # Write to file
        with open(output, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        return ""

    # Write to file-like object
    json.dump(data, output, indent=indent, ensure_ascii=False)
    return ""
