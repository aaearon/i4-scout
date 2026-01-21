# Web Interface Implementation Context

**Purpose:** This document captures the as-is state of the i4-scout codebase to assist LLMs in future sessions implementing the web interface. Read this before starting implementation work.

**Last Updated:** 2026-01-21

---

## 1. Project Structure

```
src/i4_scout/
├── __init__.py                    # Version: 0.1.0
├── cli.py                         # Typer CLI - NEEDS REFACTORING
├── config.py                      # YAML config loading
├── database/
│   ├── __init__.py
│   ├── engine.py                  # SQLAlchemy engine setup
│   └── repository.py              # ListingRepository with retry logic
├── export/
│   ├── csv_exporter.py
│   └── json_exporter.py           # Has duplicate listing_to_dict()
├── matching/
│   ├── bundle_expander.py         # Package option expansion
│   ├── normalizer.py              # Text normalization (German chars)
│   ├── option_matcher.py          # Pure function - reusable
│   └── scorer.py                  # Pure function - reusable
├── models/
│   ├── db_models.py               # SQLAlchemy ORM models
│   └── pydantic_models.py         # Validation models
└── scrapers/
    ├── autoscout24_base.py        # Shared AS24 parsing
    ├── autoscout24_de.py          # German site scraper
    ├── autoscout24_nl.py          # Dutch site scraper
    ├── base.py                    # Abstract base with caching
    ├── browser.py                 # Playwright browser management
    └── cache.py                   # HTML caching (file-based)
```

---

## 2. Key Files for Web Interface

### 2.1 Database Layer

#### `src/i4_scout/database/engine.py`

**Current Implementation:**
```python
# Lines 1-35 (approximate)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

DEFAULT_DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "i4_scout.db"

_engine = None
_SessionLocal = None

def get_engine(db_path: Path | None = None, echo: bool = False):
    global _engine
    if _engine is None:
        path = db_path or DEFAULT_DB_PATH
        _engine = create_engine(
            f"sqlite:///{path}",
            connect_args={"check_same_thread": False, "timeout": 30},
            echo=echo,
        )
    return _engine

@contextmanager
def get_session() -> Generator[Session, None, None]:
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

**Web Interface Changes Needed:**
- Add `DATABASE_URL` environment variable support
- Add connection pooling configuration
- Enable WAL mode for SQLite
- Consider async session factory for FastAPI

#### `src/i4_scout/database/repository.py`

**Key Classes/Functions:**
- `with_db_retry` decorator (lines 33-55) - Retries on SQLite lock errors
- `ListingRepository` class (lines 58-574) - All CRUD operations

**Important Methods for Web API:**
```python
# These methods are directly usable by web API
def get_listing_by_id(self, listing_id: int) -> Listing | None
def get_listing_by_url(self, url: str) -> Listing | None
def listing_exists_with_price(self, url: str, price: int | None) -> bool
def get_listings(self, source, qualified_only, min_score, limit, offset) -> list[Listing]
def count_listings(self, source, qualified_only) -> int
def get_price_history(self, listing_id: int) -> list[PriceHistory]
def delete_listing(self, listing_id: int) -> bool
```

**Session Injection Pattern:**
```python
# Current usage (context manager)
with get_session() as session:
    repo = ListingRepository(session)
    listings = repo.get_listings()

# Web API should use dependency injection instead
```

### 2.2 Models

#### `src/i4_scout/models/db_models.py`

**Tables:**
```python
class Listing(Base):
    __tablename__ = "listings"
    id: int (primary key)
    source: str (enum value)
    external_id: str | None
    url: str (unique)
    title: str
    price: int | None (cents)
    mileage_km: int | None
    year: int | None
    first_registration: str | None
    vin: str | None
    location_city, location_zip, location_country: str | None
    dealer_name, dealer_type: str | None
    description: str | None
    raw_options_text: str | None
    photo_urls: JSON | None
    match_score: float
    is_qualified: bool
    dedup_hash: str
    first_seen_at, last_seen_at: datetime

    # Relationships
    options: list[ListingOption]  # via listing_options table
    price_history: list[PriceHistory]

    # Property
    @property
    def matched_options(self) -> list[str]:
        return [lo.option.canonical_name for lo in self.options]

