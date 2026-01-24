# i4-scout Architecture Documentation

## 1. Overview

### System Purpose
BMW i4 listing scraper for AutoScout24 DE/NL. The system scrapes car listings, matches against user-defined options configuration, scores and qualifies listings based on requirements, and stores results in SQLite with a web interface for management.

### High-Level Architecture
```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                  CLI / API                                       │
│                     (Typer CLI | FastAPI REST + HTMX Web)                       │
├─────────────────────────────────────────────────────────────────────────────────┤
│                              Service Layer                                       │
│     ScrapeService | ListingService | DocumentService | NoteService | JobService  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                             Matching Engine                                      │
│         Normalizer → Bundle Expander → Option Matcher → Scorer                  │
├──────────────────────────────┬──────────────────────────────────────────────────┤
│        Scraping System       │              Repository Layer                     │
│   BrowserManager (Playwright)│    ListingRepository | DocumentRepository        │
│   BaseScraper → AutoScout24  │    NoteRepository | ScrapeJobRepository          │
│   HTMLCache (File-based)     │                                                   │
├──────────────────────────────┴──────────────────────────────────────────────────┤
│                              Database Layer                                      │
│                    SQLAlchemy ORM | SQLite (WAL mode)                           │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      ↓
                          ┌─────────────────────┐
                          │  config/options.yaml │
                          │  (Options Config)    │
                          └─────────────────────┘
```

### Technology Stack

| Layer | Technology |
|-------|------------|
| CLI | Typer |
| API | FastAPI |
| Web UI | Jinja2 + HTMX + Pico CSS |
| Scraping | Playwright + playwright-stealth |
| ORM | SQLAlchemy 2.0 |
| Database | SQLite (WAL mode) / PostgreSQL |
| Validation | Pydantic v2 |
| PDF Processing | pdfplumber |
| Testing | pytest + pytest-asyncio |

---

## 2. Core Data Flow

```
                    ┌──────────────┐
                    │   Scraper    │
                    │ (Playwright) │
                    └──────┬───────┘
                           │ HTML
                           ▼
                    ┌──────────────┐
                    │    Parser    │
                    │ (BeautifulSoup)│
                    └──────┬───────┘
                           │ ScrapedListing
                           ▼
┌────────────────┐  ┌──────────────┐
│ OptionsConfig  │─▶│OptionMatcher │
│ (YAML)         │  └──────┬───────┘
└────────────────┘         │ MatchResult
                           ▼
                    ┌──────────────┐
                    │    Scorer    │
                    └──────┬───────┘
                           │ ScoredResult
                           ▼
                    ┌──────────────┐
                    │  Repository  │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │   SQLite     │
                    └──────────────┘
```

### Processing Steps

1. **Scrape Search Page** - Extract listing cards with basic info (title, URL, price)
2. **Fetch Detail Pages** - Get full listing details (options, description, JSON-LD)
3. **Parse Data** - Extract structured data from HTML (options list, colors, dealer info)
4. **Expand Bundles** - Expand package options into individual components
5. **Match Options** - Match listing options against configuration aliases
6. **Calculate Score** - Compute match score and qualification status
7. **Persist** - Upsert listing with deduplication and price history

---

## 3. Data Models

### 3.1 Pydantic Models

Location: `src/i4_scout/models/pydantic_models.py`

#### Configuration Models
| Model | Purpose |
|-------|---------|
| `OptionConfig` | Single option definition with name, aliases, category, bundle info |
| `OptionsConfig` | Complete config: required, nice_to_have, dealbreakers lists |
| `SearchFilters` | Search criteria: price_max_eur, mileage_max_km, year_min/max, countries |

#### Data Transfer Models
| Model | Purpose |
|-------|---------|
| `ScrapedListing` | Raw data from scraping (immutable, frozen=True) |
| `ListingCreate` | Input for creating/upserting listings |
| `ListingRead` | Output from database with computed fields |

**`ListingRead` computed fields:**
- `matched_options`: List of matched option names
- `document_count`, `notes_count`: Related entity counts
- `price_change`, `price_change_count`, `last_price_change_at`: Price history
- `status`, `status_changed_at`, `consecutive_misses`: Lifecycle tracking
- `days_on_market`: Computed property (first_seen to status_changed_at or now)

