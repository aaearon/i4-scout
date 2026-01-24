# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BMW i4 listing scraper for AutoScout24 DE/NL. Scrapes car listings, matches against user-defined options configuration, scores and qualifies listings, and stores results in SQLite.

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

# Force re-fetch detail pages for all listings (updates dealer/location info)
i4-scout scrape autoscout24_de --max-pages 5 --force-refresh

# List/export
i4-scout list --qualified
i4-scout export --format csv --qualified

# Recalculate scores after changing scoring weights
i4-scout recalculate-scores
i4-scout recalculate-scores --json  # JSON output

# Database migrations (Alembic)
alembic current                          # Show current revision
alembic upgrade head                     # Apply all pending migrations
alembic downgrade -1                     # Revert last migration
alembic revision --autogenerate -m "description"  # Create new migration
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

**`recalculate-scores --json`:**
```json
{
  "status": "success",
  "total_processed": 222,
  "score_changed": 217,
  "qualification_changed": 0,
  "changes": [
    {"id": 69, "title": "BMW i4 eDrive40...", "old_score": 94.92, "new_score": 85.37, "old_qualified": true, "new_qualified": true}
  ]
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
   - **Vehicle Colors**: Extracts color information from dt/dd pairs:
     - `parse_colors_sync()`: Extracts `exterior_color`, `interior_color`, `interior_material`
     - Exterior color uses manufacturer color name (e.g., "Portimao Blau") with fallback to generic color (e.g., "blau")
     - German labels: Farbe laut Hersteller (manufacturer), Außenfarbe (generic fallback), Farbe der Innenausstattung, Innenausstattung
     - Dutch labels: Oorspronkelijke kleur (manufacturer), Kleur (generic fallback), Kleur interieur, Materiaal

2. **Matching Engine** (`src/i4_scout/matching/`)
   - `normalizer.py`: Text normalization (German umlauts, case, punctuation)
   - `bundle_expander.py`: Expands package options (e.g., "M Sport Package" → individual options)
   - `option_matcher.py`: Matches listing options against config aliases
   - `scorer.py`: Calculates match score and qualification status

3. **Database** (`src/i4_scout/database/`)
   - SQLAlchemy models with SQLite backend
   - `repository.py`: CRUD operations with external_id-based deduplication (cross-site, e.g., same listing on .de and .nl), price history, and matched options storage
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

Score formula: `((required_matched * 75) + (nice_to_have_matched * 25)) / max_possible * 100` (3:1 weight ratio, nice-to-have contributes ~20% to total score)

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

### Issue Marker

Mark listings with issues (e.g., DEKRA report findings, damage, etc.):

**Web Interface:**
- Issue badge displayed in listing detail header (red when has_issue=True)
- Issue toggle button to mark/unmark listings
- Issue icon (warning symbol) shown in listings table for flagged items
- "Has Issues" checkbox filter in listings page

**API:**
```bash
# Mark listing as having an issue
curl -X PATCH "http://localhost:8000/api/listings/42/issue" \
  -H "Content-Type: application/json" \
  -d '{"has_issue": true}'

# Filter listings with issues
curl "http://localhost:8000/api/listings?has_issue=true"
```

### Notes System

Work log style notes with timestamps for each listing. Useful for tracking communication with dealers, scheduling viewings, recording inspection findings, etc.

**Web Interface:**
- Notes section on listing detail page (below document upload)
- Add note form (textarea + submit button)
- Notes displayed in reverse chronological order (newest first)
- Delete button on each note (with confirmation)

**API:**
```bash
# Add a note
curl -X POST "http://localhost:8000/api/listings/42/notes" \
  -H "Content-Type: application/json" \
  -d '{"content": "Called dealer, car is available. Scheduling viewing for Saturday."}'

# List notes
curl "http://localhost:8000/api/listings/42/notes"

