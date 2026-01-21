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
    {"id": 1, "title": "...", "price": 45000, "mileage_km": 15000, "match_score": 85.0, "is_qualified": true, "url": "...", "location_city": "Berlin", "dealer_name": "...", ...}
  ],
  "count": 10,
  "total": 50,
  "filters": {"qualified_only": true, "min_score": 70.0, "source": null, "limit": 20}
}
```

**`show --json`:**
```json
{"id": 1, "title": "...", "price": 45000, "mileage_km": 15000, "match_score": 85.0, "is_qualified": true, "url": "...", "description": "...", "location_city": "...", "location_zip": "...", "location_country": "DE", "dealer_name": "...", "dealer_type": "dealer", ...}
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
   - `autoscout24_base.py`: Shared parsing for AutoScout24 sites (options, description, JSON-LD)
   - `autoscout24_de.py` / `autoscout24_nl.py`: Site-specific URL patterns and localization
   - **JSON-LD Extraction**: Detail pages contain structured JSON-LD (schema.org) data with dealer/location info:
     - `parse_json_ld_sync()`: Extracts `dealer_name`, `dealer_type` (dealer/private), `location_city`, `location_zip`, `location_country`
     - Normalizes `@type: "AutoDealer"` → "dealer", `@type: "Person"` → "private"
     - Handles missing/malformed JSON-LD gracefully

2. **Matching Engine** (`src/i4_scout/matching/`)
   - `normalizer.py`: Text normalization (German umlauts, case, punctuation)
   - `bundle_expander.py`: Expands package options (e.g., "M Sport Package" → individual options)
   - `option_matcher.py`: Matches listing options against config aliases
   - `scorer.py`: Calculates match score and qualification status

3. **Database** (`src/i4_scout/database/`)
   - SQLAlchemy models with SQLite backend
   - `repository.py`: CRUD operations with URL-based deduplication, price history, and matched options storage
   - `engine.py`: Database engine with 30-second SQLite busy timeout for concurrent access
   - **Tables**: `listings`, `options`, `listing_options` (many-to-many), `listing_documents`, `price_history`, `scrape_sessions`
   - **Retry Logic**: Write operations use `@with_db_retry` decorator (5 attempts, exponential backoff 1-8s) to handle SQLite "database is locked" errors during concurrent scraping

4. **CLI** (`src/i4_scout/cli.py`) - Typer-based CLI with commands: `init-database`, `scrape`, `list`, `show`, `export`, `enrich`, `serve`

5. **Services** (`src/i4_scout/services/`)
   - `listing_service.py`: Business logic for listing operations (get, list, delete)
   - `scrape_service.py`: Orchestrates scraping with progress callbacks

6. **API** (`src/i4_scout/api/`)
   - `main.py`: FastAPI app factory
   - `dependencies.py`: Dependency injection for DB sessions and services
   - `schemas.py`: API response models
   - `routes/`: Endpoint implementations (listings, config, stats)

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
- `listing_options` tracks which options matched for each listing, with a `source` field ('scrape' or 'pdf')
- When a listing is re-scraped, only scrape-sourced options are cleared (PDF-sourced options persist)
- Access matched options via `listing.matched_options` property or JSON output

### PDF Enrichment

Dealers often have incomplete listings on AutoScout24. Users can upload dealer specification PDFs to extract additional options:

**CLI:**
```bash
# Enrich a listing with options from a PDF
i4-scout enrich 42 /path/to/dealer_specs.pdf

# With JSON output for scripting
i4-scout enrich 42 /path/to/dealer_specs.pdf --json
```

**JSON output:**
```json
{
  "listing_id": 42,
  "document_id": 7,
  "options_found": ["M Sport Package", "Laser Light", "Head-Up Display"],
  "new_options_added": ["Laser Light", "Head-Up Display"],
  "score_before": 65.5,
  "score_after": 82.0,
  "is_qualified_before": false,
  "is_qualified_after": true
}
```

**API Endpoints:**
- `POST /api/listings/{id}/document` - Upload/replace PDF (multipart/form-data)
- `GET /api/listings/{id}/document` - Get document metadata
- `GET /api/listings/{id}/document/download` - Download PDF file
- `DELETE /api/listings/{id}/document` - Delete document (recalculates score)
- `POST /api/listings/{id}/document/reprocess` - Re-extract options

**Key behaviors:**
- Single PDF per listing (uploading replaces existing)
- PDF text extraction uses pdfplumber (text + tables)
- Matches options via same logic as scraper (aliases, BMW option codes)
- PDF-sourced options persist across re-scrapes
- Deleting document removes PDF-sourced options and recalculates score

**File storage:** `data/documents/{listing_id}.pdf`

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
- `DocumentRead`: Metadata for uploaded PDF documents
- `EnrichmentResult`: Result of PDF enrichment (options found, score changes)

## API Server

The project includes a FastAPI-based REST API for programmatic access.

### Starting the Server

```bash
# Start API server (default: http://127.0.0.1:8000)
i4-scout serve

# Custom host/port
i4-scout serve --host 0.0.0.0 --port 8080

# Development mode with auto-reload
i4-scout serve --reload
```

### API Endpoints

**Listings:**
- `GET /api/listings` - List listings with pagination and filters
- `GET /api/listings/{id}` - Get single listing
- `GET /api/listings/{id}/price-history` - Get price history
- `DELETE /api/listings/{id}` - Delete a listing