#### Matching Models
| Model | Purpose |
|-------|---------|
| `MatchResult` | Matched/missing options, dealbreaker status |
| `ScoredResult` | Extended MatchResult with score (0-100) and is_qualified |

#### Enums
| Enum | Values |
|------|--------|
| `Source` | AUTOSCOUT24_DE, AUTOSCOUT24_NL, MOBILE_DE |
| `ScrapeStatus` | PENDING, RUNNING, COMPLETED, FAILED, CANCELLED |
| `ListingStatus` | ACTIVE, DELISTED |

#### Process Models
| Model | Purpose |
|-------|---------|
| `ScrapeProgress` | Real-time progress updates (page, counts, current_listing) |
| `ScrapeResult` | Final scrape summary (total_found, new_listings, updated, skipped) |
| `ScrapeJobRead` | Background job status and progress |

#### Enhancement Models
| Model | Purpose |
|-------|---------|
| `DocumentRead` | PDF document metadata |
| `EnrichmentResult` | PDF enrichment results (options found, score changes) |
| `ListingNoteRead` | Work log note data |

### 3.2 SQLAlchemy ORM Models

Location: `src/i4_scout/models/db_models.py`

#### Entity Relationship Diagram
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                listings                                      │
│ ─────────────────────────────────────────────────────────────────────────── │
│ PK id                                                                        │
│    source (indexed)          external_id            url (unique)             │
│    title                     price                  mileage_km               │
│    year                      first_registration     vin                      │
│    exterior_color            interior_color         interior_material        │
│    location_city/zip/country dealer_name/type                               │
│    description               raw_options_text       photo_urls (JSON)        │
│    match_score               is_qualified (indexed) dedup_hash (indexed)     │
│    has_issue (indexed)       status (indexed)       status_changed_at        │
│    consecutive_misses        first_seen_at          last_seen_at             │
└──────────────────┬──────────┬──────────┬──────────┬──────────────────────────┘
                   │          │          │          │
       ┌───────────┘          │          │          └──────────┐
       ▼                      ▼          ▼                     ▼
┌──────────────────┐  ┌──────────────┐  ┌─────────────────┐  ┌──────────────┐
│  listing_options │  │ price_history│  │listing_documents│  │listing_notes │
│ ───────────────  │  │ ──────────── │  │ ─────────────── │  │ ──────────── │
│ PK id            │  │ PK id        │  │ PK id           │  │ PK id        │
│ FK listing_id    │  │ FK listing_id│  │ FK listing_id   │  │ FK listing_id│
│ FK option_id     │  │    price     │  │    filename     │  │    content   │
│ FK document_id   │  │    recorded_at│ │    original_fn  │  │    created_at│
│    raw_text      │  └──────────────┘  │    file_path    │  └──────────────┘
│    confidence    │                    │    file_size    │
│    source        │                    │    extracted_txt│
└────────┬─────────┘                    │    options_json │
         │                              │    uploaded_at  │
         ▼                              │    processed_at │
┌──────────────────┐                    └─────────────────┘
│     options      │
│ ──────────────── │
│ PK id            │
│    canonical_name│
│    display_name  │
│    category      │
│    is_bundle     │
└──────────────────┘