# Delete a note
curl -X DELETE "http://localhost:8000/api/listings/42/notes/5"
```

**Database:**
- Notes stored in `listing_notes` table
- Cascade delete: notes are automatically deleted when listing is deleted

### Price Change Visibility

Track and display price changes (drops and increases) for listings:

**Web Interface:**
- Price change indicator in listings table (next to notes count):
  - Green down arrow with amount for price drops (e.g., "↓ -2,000")
  - Red up arrow with amount for price increases (e.g., "↑ +1,500")
- "Has Price Change" checkbox filter in listings page
- Indicator shows total change from original price (first recorded → current)

### Recently Updated Indicator

Show listings that have had price changes within the last 24 hours:

**Web Interface:**
- Refresh icon (↻) in listings table title cell for listings with recent price changes
- "Recently Updated" checkbox filter in listings page
- Tooltip shows hours since last price change

**Logic:**
- A listing is "recently updated" if it has a price change recorded within 24 hours
- Only actual data changes (price) are considered updates, not just re-scraping
- The `last_price_change_at` field tracks when the most recent price change occurred

**API:**
```bash
# Filter listings with price changes
curl "http://localhost:8000/api/listings?has_price_change=true"

# Filter listings with recent price changes (within 24h)
curl "http://localhost:8000/api/listings?recently_updated=true"
```

**ListingRead fields:**
- `price_change`: Total change from original price (negative = drop, positive = increase, null = no change)
- `price_change_count`: Number of price changes recorded (excluding initial price)
- `last_price_change_at`: Timestamp of most recent price change (null if no changes)

### Listing Lifecycle Tracking

Track when listings disappear from the source and show days on market:

**Status values:**
- `active` (default): Listing is currently available on the source
- `delisted`: Listing has disappeared from the source (after 2 consecutive missed scrapes)

**How it works:**
1. During each scrape, listings seen are tracked
2. For listings not seen: `consecutive_misses` is incremented
3. For listings seen: `consecutive_misses` is reset to 0 (status also resets to active if delisted)
4. After 2 consecutive misses, status changes to `delisted`

**Web Interface:**
- Status badge (Active/Delisted) in listing detail header
- Delisted icon in listings table for delisted items
- "Days on market" indicator in listing detail
- Status filter dropdown in filter form (Active / Delisted / All)

**API:**
```bash
# Filter by status
curl "http://localhost:8000/api/listings?status=active"
curl "http://localhost:8000/api/listings?status=delisted"
```

**ListingRead fields:**
- `status`: "active" or "delisted"
- `consecutive_misses`: Number of consecutive scrapes where listing was not seen
- `status_changed_at`: Timestamp when status last changed (null if never changed)
- `days_on_market`: Computed property (first_seen_at to status_changed_at for delisted, to now for active)

### Photo Gallery

Display listing photos with thumbnail navigation and lightbox viewer:

**Features:**
- Photo URLs extracted from listing detail pages
- Main image display (720x540)
- Horizontal thumbnail strip with scroll
- Click thumbnail to change main image
- Click main image to open lightbox
- Lightbox: full-size image, prev/next navigation, keyboard support (arrow keys, Escape)

**Photo URL format:**
- Base URL: `https://prod.pictures.autoscout24.net/listing-images/{guid}_{guid}.jpg`
- Resolution variants: `/120x90.webp` (thumb), `/720x540.webp` (main), `/1280x960.webp` (lightbox)

**Compare page:**
- Thumbnail row showing first photo from each listing
- Click opens lightbox for that listing

**ListingRead fields:**
- `photo_urls`: List of base photo URLs (without resolution suffix)

### Global Scrape Progress Banner

When a scrape job is running, a progress banner is displayed at the top of all pages (except listing detail and compare pages) showing:
- Source being scraped
- Current page progress (e.g., "Page 3 / 10")
- Listings found and new count
- Link to the scrape control page

The banner polls every 2 seconds for updates and automatically disappears when the scrape completes. When no scrape is running, the component polls every 10 seconds to detect new jobs.

**HTMX endpoint:**
- `GET /partials/scrape/active` - Returns progress banner HTML or empty placeholder

### CLI Scrape Job Tracking

CLI-initiated scrapes are now fully integrated with the web interface:

**Features:**
- CLI scrapes create ScrapeJob records visible in `/scrape` page
- Job progress is updated in real-time during scraping
- Jobs can be cancelled from the web interface (scrape stops at next checkpoint)
- KeyboardInterrupt (Ctrl+C) marks the job as CANCELLED