**Configuration:**
- `GET /api/config/options` - Get options matching configuration
- `GET /api/config/filters` - Get search filters configuration

**Statistics:**
- `GET /api/stats` - Get aggregated statistics

**Other:**
- `GET /health` - Health check
- `GET /docs` - OpenAPI documentation (Swagger UI)
- `GET /redoc` - ReDoc documentation

### Query Parameters for `/api/listings`

**Basic Filters:**
```
?source=autoscout24_de     # Filter by source
?qualified_only=true       # Only qualified listings
?min_score=70              # Minimum match score (0-100)
```

**Range Filters:**
```
?price_min=40000           # Minimum price in EUR
?price_max=50000           # Maximum price in EUR
?mileage_min=10000         # Minimum mileage in km
?mileage_max=30000         # Maximum mileage in km
?year_min=2023             # Minimum model year
?year_max=2024             # Maximum model year
```

**Other Filters:**
```
?country=D                 # Country code (D, NL, B, etc.)
?search=M%20Sport          # Text search in title/description (URL-encoded)
```

**Sorting:**
```
?sort_by=price             # Sort by: price, mileage, score, first_seen, last_seen
?sort_order=asc            # Sort direction: asc, desc (default: desc)
```

**Pagination:**
```
?limit=20                  # Results per page (1-100)
?offset=0                  # Pagination offset
```

**Example Combined:**
```
/api/listings?price_max=50000&year_min=2023&qualified_only=true&sort_by=price&sort_order=asc
```

### Database Configuration

The API supports PostgreSQL via `DATABASE_URL` environment variable:

```bash
# SQLite (default)
i4-scout serve

# PostgreSQL
DATABASE_URL=postgresql://user:pass@localhost/i4scout i4-scout serve
```

SQLite features:
- WAL mode enabled for better concurrent access
- 30-second busy timeout for lock contention

### Implementation Details

See `docs/web-interface-implementation-plan.md` for the full implementation plan.

## Web Interface

The project includes a full-featured web dashboard built with HTMX + Jinja2, embedded in FastAPI.

### Technology Stack

- **CSS Framework:** Pico CSS (~10KB) - classless, dark mode, mobile responsive
- **Interactivity:** HTMX (~14KB) - partial page updates, polling
- **Templates:** Jinja2 - integrates with FastAPI
- **Hosting:** Embedded in FastAPI via StaticFiles and Jinja2Templates

### Accessing the Web Interface

Start the server and navigate to `http://localhost:8000/` in your browser:

```bash
i4-scout serve
```

### Pages

**Dashboard (`/`):**
- Statistics overview (total listings, qualified count, averages)
- Listings by source breakdown
- Recent qualified listings
- Auto-refresh every 60 seconds

**Listings (`/listings`):**
- Full listings table with all fields
- Checkbox selection for comparison (max 4 listings)
- Favorite star button per listing (persists in localStorage)
- Hover popover showing options summary (lazy-loaded via HTMX)
- Filter form: source, qualified only, favorites only, score, price, mileage, year, country, search
- Options filtering: collapsible checkbox list for required and nice-to-have options
  - Has ALL mode: require all selected options (AND logic)
  - Has ANY mode: require at least one selected option (OR logic)
- Sorting by price, mileage, score, date
- Pagination with Previous/Next navigation
- Search with debounce (500ms delay)
- URL state preservation (bookmarkable filters)
- Compare bar appears when listings selected (fixed at bottom)

**Listing Detail (`/listings/{id}`):**
- Full listing information
- Location and dealer details
- Favorite button (persists in localStorage)
- Color-coded option cards: green (has), red (missing required), cyan (has nice-to-have), gray (missing nice-to-have)
- Dealbreakers section with expandable keyword list
- Price history table with change indicators
- Delete button with confirmation
- External link to source

**Scrape Control (`/scrape`):**
- Start new scrapes (source, max pages)
- Live job progress (auto-polling every 2s for running jobs)
- Job history with status, counts, timestamps

**Compare (`/compare?ids=1,2,3`):**
- Side-by-side comparison of up to 4 listings
- Basic info section: price, mileage, year, location, dealer, source
- Match score section with qualification status
- Required options matrix with color-coded Yes/No badges
- Nice-to-have options matrix
- Best values highlighted (lowest price/mileage, highest score/year)
- Bookmarkable URL with listing IDs
- Selection stored in localStorage (persists across browser sessions)

### HTMX Partial Endpoints

These endpoints return HTML fragments for HTMX requests:

- `GET /partials/stats` - Stats cards
- `GET /partials/recent-qualified` - Recent qualified listings
- `GET /partials/listings` - Listings table with pagination
  - Options filtering: `?has_option=Laser%20Light&has_option=Harman%20Kardon&options_match=all`
  - `has_option` (repeatable): Filter by option name
  - `options_match`: `all` (AND, default) or `any` (OR)
- `GET /partials/listing/{id}` - Listing detail content
- `GET /partials/listing/{id}/options-summary` - Options summary for hover popover
- `GET /partials/listing/{id}/price-chart` - Price history chart
- `GET /partials/scrape/jobs` - Scrape jobs list
- `GET /partials/scrape/job/{id}` - Single job row (for polling)