┌──────────────────┐      ┌─────────────────────┐
│   scrape_jobs    │      │ scrape_job_listings │
│ ──────────────── │      │ ─────────────────── │
│ PK id            │◄─────│ FK scrape_job_id    │
│    source        │      │ FK listing_id       │
│    status        │      │    status           │
│    max_pages     │      │    created_at       │
│    current_page  │      └─────────────────────┘
│    total_found   │
│    new_listings  │
│    updated_lstng │
│    created_at    │
│    started_at    │
│    completed_at  │
│    error_message │
└──────────────────┘
```

#### Tables

| Table | Purpose | Key Indexes |
|-------|---------|-------------|
| `listings` | Main car listing entity | source, is_qualified, has_issue, status, dedup_hash |
| `options` | Canonical options registry | canonical_name (unique) |
| `listing_options` | Many-to-many with source tracking | listing_id, option_id |
| `price_history` | Price change audit trail | listing_id |
| `listing_documents` | PDF metadata and extracted text | listing_id |
| `listing_notes` | Work log notes | listing_id |
| `scrape_jobs` | Background job tracking | - |
| `scrape_job_listings` | Job-listing association tracking | scrape_job_id, listing_id |
| `scrape_sessions` | Historical scrape records | - |

#### Key Fields

**`listings.source`**: Enum (`autoscout24_de`, `autoscout24_nl`, `mobile_de`)

**`listings.status`**: Enum (`active`, `delisted`) - lifecycle tracking for listings

**`listing_options.source`**: String (`scrape` or `pdf`) - tracks origin of matched options

**`listings.dedup_hash`**: SHA256 hash of (source, title, price, mileage, year) for cross-listing deduplication

**`scrape_job_listings.status`**: String (`new`, `updated`, `unchanged`) - tracks how listing was processed in job

---

## 4. Database Layer

### 4.1 Engine Configuration

Location: `src/i4_scout/database/engine.py`

#### Connection Priority
1. `DATABASE_URL` environment variable (PostgreSQL/external)
2. Explicit `db_path` argument
3. `I4_SCOUT_DB_PATH` environment variable
4. Default: `data/i4_scout.db`

#### SQLite Configuration
```python
connect_args = {
    "check_same_thread": False,  # Allow cross-thread access
    "timeout": 30,               # 30-second busy timeout
}
# WAL mode enabled for better concurrent access
conn.execute("PRAGMA journal_mode=WAL")
```

#### PostgreSQL Configuration
```python
engine_kwargs = {
    "pool_size": 5,
    "pool_recycle": 3600,  # Recycle connections after 1 hour
}
```

### 4.2 Repository Pattern

Location: `src/i4_scout/database/repository.py`

#### Repositories

| Repository | Responsibility |
|------------|----------------|
| `ListingRepository` | CRUD, filtering, deduplication, price history, options management |
| `DocumentRepository` | PDF document CRUD |
| `NoteRepository` | Notes CRUD |
| `ScrapeJobRepository` | Job lifecycle management |

#### Retry Decorator

```python
@with_db_retry  # Decorator on write operations
def create_listing(self, data: ListingCreate) -> Listing:
    ...

# Configuration
DB_RETRY_MAX_ATTEMPTS = 5
DB_RETRY_WAIT_MIN = 1      # seconds
DB_RETRY_WAIT_MAX = 8      # seconds
DB_RETRY_WAIT_MULTIPLIER = 2  # exponential backoff
```

Handles SQLite "database is locked" errors during concurrent scraping with tenacity-based exponential backoff.

#### Deduplication Strategy

1. **external_id** (preferred) - AutoScout24 listing GUID, enables cross-site deduplication
2. **url** (fallback) - Unique per listing
3. **dedup_hash** - Attribute-based hash for fuzzy matching

```python
def upsert_listing(self, data: ListingCreate) -> tuple[Listing, bool]:
    # Try external_id first for cross-site deduplication
    existing = self.get_listing_by_external_id(data.external_id) if data.external_id else None
    # Fall back to URL-based lookup
    if existing is None:
        existing = self.get_listing_by_url(data.url)
```

---

## 5. Scraping System

### 5.1 Scraper Hierarchy

```
BaseScraper (abstract)
│   - Retry logic (tenacity)
│   - Rate limiting (20 req/min)
│   - Cookie consent handling
│   - Human-like behavior (delays, scrolling)
│
└── AutoScout24BaseScraper
    │   - Shared parsing logic
    │   - JSON-LD extraction (dealer/location)
    │   - Color extraction (dt/dd pairs)
    │   - Options parsing
    │
    ├── AutoScout24DEScraper
    │       - German URL patterns
    │       - German localization
    │
    └── AutoScout24NLScraper
            - Dutch URL patterns
            - Dutch localization
```

### 5.2 Browser Manager

Location: `src/i4_scout/scrapers/browser.py`

#### Features
- **Stealth Mode**: Uses `playwright-stealth` to avoid detection
- **Context Rotation**: Creates new browser context every 10 requests
- **User Agent Rotation**: Cycles through realistic Chrome user agents
- **Locale/Timezone**: Configured for German locale (de-DE, Europe/Berlin)

```python
@dataclass
class BrowserConfig:
    headless: bool = True
    locale: str = "de-DE"
    timezone_id: str = "Europe/Berlin"
    viewport_width: int = 1920
    viewport_height: int = 1080
    rotation_threshold: int = 10  # Rotate context after N requests