class Option(Base):
    __tablename__ = "options"
    id, canonical_name, display_name, category, is_bundle

class ListingOption(Base):
    __tablename__ = "listing_options"
    listing_id, option_id, raw_text, confidence

class PriceHistory(Base):
    __tablename__ = "price_history"
    id, listing_id, price, recorded_at

class ScrapeSession(Base):
    __tablename__ = "scrape_sessions"
    id, source, started_at, completed_at, status
    total_found, new_listings, updated_listings, errors
```

#### `src/i4_scout/models/pydantic_models.py`

**Existing Models:**
```python
class Source(str, Enum):
    AUTOSCOUT24_DE = "autoscout24_de"
    AUTOSCOUT24_NL = "autoscout24_nl"

class ListingCreate(BaseModel):
    # Used for creating/upserting listings
    source: Source
    external_id: str | None = None
    url: str
    title: str = ""
    price: int | None = None
    # ... all listing fields

class ScrapedListing(BaseModel):
    # Output from detail page parsing
    options_list: list[str] = []
    description: str | None = None

class SearchFilters(BaseModel):
    price_max_eur: int | None = None
    mileage_max_km: int | None = None
    year_min: int | None = None
    year_max: int | None = None
    countries: list[str] | None = None

class OptionsConfig(BaseModel):
    required: list[OptionDefinition]
    nice_to_have: list[OptionDefinition]
    dealbreakers: list[OptionDefinition]

class MatchResult(BaseModel):
    matched_required: list[str]
    matched_nice_to_have: list[str]
    matched_dealbreakers: list[str]
    missing_required: list[str]

class ScoredResult(BaseModel):
    score: float
    is_qualified: bool
    match_result: MatchResult
```

**Models to Add for Web API:**
```python
# These need to be created for API responses
class ListingRead(BaseModel):
    """API response model for listing data"""
    id: int
    source: Source
    url: str
    title: str
    price: int | None
    mileage_km: int | None
    # ... etc
    matched_options: list[str]

    model_config = ConfigDict(from_attributes=True)

class ListingList(BaseModel):
    """Paginated listing response"""
    listings: list[ListingRead]
    total: int
    limit: int
    offset: int

class ScrapeJobCreate(BaseModel):
    source: Source
    max_pages: int = 50
    filters: SearchFilters | None = None

class ScrapeJobStatus(BaseModel):
    id: int
    status: str  # pending, running, completed, failed
    progress: ScrapeProgress | None
    result: ScrapeResult | None
```

### 2.3 CLI (Code to Extract)

#### `src/i4_scout/cli.py`

**Lines 35-59: `listing_to_dict()` - DUPLICATE CODE**
```python
def listing_to_dict(listing: Any) -> dict[str, Any]:
    """Convert a Listing ORM object to a JSON-serializable dict."""
    return {
        "id": listing.id,
        "source": listing.source.value if listing.source else None,
        "external_id": listing.external_id,
        "url": listing.url,
        "title": listing.title,
        "price": listing.price,
        "mileage_km": listing.mileage_km,
        # ... more fields
        "matched_options": listing.matched_options,
        "first_seen_at": listing.first_seen_at.isoformat() if listing.first_seen_at else None,
        "last_seen_at": listing.last_seen_at.isoformat() if listing.last_seen_at else None,
    }