**How cancellation works:**
1. User clicks "Stop Job" in web interface, which sets job status to CANCELLED
2. ScrapeService checks cancellation status before each page and after processing listings
3. When cancelled, the scrape stops gracefully and returns partial results
4. CLI shows cancellation message: "Scrape was cancelled from web interface"

**Job-Listing Association:**
- Each scrape tracks which listings were processed
- Listings are tracked as "new", "updated", or "unchanged"
- Click on Found/New/Updated counts in job history to filter listings
- API: `GET /api/scrape/jobs/{id}/listings?status=new`

**Database:**
- `scrape_job_listings` table tracks job-listing associations
- Foreign keys with CASCADE delete for cleanup

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
- `--force-refresh`: Force re-fetch detail pages for all listings (ignores skip optimization)

Scrape summary includes performance stats:
- `skipped_unchanged`: Listings skipped because price hasn't changed
- `fetched_details`: Detail pages actually fetched

## Testing

- Unit tests use HTML fixtures in `tests/fixtures/`
- Integration tests require database and may use live browser
- Tests are async-aware via `pytest-asyncio` with `asyncio_mode = "auto"`

## Key Pydantic Models

- `ListingCreate`: Input data for creating/upserting listings (includes `has_issue`, color fields)
- `ListingRead`: Listing data as read from database (extends ListingCreate with timestamps)
- `ScrapedListing`: Output from detail page scraping (includes `exterior_color`, `interior_color`, `interior_material`)
- `OptionsConfig`: Parsed YAML configuration for options matching
- `SearchFilters`: Search criteria for source-level filtering (price, mileage, year, countries)
- `MatchResult`: Output from option matching
- `ScoredResult`: Final score and qualification status
- `DocumentRead`: Metadata for uploaded PDF documents
- `EnrichmentResult`: Result of PDF enrichment (options found, score changes)
- `ListingNoteCreate`: Input for creating a note (content)
- `ListingNoteRead`: Note data with id, listing_id, content, created_at

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
- `PATCH /api/listings/{id}/issue` - Set issue flag (body: `{"has_issue": true/false}`)

**Notes:**
- `GET /api/listings/{id}/notes` - List notes for a listing (newest first)
- `POST /api/listings/{id}/notes` - Add a note (body: `{"content": "..."}`)
- `DELETE /api/listings/{id}/notes/{note_id}` - Delete a note

**Configuration:**
- `GET /api/config/options` - Get options matching configuration
- `GET /api/config/filters` - Get search filters configuration

**Statistics:**
- `GET /api/stats` - Get aggregated statistics

**Scrape Jobs:**
- `POST /api/scrape/jobs` - Start a new scrape job
- `GET /api/scrape/jobs` - List recent scrape jobs
- `GET /api/scrape/jobs/{id}` - Get scrape job status
- `POST /api/scrape/jobs/{id}/cancel` - Cancel a running scrape job
- `GET /api/scrape/jobs/{id}/listings` - Get listings processed by job (with optional status filter)

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
?has_issue=true            # Filter by issue status (true/false)
?has_price_change=true     # Filter by price change status (true/false)
?recently_updated=true     # Filter by recent price changes (within 24h)
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
- **Market Pulse** - 7-day velocity stats (new/delisted/net listings, active and qualified totals)
- **Price Drops** - Listings with recent price reductions, sorted by drop magnitude
- **Near-Miss Listings** - High-score unqualified listings (threshold configurable, default 70%)
- **Feature Rarity** - Option frequency showing hardest-to-find and most common options
- **Your Favorites** - Status of starred listings (loaded from localStorage)

**Listings (`/listings`):**
- Full listings table with all fields
- Status icons in title cell:
  - Issue icon (warning symbol, red) for flagged items
  - Updated icon (refresh symbol, blue) for listings with price changes in last 24h
  - Document icon (purple) for listings with uploaded PDF
  - Notes icon with count (blue badge) for listings with notes
- Checkbox selection for comparison (max 4 listings)
- Favorite star button per listing (persists in localStorage)
- Hover popover showing options summary (lazy-loaded via HTMX)
- Hover popover showing notes preview when hovering over notes count badge
- Filter form: source, qualified only, favorites only, has issues, price change, recently updated, score, price, mileage, year, country, search
- Options filtering: collapsible checkbox list for required and nice-to-have options
  - Has ALL mode: require all selected options (AND logic)
  - Has ANY mode: require at least one selected option (OR logic)