```

### 5.3 HTML Cache

Location: `src/i4_scout/scrapers/cache.py`

#### Cache Strategy
| Page Type | TTL | Rationale |
|-----------|-----|-----------|
| Search pages | 1 hour | Listings change frequently |
| Detail pages | 24 hours | Content rarely changes |

```
.cache/
└── html/
    ├── {url_hash}.html
    └── {url_hash}.meta.json  # TTL, timestamp
```

CLI Options:
- `--no-cache`: Disable HTML caching
- `--force-refresh`: Force re-fetch all detail pages

### 5.4 Data Extraction

#### Search Page Extraction
- Listing cards with title, URL, price, mileage
- External ID from data attributes

#### Detail Page Extraction
- **Options List**: Parsed from equipment section
- **Description**: Full vehicle description text
- **JSON-LD**: Structured schema.org data
  - `dealer_name`, `dealer_type` (dealer/private)
  - `location_city`, `location_zip`, `location_country`
- **Colors**: Extracted from dt/dd pairs
  - German: Außenfarbe, Farbe der Innenausstattung, Innenausstattung
  - Dutch: Kleur, Kleur interieur, Materiaal

---

## 6. Matching Engine

Location: `src/i4_scout/matching/`

### 6.1 Pipeline

```
Raw Options
    │
    ▼
┌──────────────────┐
│  Bundle Expander │  Expands "M Sport Package" → individual options
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│   Normalizer     │  German umlauts, case, punctuation
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Option Matcher  │  Exact + substring + description search
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│     Scorer       │  Calculate score and qualification
└──────────────────┘
```

### 6.2 Components

#### Normalizer (`normalizer.py`)
```python
def normalize_text(text: str) -> str:
    # German umlaut normalization
    # "Außenfarbe" → "aussenfarbe"
    # Case normalization, punctuation removal
```

#### Bundle Expander (`bundle_expander.py`)
Expands package options into individual components based on config:
```yaml
nice_to_have:
  - name: M Sport Package
    is_bundle: true
    bundle_contents:
      - M Sport Steering Wheel
      - M Sport Seats
      - M Sport Suspension
```

#### Option Matcher (`option_matcher.py`)
Matching strategies:
1. **Exact match**: Normalized option equals normalized alias
2. **Substring match**: Alias contained within option (min 3 chars)
3. **Description search**: Search title/description for option names and codes

```python
# BMW option codes use word boundary matching
pattern = rf"\b{re.escape(code)}\b"  # e.g., "337", "7A2"
```

#### Scorer (`scorer.py`)
```python
# Score formula
REQUIRED_WEIGHT = 100
NICE_TO_HAVE_WEIGHT = 10

raw_score = (matched_required * 100) + (matched_nice_to_have * 10)
max_score = (total_required * 100) + (total_nice_to_have * 10)
normalized_score = (raw_score / max_score) * 100

# Qualification
is_qualified = (all required matched) AND (no dealbreaker found)
```

---

## 7. Service Layer

Location: `src/i4_scout/services/`

### Services

| Service | Responsibility |
|---------|----------------|
| `ListingService` | Listing CRUD with Pydantic conversion, filtering |
| `ScrapeService` | Orchestrates scraping with browser, matching, persistence |
| `DocumentService` | PDF upload, validation, text extraction, enrichment |
| `NoteService` | Notes CRUD operations |
| `JobService` | Background scrape job management |

### ScrapeService Flow

```python
async def run_scrape(
    source: Source,
    max_pages: int,
    search_filters: SearchFilters | None,
    headless: bool,
    use_cache: bool,
    force_refresh: bool,
    progress_callback: Callable[[ScrapeProgress], None] | None,
) -> ScrapeResult:
    async with browser_context as (browser, page):
        scraper = create_scraper(source, browser)
        for page_num in range(1, max_pages + 1):
            listings = await scraper.scrape_search_page(page, page_num)
            for listing in listings:
                # Skip optimization: check if price unchanged
                if listing_exists_with_same_price(url, price):
                    continue  # Skip detail fetch
                # Fetch and process
                detail = await scraper.scrape_listing_detail(page, url)
                match_result = match_options(detail.options, config)
                scored = calculate_score(match_result, config)
                listing, created = repo.upsert_listing(data)