```
**Action:** Replace with `ListingRead.model_validate(listing).model_dump()`

**Lines 127-299: `run_scrape()` - EXTRACT TO SERVICE**

This function contains the core scraping orchestration logic that should be extracted to `ScrapeService`. Key sections:

```python
async def run_scrape(
    source: Source,
    max_pages: int,
    headless: bool,
    config_path: Path | None,
    quiet: bool = False,
    search_filters: SearchFilters | None = None,
    use_cache: bool = True,
) -> dict[str, int]:
    # Lines 150-162: Setup
    options_config = load_options_config(config_path)
    browser_config = BrowserConfig(headless=headless)
    scraper_class = get_scraper_class(source)

    # Lines 164-168: Browser context
    async with BrowserManager(browser_config) as browser:
        scraper = scraper_class(browser)
        page = await browser.get_page()

        # Lines 169-291: Main scraping loop
        for page_num in range(1, max_pages + 1):
            # Fetch search page
            listings_data = await scraper.scrape_search_page(...)

            # Process each listing
            with get_session() as session:
                repo = ListingRepository(session)
                for listing_data in listings_data:
                    # Skip unchanged check (lines 197-209)
                    if repo.listing_exists_with_price(url, price):
                        skipped_count += 1
                        continue

                    # Fetch detail page (lines 220-229)
                    detail = await scraper.scrape_listing_detail(page, url)

                    # Match options (lines 231-232)
                    match_result = match_options(options_list, options_config, searchable_text)
                    scored_result = calculate_score(match_result, options_config)

                    # Save to database (lines 234-256)
                    listing, created = repo.upsert_listing(create_data)

    # Lines 293-299: Return results
    return {
        "total_found": total_found,
        "new_listings": new_count,
        "updated_listings": updated_count,
        "skipped_unchanged": skipped_count,
        "fetched_details": fetched_count,
    }
```

**Lines 362-371: Filter Merging - MOVE TO CONFIG**
```python
# Currently in scrape() command
search_filters = SearchFilters(
    price_max_eur=price_max if price_max is not None else config_filters.price_max_eur,
    mileage_max_km=mileage_max if mileage_max is not None else config_filters.mileage_max_km,
    year_min=year_min if year_min is not None else config_filters.year_min,
    year_max=config_filters.year_max,
    countries=country if country else config_filters.countries,
)
```
**Action:** Move to `config.py` as `merge_search_filters(config_filters, overrides)`

### 2.4 Matching Engine (Reusable As-Is)

#### `src/i4_scout/matching/option_matcher.py`

**Pure Function - No Changes Needed:**
```python
def match_options(
    options_list: list[str],
    config: OptionsConfig,
    searchable_text: str = "",
) -> MatchResult:
    """Match listing options against configuration."""
    # Returns MatchResult with matched/missing options
```

#### `src/i4_scout/matching/scorer.py`

**Pure Function - No Changes Needed:**
```python
def calculate_score(match_result: MatchResult, config: OptionsConfig) -> ScoredResult:
    """Calculate match score and qualification status."""
    # Returns ScoredResult with score and is_qualified
```

### 2.5 Scrapers

#### `src/i4_scout/scrapers/base.py`

**Key Methods:**
```python
class BaseScraper(ABC):
    async def scrape_search_page(
        self, page: Page, page_num: int = 1,
        filters: SearchFilters | None = None,
        use_cache: bool = True,
    ) -> list[dict[str, Any]]

    async def scrape_listing_detail(
        self, page: Page, url: str,
        use_cache: bool = True,
    ) -> ScrapedListing
```

**Browser Management:**
```python
# BrowserManager handles Playwright lifecycle
async with BrowserManager(BrowserConfig(headless=True)) as browser:
    scraper = AutoScout24DEScraper(browser)
    page = await browser.get_page()
    # ... use scraper
```

#### `src/i4_scout/scrapers/cache.py`

**Cache Location:** `.cache/html/`
**TTLs:** Search pages = 1 hour, Detail pages = 24 hours

```python
class HTMLCache:
    SEARCH_TTL_SECONDS = 3600   # 1 hour
    DETAIL_TTL_SECONDS = 86400  # 24 hours

    def get(self, url: str) -> CacheEntry | None
    def set(self, url: str, html: str) -> None
    def clear(self) -> int
    def stats(self) -> dict
