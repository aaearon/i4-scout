# Plan: Extend API Filtering for Listings

## Overview

Extend the `GET /api/listings` endpoint with additional filtering and sorting capabilities to support a future web frontend.

## Implementation Status: COMPLETE

### Summary of Changes

**Bug Fixed:**
- `count_listings()` now properly includes all filters (was missing `min_score`, causing incorrect total count)

**New Features Added:**

### Range Filters
| Filter | Type | Description |
|--------|------|-------------|
| `price_min` | int | Minimum price in EUR |
| `price_max` | int | Maximum price in EUR |
| `mileage_min` | int | Minimum mileage in km |
| `mileage_max` | int | Maximum mileage in km |
| `year_min` | int | Minimum model year |
| `year_max` | int | Maximum model year |

### Exact Match Filters
| Filter | Type | Description |
|--------|------|-------------|
| `country` | str | Country code (D, NL, B, etc.) |

### Text Search
| Filter | Type | Description |
|--------|------|-------------|
| `search` | str | Search in title and description (case-insensitive contains) |

### Sorting
| Parameter | Values | Description |
|-----------|--------|-------------|
| `sort_by` | price, mileage, score, first_seen, last_seen | Field to sort by |
| `sort_order` | asc, desc | Sort direction (default: desc) |

## Files Modified

1. `src/i4_scout/database/repository.py` - Added filters to `get_listings()` and fixed `count_listings()`
2. `src/i4_scout/services/listing_service.py` - Pass new filters through
3. `src/i4_scout/api/routes/listings.py` - Added query parameters
4. `tests/integration/test_api_listings.py` - Added comprehensive tests
5. `tests/unit/test_listing_service.py` - Fixed test that expected old broken behavior
6. `CLAUDE.md` - Updated API documentation

## Verification

```bash
# Run tests
pytest tests/ -v --ignore=tests/integration/test_scraping_live.py

# Lint and type check
ruff check src/i4_scout/api/ src/i4_scout/services/ src/i4_scout/database/
mypy src/

# Manual API testing
i4-scout serve &

# Test filters
curl "http://localhost:8000/api/listings?price_min=40000&price_max=50000"
curl "http://localhost:8000/api/listings?year_min=2023&mileage_max=30000"
curl "http://localhost:8000/api/listings?country=D&qualified_only=true"
curl "http://localhost:8000/api/listings?search=M%20Sport"

# Test sorting
curl "http://localhost:8000/api/listings?sort_by=price&sort_order=asc"
curl "http://localhost:8000/api/listings?sort_by=score&sort_order=desc"

# Test combined
curl "http://localhost:8000/api/listings?price_max=50000&sort_by=price&sort_order=asc&qualified_only=true"
```

## Commit Message

```
feat(api): add extended filtering and sorting for listings

- Add range filters: price_min/max, mileage_min/max, year_min/max
- Add country filter for location_country
- Add text search in title and description
- Add sorting by price, mileage, score, first_seen, last_seen
- Fix count_listings() to include all filters (was missing min_score)
```