```

---

## 8. API Layer

Location: `src/i4_scout/api/`

### 8.1 FastAPI Structure

```
api/
├── main.py              # App factory
├── dependencies.py      # Dependency injection
├── schemas.py           # API response models
└── routes/
    ├── listings.py      # /api/listings/*
    ├── documents.py     # /api/listings/{id}/document/*
    ├── notes.py         # /api/listings/{id}/notes/*
    ├── scrape.py        # /api/scrape/*
    ├── config.py        # /api/config/*
    ├── stats.py         # /api/stats
    ├── web.py           # HTML pages (/, /listings, /compare, /scrape)
    └── partials.py      # HTMX partial endpoints (/partials/*)
```

### 8.2 Route Organization

| Prefix | Purpose | Examples |
|--------|---------|----------|
| `/api/` | REST JSON endpoints | GET/POST/DELETE resources |
| `/` | HTML pages | Dashboard, listings, detail |
| `/partials/` | HTMX fragments | Table rows, stats cards |

### 8.3 Dependency Injection

```python
# Type-annotated aliases
DbSession = Annotated[Session, Depends(get_db)]
ListingServiceDep = Annotated[ListingService, Depends(get_listing_service)]
DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]
NoteServiceDep = Annotated[NoteService, Depends(get_note_service)]
OptionsConfigDep = Annotated[OptionsConfig, Depends(get_options_config)]
TemplatesDep = Annotated[Jinja2Templates, Depends(get_templates)]
```

### 8.4 Key API Endpoints

#### Listings
```
GET    /api/listings                    # List with filters
GET    /api/listings/{id}               # Get single listing
DELETE /api/listings/{id}               # Delete listing
PATCH  /api/listings/{id}/issue         # Toggle issue flag
GET    /api/listings/{id}/price-history # Get price history
```

#### Documents
```
POST   /api/listings/{id}/document      # Upload PDF
GET    /api/listings/{id}/document      # Get metadata
GET    /api/listings/{id}/document/download  # Download file
DELETE /api/listings/{id}/document      # Delete document
POST   /api/listings/{id}/document/reprocess # Re-extract options
```

#### Notes
```
GET    /api/listings/{id}/notes         # List notes
POST   /api/listings/{id}/notes         # Add note
DELETE /api/listings/{id}/notes/{note_id}  # Delete note
```

#### Scraping
```
POST   /api/scrape/jobs                 # Start new job
GET    /api/scrape/jobs                 # List recent jobs
GET    /api/scrape/jobs/{id}            # Get job status
```

---

## 9. Web Interface

### 9.1 Technology Stack

| Component | Technology | Size |
|-----------|------------|------|
| CSS Framework | Pico CSS | ~10KB |
| Interactivity | HTMX | ~14KB |
| Templates | Jinja2 | - |
| State | localStorage | - |

### 9.2 Template Organization

```
templates/
├── base.html                    # Layout, nav, scripts
├── macros.html                  # Template utilities
├── pages/
│   ├── dashboard.html           # Dashboard with widgets
│   ├── listings.html            # Listings table with filters
│   ├── listing_detail.html      # Full listing view
│   ├── compare.html             # Side-by-side comparison
│   └── scrape.html              # Scrape control panel
├── partials/
│   ├── listings_table.html      # HTMX fragment
│   ├── listing_detail_content.html
│   ├── recent_qualified.html
│   └── scrape_jobs_list.html
└── components/
    ├── filter_form.html         # Filter controls
    ├── listing_row.html         # Single table row
    ├── listing_card.html        # Card view
    ├── pagination.html          # Page navigation
    ├── stats_cards.html         # Stats display
    ├── compare_bar.html         # Selection bar
    ├── document_section.html    # PDF upload
    ├── notes_section.html       # Notes list
    ├── notes_summary.html       # Notes popover
    ├── options_summary.html     # Options popover
    ├── price_chart.html         # Price history
    ├── photo_gallery.html       # Photo gallery with lightbox
    ├── scrape_form.html         # Scrape job form
    ├── scrape_progress_banner.html  # Global progress banner
    ├── scrape_job_row.html      # Job row for polling
    ├── active_job_status.html   # Active job status card
    ├── market_velocity.html     # Market pulse widget
    ├── price_drops.html         # Price drops widget
    ├── near_miss.html           # Near-miss listings widget
    ├── feature_rarity.html      # Option frequency widget
    └── favorites.html           # User favorites widget