- Sorting by price, mileage, score, date
- Pagination with Previous/Next navigation
- Search with debounce (500ms delay)
- URL state preservation (bookmarkable filters)
- Compare bar appears when listings selected (fixed at bottom)
  - "Copy Details" button copies selected listings to clipboard as LLM-friendly markdown
  - "Compare Selected" button navigates to comparison page

**Listing Detail (`/listings/{id}`):**
- Full listing information
- Location and dealer details
- Issue badge (red warning indicator when marked as having issues)
- Issue toggle button (mark/unmark listings with issues, e.g., from DEKRA reports)
- Favorite button (persists in localStorage)
- Color-coded option cards: green (has), red (missing required), cyan (has nice-to-have), gray (missing nice-to-have)
- Dealbreakers section with expandable keyword list
- Price history table with change indicators
- Notes section (work log style notes with timestamps)
  - Add note form (textarea + submit)
  - Notes list (reverse chronological, newest first)
  - Delete note with confirmation
- Delete button with confirmation
- External link to source

**Scrape Control (`/scrape`):**
- Active job status card with progress bar, stats, and stop button
- Start new scrapes (source, max pages, advanced options)
- Live job progress (auto-polling every 2s for running jobs)
- Job history with status, counts, timestamps
- Cancel running jobs via stop button (sets status to CANCELLED)

**Compare (`/compare?ids=1,2,3`):**
- Side-by-side comparison of up to 4 listings
- Basic info section: price, mileage, year, location, dealer, source
- Match score section with qualification and issue status
- Required options matrix with color-coded Yes/No badges
- Nice-to-have options matrix
- Best values highlighted (lowest price/mileage, highest score/year)
- Bookmarkable URL with listing IDs
- Selection stored in localStorage (persists across browser sessions)
- Copy to clipboard: "Copy Details" button exports selected listings as LLM-friendly markdown

### HTMX Partial Endpoints

These endpoints return HTML fragments for HTMX requests:

**Dashboard Widgets:**
- `GET /partials/market-velocity` - Market pulse stats (new/delisted/net)
  - `?days=7` (default): Time window for stats
- `GET /partials/price-drops` - Listings with price drops
  - `?days=7` (default): Time window for price changes
  - `?limit=5` (default): Max listings to show
- `GET /partials/near-miss` - High-score unqualified listings
  - `?threshold=70` (default): Minimum match score
  - `?limit=5` (default): Max listings to show
- `GET /partials/feature-rarity` - Option frequency stats
- `GET /partials/favorites` - User's favorited listings
  - `?ids=1,2,3`: Comma-separated listing IDs from localStorage

**Legacy Dashboard (deprecated):**
- `GET /partials/stats` - Stats cards
- `GET /partials/recent-qualified` - Recent qualified listings

**Listings:**
- `GET /partials/listings` - Listings table with pagination
  - Options filtering: `?has_option=Laser%20Light&has_option=Harman%20Kardon&options_match=all`
  - `has_option` (repeatable): Filter by option name
  - `options_match`: `all` (AND, default) or `any` (OR)
  - `has_issue`: Filter by issue status (true/false)
  - `recently_updated`: Filter by recent price changes (true/false)
- `GET /partials/listing/{id}` - Listing detail content
- `GET /partials/listing/{id}/options-summary` - Options summary for hover popover
- `GET /partials/listing/{id}/notes-summary` - Notes summary for hover popover
- `GET /partials/listing/{id}/price-chart` - Price history chart
- `PATCH /partials/listing/{id}/issue` - Toggle issue flag (returns updated button)
- `GET /partials/listing/{id}/notes` - Notes section
- `POST /partials/listing/{id}/notes` - Add note (returns new note HTML)
- `DELETE /partials/listing/{id}/notes/{note_id}` - Delete note
- `GET /partials/scrape/active` - Global progress banner (polls every 2s when running, 10s otherwise)
- `GET /partials/scrape/active-status` - Detailed job status card for scrape page
- `GET /partials/scrape/jobs` - Scrape jobs list
- `GET /partials/scrape/job/{id}` - Single job row (for polling)