```

---

## 3. Configuration

### 3.1 Options Config Location

**File:** `config/options.yaml`

**Structure:**
```yaml
required:
  - name: "Head-Up Display"
    aliases: ["HUD", "Head Up Display", "Heads-up Display"]
    bmw_code: "5AT"

nice_to_have:
  - name: "Harman Kardon"
    aliases: ["Harman/Kardon", "HK Sound"]

dealbreakers:
  - name: "Comfort Access"
    aliases: ["Keyless Entry"]

search_filters:
  price_max_eur: 55000
  mileage_max_km: 50000
  year_min: 2023
  countries: ["D", "NL"]
```

### 3.2 Config Loading

**File:** `src/i4_scout/config.py`

```python
def load_options_config(config_path: Path | None = None) -> OptionsConfig:
    """Load options configuration from YAML file."""

def load_search_filters(config_path: Path | None = None) -> SearchFilters:
    """Load search filters from config file."""
```

---

## 4. Dependencies

### 4.1 Current Dependencies (pyproject.toml)

```toml
dependencies = [
    "playwright>=1.40.0",
    "playwright-stealth>=1.0.0",
    "sqlalchemy>=2.0.0",
    "aiosqlite>=0.19.0",      # For async SQLite (not currently used)
    "typer>=0.9.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "pyyaml>=6.0",
    "tenacity>=8.2.0",
    "rich>=13.0.0",
    "beautifulsoup4>=4.12.0",
    "lxml>=5.0.0",
]
```

### 4.2 Dependencies to Add for Web Interface

```toml
# Add to pyproject.toml
dependencies = [
    # ... existing
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "python-multipart>=0.0.6",  # For form data
]

[project.optional-dependencies]
dev = [
    # ... existing
    "httpx>=0.26.0",  # For testing FastAPI
]
```

---

## 5. Testing Patterns

### 5.1 Test Structure

```
tests/
├── integration/
│   ├── test_browser.py        # Playwright browser tests
│   ├── test_cli.py            # CLI command tests (CliRunner)
│   └── test_repository.py     # Database integration tests
└── unit/
    ├── test_autoscout24_parsing.py
    ├── test_base_scraper.py
    ├── test_bundle_expander.py
    ├── test_config.py
    ├── test_normalizer.py
    ├── test_option_matcher.py
    ├── test_pydantic_models.py
    ├── test_repository_retry.py
    ├── test_scorer.py
    └── test_scrape_optimizations.py