```

### 9.3 HTMX Patterns

#### Form-Triggered Updates
```html
<form hx-get="/partials/listings" hx-target="#listings-table" hx-push-url="true">
    <!-- Filter inputs -->
</form>
```

#### Debounced Search
```html
<input hx-get="/partials/listings"
       hx-trigger="keyup changed delay:500ms"
       hx-target="#listings-table">
```

#### Polling for Job Status
```html
<div hx-get="/partials/scrape/job/{{ job.id }}"
     hx-trigger="every 2s"
     hx-swap="outerHTML">
```

#### URL State Preservation
Filters are preserved in URL query params for bookmarking and sharing.

### 9.4 HTMX Partial Endpoints

All partial endpoints return HTML fragments for dynamic updates.

**Dashboard Widgets (`/partials/`):**
| Endpoint | Purpose | Parameters |
|----------|---------|------------|
| `GET /market-velocity` | Market pulse stats | `days` (default 7) |
| `GET /price-drops` | Listings with price drops | `days` (7), `limit` (5) |
| `GET /near-miss` | High-score unqualified listings | `threshold` (70), `limit` (5) |
| `GET /feature-rarity` | Option frequency stats | `limit` (10) |
| `GET /favorites` | User's favorited listings | `ids` (comma-separated) |

**Listings (`/partials/`):**
| Endpoint | Purpose | Notable Parameters |
|----------|---------|-------------------|
| `GET /listings` | Listings table | All filters, `job_id`, `job_status` |
| `GET /listing/{id}` | Detail content | - |
| `GET /listing/{id}/options-summary` | Options hover popover | - |
| `GET /listing/{id}/notes-summary` | Notes hover popover | - |
| `GET /listing/{id}/price-chart` | Price history chart | - |
| `GET /listing/{id}/gallery` | Photo gallery | - |
| `PATCH /listing/{id}/issue` | Toggle issue flag | `has_issue` (form) |

**Notes (`/partials/listing/{id}/notes`):**
| Endpoint | Purpose |
|----------|---------|
| `GET /` | Notes section |
| `POST /` | Add note (form: `content`) |
| `DELETE /{note_id}` | Delete note |

**Documents (`/partials/listing/{id}/document`):**
| Endpoint | Purpose |
|----------|---------|
| `GET /` | Document section |
| `POST /` | Upload PDF (multipart) |
| `DELETE /` | Delete document |
| `POST /reprocess` | Re-extract options |

**Scrape Jobs (`/partials/scrape/`):**
| Endpoint | Purpose | Polling |
|----------|---------|---------|
| `GET /active` | Global progress banner | 2s when running, 10s idle |
| `GET /active-status` | Detailed job status card | 2s |
| `GET /jobs` | Jobs list | - |
| `GET /job/{id}` | Single job row | 2s when running |

---

## 10. Configuration

### 10.1 Options Configuration

Location: `config/options.yaml`

```yaml
required:
  - name: Laser Light
    aliases:
      - Laserlight
      - BMW Laserlicht
      - "5A2"  # BMW option code
    category: lighting

nice_to_have:
  - name: M Sport Package
    aliases:
      - M Sportpaket
      - M-Sportpakket
    is_bundle: true
    bundle_contents:
      - M Sport Steering Wheel
      - M Sport Seats

dealbreakers:
  - Salvage Title
  - Accident Damage
  - "export only"
```

### 10.2 Search Filters

```yaml
search_filters:
  price_max_eur: 55000
  mileage_max_km: 50000
  year_min: 2023
  year_max: 2025
  countries:
    - D   # Germany
    - NL  # Netherlands
