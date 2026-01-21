"""CSV export functionality for listings."""

import csv
from io import StringIO
from pathlib import Path
from typing import TextIO

from i4_scout.models.db_models import Listing

# Columns to export
EXPORT_COLUMNS = [
    "id",
    "source",
    "title",
    "price",
    "mileage_km",
    "year",
    "first_registration",
    "match_score",
    "is_qualified",
    "url",
    "location_city",
    "location_country",
    "dealer_name",
    "dealer_type",
    "vin",
    "first_seen_at",
    "last_seen_at",
]


def listing_to_row(listing: Listing) -> dict[str, str]:
    """Convert a Listing to a CSV row dictionary.

    Args:
        listing: Listing ORM object.

    Returns:
        Dictionary with column names as keys.
    """
    return {
        "id": str(listing.id),
        "source": listing.source.value if hasattr(listing.source, "value") else str(listing.source or ""),
        "title": listing.title or "",
        "price": str(listing.price) if listing.price is not None else "",
        "mileage_km": str(listing.mileage_km) if listing.mileage_km is not None else "",
        "year": str(listing.year) if listing.year is not None else "",
        "first_registration": listing.first_registration.isoformat() if listing.first_registration else "",
        "match_score": f"{listing.match_score:.1f}" if listing.match_score is not None else "",
        "is_qualified": "yes" if listing.is_qualified else "no",
        "url": listing.url or "",
        "location_city": listing.location_city or "",
        "location_country": listing.location_country or "",
        "dealer_name": listing.dealer_name or "",
        "dealer_type": listing.dealer_type or "",
        "vin": listing.vin or "",
        "first_seen_at": listing.first_seen_at.isoformat() if listing.first_seen_at else "",
        "last_seen_at": listing.last_seen_at.isoformat() if listing.last_seen_at else "",
    }


def export_to_csv(
    listings: list[Listing],
    output: Path | TextIO | None = None,
) -> str:
    """Export listings to CSV format.

    Args:
        listings: List of Listing ORM objects.
        output: Optional file path or file-like object. If None, returns string.

    Returns:
        CSV string if output is None, empty string otherwise.
    """
    # Prepare data
    rows = [listing_to_row(listing) for listing in listings]

    if output is None:
        # Return as string
        buffer = StringIO()
        writer = csv.DictWriter(buffer, fieldnames=EXPORT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
        return buffer.getvalue()

    if isinstance(output, Path):
        # Write to file
        with open(output, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=EXPORT_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        return ""

    # Write to file-like object
    writer = csv.DictWriter(output, fieldnames=EXPORT_COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    return ""
