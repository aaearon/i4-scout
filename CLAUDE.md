# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BMW i4 eDrive40 listing scraper for AutoScout24 DE/NL. Scrapes car listings, matches against user-defined options configuration, scores and qualifies listings, and stores results in SQLite.

## Common Commands

```bash
# Activate virtual environment
source .venv/bin/activate

# Install (editable + dev dependencies)
pip install -e ".[dev]"

# Install Playwright browsers (required once)
playwright install chromium

# Run all tests
pytest tests/ -v

# Run single test file
pytest tests/unit/test_normalizer.py -v

# Run single test
pytest tests/unit/test_normalizer.py::test_normalize_german_characters -v

# Lint
ruff check src/ tests/

# Type check
mypy src/

# Initialize database
i4-scout init-database

# Scrape listings
i4-scout scrape autoscout24_de --max-pages 5
i4-scout scrape autoscout24_nl --max-pages 5 --no-headless

# Scrape with search filter overrides (CLI overrides config values)
i4-scout scrape autoscout24_de --max-pages 5 --price-max 45000 --year-min 2024
i4-scout scrape autoscout24_de --max-pages 5 -C D -C NL -C B  # Multiple countries

# Scrape without caching (cache is enabled by default)
i4-scout scrape autoscout24_de --max-pages 5 --no-cache

# List/export
i4-scout list --qualified
i4-scout export --format csv --qualified
```

## LLM-Friendly Output (--json flag)

All data commands support `--json` for structured output optimized for programmatic/LLM consumption:

```bash
# List all listings as JSON
i4-scout list --json

# List qualified listings with filters as JSON
i4-scout list --qualified --min-score 70 --json

# Show single listing as JSON
i4-scout show 1 --json

# Scrape and get JSON summary (suppresses progress output)
i4-scout scrape autoscout24_de --max-pages 3 --json
```

### JSON Output Schemas

**`list --json`:**
```json
{
  "listings": [
    {"id": 1, "title": "...", "price": 45000, "mileage_km": 15000, "match_score": 85.0, "is_qualified": true, "url": "...", ...}
  ],
  "count": 10,
  "total": 50,
  "filters": {"qualified_only": true, "min_score": 70.0, "source": null, "limit": 20}
}
```

**`show --json`:**
```json
{"id": 1, "title": "...", "price": 45000, "mileage_km": 15000, "match_score": 85.0, "is_qualified": true, "url": "...", "description": "...", ...}
```

**`scrape --json`:**
```json
{
  "status": "success",
  "source": "autoscout24_de",
  "max_pages": 3,
  "cache_enabled": true,
  "results": {
    "total_found": 45,
    "new_listings": 12,
    "updated_listings": 8,
    "skipped_unchanged": 25,
    "fetched_details": 20
  }
}
```

## Architecture

### Core Data Flow

```
Scraper → Parser → OptionMatcher → Scorer → Repository → SQLite
                        ↓
               OptionsConfig (YAML)
```

1. **Scrapers** (`src/i4_scout/scrapers/`) - Playwright-based scrapers for AutoScout24 sites
   - `base.py`: Abstract base class with retry logic, rate limiting, cookie consent handling, HTML caching
   - `cache.py`: File-based HTML cache with TTL (1h for search pages, 24h for detail pages)
   - `autoscout24_base.py`: Shared parsing for AutoScout24 sites
   - `autoscout24_de.py` / `autoscout24_nl.py`: Site-specific URL patterns and localization

2. **Matching Engine** (`src/i4_scout/matching/`)
   - `normalizer.py`: Text normalization (German umlauts, case, punctuation)
   - `bundle_expander.py`: Expands package options (e.g., "M Sport Package" → individual options)
   - `option_matcher.py`: Matches listing options against config aliases
   - `scorer.py`: Calculates match score and qualification status