```

AutoScout24 country codes: D, NL, B, A, L, F, I, E, CH

CLI options override config values:
- `--price-max` / `-P`
- `--mileage-max` / `-M`
- `--year-min` / `-Y`
- `--country` / `-C` (repeatable)

---

## 11. CLI

Location: `src/i4_scout/cli.py`

### Commands

| Command | Purpose |
|---------|---------|
| `init-database` | Create database schema |
| `scrape` | Run scraping job |
| `list` | List listings with filters |
| `show` | Show single listing |
| `export` | Export to CSV/JSON |
| `recalculate-scores` | Recalculate match scores |
| `enrich` | PDF enrichment |
| `serve` | Start API server |

### Common Options

```bash
# Scrape with filters
i4-scout scrape autoscout24_de --max-pages 5 --price-max 45000 --year-min 2024

# Force refresh all detail pages
i4-scout scrape autoscout24_de --force-refresh

# Disable caching
i4-scout scrape autoscout24_de --no-cache

# JSON output for scripting
i4-scout list --qualified --json
i4-scout show 42 --json

# Start API server
i4-scout serve --host 0.0.0.0 --port 8080 --reload
```

---

## 12. Key Design Decisions

### Deduplication Strategy
- **external_id** (preferred): AutoScout24's GUID enables cross-site deduplication (same car on .de and .nl)
- **URL** (fallback): Unique within source
- **dedup_hash**: SHA256 of normalized attributes for fuzzy matching

### Option Source Tracking
Options are tracked by source (`scrape` vs `pdf`):
```python
# When re-scraping, only clear scrape-sourced options
repo.clear_listing_options(listing.id, source="scrape")
# PDF-sourced options persist across re-scrapes
```

### Price History
- Full audit trail maintained in `price_history` table
- Initial price recorded on listing creation
- Changes detected during upsert operations
- Used for skip optimization (no change = skip detail fetch)

### Performance Optimizations
1. **Skip Unchanged**: Check if listing exists with same price before fetching details
2. **HTML Caching**: File-based cache with TTL (1h search, 24h detail)
3. **Eager Loading**: SQLAlchemy joinedload for related entities
4. **Context Rotation**: Fresh browser context every 10 requests

### Resilience Patterns
1. **Retry Decorators**: Exponential backoff for SQLite locks
2. **Fallback Parsing**: Multiple strategies for extracting data
3. **Error Isolation**: Page-level errors don't abort entire scrape
4. **Rate Limiting**: 20 requests/minute to avoid detection

---

## 13. File Structure

```
i4-scout/
├── alembic/                  # Database migrations
│   ├── env.py
│   └── versions/            # Migration scripts
├── config/
│   └── options.yaml         # Options configuration
├── data/
│   ├── i4_scout.db          # SQLite database
│   └── documents/           # Uploaded PDFs
├── docs/                    # Documentation
├── src/i4_scout/
│   ├── __init__.py
│   ├── cli.py               # Typer CLI
│   ├── config.py            # Config loading
│   ├── api/
│   │   ├── main.py          # FastAPI app
│   │   ├── dependencies.py  # DI configuration
│   │   ├── schemas.py       # API models
│   │   ├── routes/          # Endpoint handlers
│   │   └── templates/       # Jinja2 templates
│   ├── database/
│   │   ├── engine.py        # SQLAlchemy engine
│   │   └── repository.py    # Repository classes
│   ├── export/
│   │   ├── csv_exporter.py  # CSV export
│   │   └── json_exporter.py # JSON export
│   ├── matching/
│   │   ├── normalizer.py
│   │   ├── bundle_expander.py
│   │   ├── option_matcher.py
│   │   └── scorer.py
│   ├── models/
│   │   ├── pydantic_models.py
│   │   └── db_models.py
│   ├── scrapers/
│   │   ├── browser.py       # Playwright browser manager
│   │   ├── cache.py         # HTML cache with TTL
│   │   ├── base.py          # Abstract base scraper
│   │   ├── autoscout24_base.py
│   │   ├── autoscout24_de.py
│   │   └── autoscout24_nl.py
│   └── services/
│       ├── listing_service.py
│       ├── scrape_service.py
│       ├── document_service.py
│       ├── note_service.py
│       └── job_service.py
├── tests/
│   ├── fixtures/            # HTML fixtures
│   ├── unit/                # Unit tests
│   └── integration/         # Integration tests
├── .cache/
│   └── html/                # HTML cache files
├── pyproject.toml
└── README.md
```