```

### 5.2 Database Test Pattern

```python
@pytest.fixture
def db_session():
    """Create an in-memory database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()

@pytest.fixture
def repository(db_session):
    return ListingRepository(db_session)
```

### 5.3 CLI Test Pattern

```python
@pytest.fixture
def runner():
    return CliRunner()

@pytest.fixture
def test_db(tmp_path):
    reset_engine()
    db_path = tmp_path / "test.db"
    os.environ["I4_SCOUT_DB_PATH"] = str(db_path)
    init_db(db_path)
    yield db_path
    reset_engine()
    del os.environ["I4_SCOUT_DB_PATH"]

def test_list_command(runner, populated_db):
    result = runner.invoke(app, ["list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "listings" in data
```

### 5.4 Web API Test Pattern (To Implement)

```python
from fastapi.testclient import TestClient
from i4_scout.api.main import create_app

@pytest.fixture
def client(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)

def test_list_listings(client, populated_db):
    response = client.get("/api/listings")
    assert response.status_code == 200
    data = response.json()
    assert "listings" in data
    assert "total" in data
```

---

## 6. Gotchas and Non-Obvious Details

### 6.1 Source Enum Handling

The `Source` enum value is stored as a string in the database:
```python
# In db_models.py
source = Column(String, nullable=False)  # Stores "autoscout24_de"

# When querying
listing.source  # Returns string "autoscout24_de", not Source enum

# In pydantic models
source: Source  # Expects/validates as enum

# Conversion needed in listing_to_dict:
"source": listing.source.value if listing.source else None  # WRONG - source is already string
"source": listing.source  # Correct for DB model
```

### 6.2 Price Storage

Prices are stored in **EUR as integers** (not cents despite comments):
```python
# Stored as: 45000 (meaning 45,000 EUR)
# NOT stored as: 4500000 (cents)
```

### 6.3 Matched Options Property

The `matched_options` property on Listing requires loaded relationships:
```python
# This works after session.refresh(listing) or with joinedload
listing.matched_options  # Returns ["head_up_display", "parking_assistant"]

# This fails with DetachedInstanceError if accessed outside session
```

### 6.4 Async Context

Scrapers are async but repository is sync:
```python
# In run_scrape() - mixing async scraper with sync DB
async with BrowserManager(...) as browser:
    # ... async scraping
    with get_session() as session:  # Sync context manager
        repo = ListingRepository(session)  # Sync operations
```

For web API with background tasks, this pattern still works. For full async, would need:
- `async_sessionmaker` from SQLAlchemy
- Async repository methods

### 6.5 Global Engine State

```python
# engine.py uses module-level globals
_engine = None
_SessionLocal = None

# reset_engine() must be called in tests to avoid cross-test contamination
def reset_engine():
    global _engine, _SessionLocal
    if _engine:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
```

### 6.6 Environment Variable for DB Path

Currently supported but not well documented:
```python
# In tests
os.environ["I4_SCOUT_DB_PATH"] = str(db_path)

# Should add DATABASE_URL support for web deployment
```

---

## 7. Implementation Checklist

### Phase 1: Service Layer
- [ ] Create `src/i4_scout/services/__init__.py`
- [ ] Create `src/i4_scout/services/listing_service.py`
- [ ] Create `src/i4_scout/services/scrape_service.py`
- [ ] Create `src/i4_scout/services/stats_service.py`
- [ ] Move `listing_to_dict()` logic to `ListingRead` pydantic model
- [ ] Move filter merging to `config.py`
- [ ] Update `cli.py` to use services
- [ ] Verify all CLI tests still pass

### Phase 2: Database Improvements
- [ ] Add `DATABASE_URL` environment variable support
- [ ] Add connection pooling configuration
- [ ] Enable WAL mode for SQLite
- [ ] Add `scrape_jobs` table for job tracking
- [ ] Create migration script (if using alembic)

### Phase 3: FastAPI Foundation
- [ ] Create `src/i4_scout/api/__init__.py`
- [ ] Create `src/i4_scout/api/main.py` (app factory)
- [ ] Create `src/i4_scout/api/dependencies.py`
- [ ] Create `src/i4_scout/api/schemas.py` (response models)
- [ ] Create `src/i4_scout/api/routes/listings.py`
- [ ] Create `src/i4_scout/api/routes/config.py`
- [ ] Create `src/i4_scout/api/routes/stats.py`
- [ ] Create `src/i4_scout/api/routes/export.py`
- [ ] Add API tests
- [ ] Add `i4-scout serve` CLI command

### Phase 4: Background Scraping
- [ ] Create `src/i4_scout/api/routes/scrape.py`
- [ ] Implement job creation endpoint
- [ ] Implement background task execution
- [ ] Implement job status endpoint
- [ ] Add job cleanup/expiration

---

## 8. Quick Reference Commands

```bash
# Activate environment
source .venv/bin/activate

# Run tests
pytest tests/ -v

# Lint
ruff check src/ tests/

# Type check
mypy src/

# Current CLI
i4-scout scrape autoscout24_de --max-pages 5
i4-scout list --qualified --json
i4-scout show 1 --json

# Future web server (to implement)
i4-scout serve --host 0.0.0.0 --port 8000
# or
uvicorn i4_scout.api.main:app --reload
```