3. **Database** (`src/i4_scout/database/`)
   - SQLAlchemy models with SQLite backend
   - `repository.py`: CRUD operations with URL-based deduplication, price history, and matched options storage
   - `engine.py`: Database engine with 30-second SQLite busy timeout for concurrent access
   - **Tables**: `listings`, `options`, `listing_options` (many-to-many), `price_history`, `scrape_sessions`
   - **Retry Logic**: Write operations use `@with_db_retry` decorator (5 attempts, exponential backoff 1-8s) to handle SQLite "database is locked" errors during concurrent scraping

4. **CLI** (`src/i4_scout/cli.py`) - Typer-based CLI with commands: `init-database`, `scrape`, `list`, `show`, `export`

### Options Configuration

Options are defined in `config/options.yaml` with:
- **required**: ALL must match for "qualified" status
- **nice_to_have**: Contribute to score but not required
- **dealbreakers**: Instant disqualification if found
- **search_filters**: Source-level filtering (applied to AutoScout24 URL parameters)

Each option has aliases (multilingual variations), optional BMW option codes, and bundle expansion support.

### Search Filters

Search filters are applied at the source (AutoScout24 URL) to reduce noise before scraping:

```yaml
search_filters:
  price_max_eur: 55000      # Maximum price in EUR
  mileage_max_km: 50000     # Maximum mileage in km
  year_min: 2023            # Minimum first registration year
  year_max: 2025            # Maximum first registration year (optional)
  countries:                # Country codes to include
    - D                     # Germany
    - NL                    # Netherlands
```

CLI options override config values:
- `--price-max` / `-P`: Max price in EUR
- `--mileage-max` / `-M`: Max mileage in km
- `--year-min` / `-Y`: Min first registration year
- `--country` / `-C`: Country codes (repeatable, e.g., `-C D -C NL`)

AutoScout24 country codes: D (Germany), NL (Netherlands), B (Belgium), A (Austria), L (Luxembourg), F (France), I (Italy), E (Spain), CH (Switzerland).

### Qualification Logic

A listing is qualified when:
1. ALL required options are matched (via option list OR title/description text search)
2. NO dealbreakers are found

Score formula: `((required_matched * 100) + (nice_to_have_matched * 10)) / max_possible * 100`

### Matched Options Storage

During scraping, matched options (both required and nice-to-have) are persisted:
- Each unique option is stored once in the `options` table (canonical names)
- `listing_options` tracks which options matched for each listing
- When a listing is re-scraped, its options are cleared and re-matched
- Access matched options via `listing.matched_options` property or JSON output

### Scraper Performance Optimizations

The scraper includes two performance optimizations to reduce unnecessary network requests:

1. **Skip Unchanged Listings**: Before fetching a detail page, the scraper checks if the listing already exists in the database with the same price. If the price hasn't changed, the detail fetch is skipped (the listing data is unlikely to have changed).

2. **HTML Caching**: HTML responses are cached to disk with TTL-based expiration:
   - Search pages: 1-hour TTL (listings change frequently)
   - Detail pages: 24-hour TTL (content rarely changes)
   - Cache location: `.cache/html/`
   - Disable with `--no-cache` flag

CLI options:
- `--no-cache`: Disable HTML caching (cache is enabled by default)

Scrape summary includes performance stats:
- `skipped_unchanged`: Listings skipped because price hasn't changed
- `fetched_details`: Detail pages actually fetched

## Testing

- Unit tests use HTML fixtures in `tests/fixtures/`
- Integration tests require database and may use live browser
- Tests are async-aware via `pytest-asyncio` with `asyncio_mode = "auto"`

## Key Pydantic Models

- `ListingCreate`: Input data for creating/upserting listings
- `ScrapedListing`: Output from detail page scraping
- `OptionsConfig`: Parsed YAML configuration for options matching
- `SearchFilters`: Search criteria for source-level filtering (price, mileage, year, countries)
- `MatchResult`: Output from option matching
- `ScoredResult`: Final score and qualification status
