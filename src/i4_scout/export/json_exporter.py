"""JSON export functionality for listings."""

import json
from pathlib import Path
from typing import Any, TextIO

from i4_scout.models.db_models import Listing


def listing_to_dict(listing: Listing) -> dict[str, Any]:
    """Convert a Listing to a JSON-serializable dictionary.

    Args:
        listing: Listing ORM object.

    Returns:
        Dictionary representation of the listing.
    """
    return {
        "id": listing.id,
        "source": listing.source.value if listing.source else None,
        "external_id": listing.external_id,
        "url": listing.url,
        "title": listing.title,
        "price": listing.price,
        "mileage_km": listing.mileage_km,
        "year": listing.year,
        "first_registration": listing.first_registration,
        "vin": listing.vin,
        "location": {
            "city": listing.location_city,
            "zip": listing.location_zip,
            "country": listing.location_country,
        },
        "dealer": {
            "name": listing.dealer_name,
            "type": listing.dealer_type,
        },
        "match_score": listing.match_score,
        "is_qualified": listing.is_qualified,
        "matched_options": listing.matched_options,
        "photo_urls": listing.photo_urls,
        "first_seen_at": listing.first_seen_at.isoformat() if listing.first_seen_at else None,
        "last_seen_at": listing.last_seen_at.isoformat() if listing.last_seen_at else None,
    }


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
    # Prepare data
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
