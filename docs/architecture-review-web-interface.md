# Architecture Review: Web Interface Implementation Plan

**Date:** 2026-01-21
**Project:** i4-scout
**Reviewer:** Architecture Review

## Executive Summary

The i4-scout project has a reasonably well-structured architecture that can support a web interface with moderate refactoring. The main work involves extracting a **service layer** from the CLI and adding a **FastAPI-based API layer**. The existing repository pattern, Pydantic models, and async scraping infrastructure provide a solid foundation.

---

## 1. Current Architecture Analysis

### 1.1 Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Current Data Flow                                  │
└─────────────────────────────────────────────────────────────────────────────┘

User (CLI)
    │
    ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   cli.py    │────▶│  Scraper     │────▶│  HTML Parser    │
│  (Typer)    │     │  (Playwright)│     │  (BeautifulSoup)│
└─────────────┘     └──────────────┘     └─────────────────┘
    │                                            │
    │                                            ▼
    │                                    ┌─────────────────┐
    │                                    │ option_matcher  │
    │                                    │    + scorer     │
    │                                    └─────────────────┘
    │                                            │
    ▼                                            ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Repository │◀────│  Session     │◀────│ ListingCreate   │
│  (CRUD)     │     │  (SQLAlchemy)│     │ (Pydantic)      │
└─────────────┘     └──────────────┘     └─────────────────┘
    │
    ▼
┌─────────────┐
│   SQLite    │
│  Database   │
└─────────────┘
```

### 1.2 Module Structure

| Module | Purpose | Web Reusability |
|--------|---------|-----------------|
| `database/repository.py` | CRUD operations with retry logic | High - needs session injection |
| `database/engine.py` | Engine/session management | Medium - needs async support |
| `models/db_models.py` | SQLAlchemy ORM models | High - unchanged |
| `models/pydantic_models.py` | Data validation models | High - add response models |
| `matching/option_matcher.py` | Option matching logic | High - pure function |
| `matching/scorer.py` | Score calculation | High - pure function |
| `scrapers/*.py` | Web scraping | High - async already |
| `config.py` | YAML config loading | High - unchanged |
| `cli.py` | CLI presentation | Low - extract service layer |
| `export/*.py` | CSV/JSON export | High - unchanged |

### 1.3 Database Schema

```
Tables:
├── listings (main entity)
│   ├── id, source, external_id, url (unique)
│   ├── title, price, mileage_km, year, first_registration
│   ├── location_*, dealer_*, description
│   ├── match_score, is_qualified, dedup_hash
│   └── first_seen_at, last_seen_at
│
├── options (canonical option names)
│   └── id, canonical_name, display_name, category, is_bundle
│
├── listing_options (many-to-many)
│   └── listing_id, option_id, raw_text, confidence
│
├── price_history (price tracking)
│   └── listing_id, price, recorded_at
│
└── scrape_sessions (scrape job metadata)
    └── id, source, started_at, completed_at, status, counts, errors
```

**Assessment:** Schema is web-ready. Consider adding indexes on `(source, is_qualified)` for filtered queries.

---

## 2. Separation of Concerns

### 2.1 Well-Separated Components

| Component | Location | Responsibility |
|-----------|----------|----------------|
| Repository | `database/repository.py` | Data access abstraction |
| ORM Models | `models/db_models.py` | Database schema |
| Pydantic Models | `models/pydantic_models.py` | Validation & serialization |
| Option Matcher | `matching/option_matcher.py` | Pure function, no state |
| Scorer | `matching/scorer.py` | Pure function, no state |
| Config Loader | `config.py` | YAML parsing |

### 2.2 Tight Couplings to Address

#### Issue 1: `run_scrape()` Contains Business Logic

**Location:** `cli.py` lines 127-299 (163 lines)

**Problem:** The scraping orchestration logic is embedded in the CLI command, mixing:
- Browser lifecycle management
- Pagination logic
- Progress reporting (Rich console)
- Detail page fetch optimization
- Option matching and scoring
- Database persistence

**Solution:** Extract to `ScrapeService` class with callback-based progress reporting.

#### Issue 2: Duplicate `listing_to_dict()`

**Locations:**
- `cli.py` lines 35-59
- `export/json_exporter.py` lines 10-45

**Solution:** Use Pydantic model's `.model_dump()` or create a single utility in models.

#### Issue 3: Search Filter Merging in CLI

**Location:** `cli.py` lines 362-371

**Problem:** CLI parameter merging with config is presentation logic mixed with business logic.

**Solution:** Move to `config.py` as `merge_search_filters(config, overrides)`.

---

## 3. API Layer Considerations

### 3.1 Framework Recommendation: FastAPI

**Rationale:**
- Native async support matches existing async scrapers
- Pydantic integration (project already uses Pydantic)
- Automatic OpenAPI/Swagger documentation
- Dependency injection for clean session management
- Built-in background tasks for async scraping
- Type hints align with project's typing style

### 3.2 Proposed API Endpoints

#### Listings (Read Operations)

```
GET  /api/listings                    # List with pagination & filters
     ?qualified=true
     &min_score=70
     &source=autoscout24_de
     &limit=20&offset=0

GET  /api/listings/{id}               # Single listing details
GET  /api/listings/{id}/price-history # Price change history
DELETE /api/listings/{id}             # Remove listing
```

#### Scraping (Background Jobs)

```
POST /api/scrape/jobs                 # Start scrape job (returns job_id)
     {
       "source": "autoscout24_de",
       "max_pages": 10,
       "filters": { "price_max_eur": 50000 }
     }

GET  /api/scrape/jobs                 # List recent jobs
GET  /api/scrape/jobs/{id}            # Job status and progress
```

#### Configuration

```
GET  /api/config/options              # Current options config
GET  /api/config/filters              # Default search filters
```

#### Statistics & Export

```
GET  /api/stats                       # Overview statistics
GET  /api/export/csv?qualified=true   # CSV download
GET  /api/export/json?qualified=true  # JSON download
```

### 3.3 Async Scraping Strategy

**Problem:** Scraping takes minutes and cannot block HTTP requests.

**Solution Options:**

| Option | Complexity | Scalability | Recommendation |
|--------|------------|-------------|----------------|
| FastAPI BackgroundTasks | Low | Single process | MVP/Personal use |
| ARQ (async Redis queue) | Medium | Multi-process | Small teams |
| Celery + Redis | High | Distributed | Production |

**Recommended MVP Approach:**

```python
# POST /api/scrape/jobs
@router.post("/jobs")
async def start_scrape(
    request: ScrapeRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    job = create_scrape_job(session, request.source)
    background_tasks.add_task(run_scrape_job, job.id, request)
    return {"job_id": job.id, "status": "pending"}
```

**Progress Updates:**
- Polling: `GET /api/scrape/jobs/{id}` every 2-5 seconds
- WebSocket: Optional enhancement for real-time updates

---

## 4. Database Considerations

### 4.1 SQLite Limitations for Web

| Issue | Current State | Impact |
|-------|---------------|--------|
| Write locking | 30s timeout + retry logic | Concurrent scrapes may conflict |
| No pooling | New connection per session | Acceptable for low traffic |
| Single file | `data/i4_scout.db` | Cannot scale horizontally |

### 4.2 Recommendations

**For Personal/Development Use:**
- Keep SQLite
- Add proper connection pooling
- Ensure WAL mode for better concurrent reads

```python
# engine.py enhancement
engine = create_engine(
    f"sqlite:///{db_path}",
    connect_args={
        "check_same_thread": False,
        "timeout": 30,
    },
    pool_size=5,
    pool_recycle=3600,
)
# Enable WAL mode
with engine.connect() as conn:
    conn.execute(text("PRAGMA journal_mode=WAL"))
```

**For Production/Multi-user:**
- Migrate to PostgreSQL
- SQLAlchemy makes this a connection string change
- No schema changes required

```python
# Support both SQLite and PostgreSQL
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")
engine = create_engine(DATABASE_URL, pool_size=10)
```

### 4.3 Session Management for Web

**Current (CLI):**
```python
with get_session() as session:
    repo = ListingRepository(session)
    # use repo
```

**Web (FastAPI Dependency):**
```python
def get_db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

@router.get("/listings")
async def list_listings(session: Session = Depends(get_db_session)):
    repo = ListingRepository(session)
    return repo.get_listings()
```

---

## 5. Recommended Architecture

### 5.1 Target Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           Presentation Layer                                │
├────────────────────────────┬───────────────────────────────────────────────┤
│       CLI (Typer)          │            Web API (FastAPI)                  │
│    src/i4_scout/cli.py     │         src/i4_scout/api/                     │
│                            │           ├── main.py                         │
│                            │           ├── dependencies.py                 │
│                            │           └── routes/                         │
│                            │               ├── listings.py                 │
│                            │               ├── scrape.py                   │
│                            │               └── stats.py                    │
└────────────────────────────┴───────────────────────────────────────────────┘
                                          │
                                          ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                           Service Layer (NEW)                               │
│                      src/i4_scout/services/                                 │
│                        ├── __init__.py                                      │
│                        ├── listing_service.py (query, filter, serialize)   │
│                        ├── scrape_service.py  (orchestration, progress)    │
│                        └── stats_service.py   (aggregations)               │
└────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                           Core Layer (EXISTS)                               │
├──────────────────────────────┬─────────────────────────────────────────────┤
│      Matching Engine         │           Repository Layer                   │
│      matching/               │           database/repository.py             │
│       ├── option_matcher.py  │                                              │
│       ├── scorer.py          │                                              │
│       └── normalizer.py      │                                              │
├──────────────────────────────┼─────────────────────────────────────────────┤
│      Scrapers                │           Configuration                      │
│      scrapers/               │           config.py                          │
│       ├── base.py            │                                              │
│       ├── autoscout24_*.py   │                                              │
│       └── browser.py         │                                              │
└──────────────────────────────┴─────────────────────────────────────────────┘
                                          │
                                          ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                           Data Layer (EXISTS)                               │
│                 database/engine.py + models/db_models.py                    │
│                            SQLite / PostgreSQL                              │
└────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 New Files to Create

```
src/i4_scout/
├── services/
│   ├── __init__.py
│   ├── listing_service.py      # Listing queries and serialization
│   ├── scrape_service.py       # Scraping orchestration (from CLI)
│   └── stats_service.py        # Statistics and aggregations
│
├── api/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app factory
│   ├── dependencies.py         # Session injection, auth (future)
│   ├── schemas.py              # API request/response models
│   └── routes/
│       ├── __init__.py
│       ├── listings.py         # /api/listings/*
│       ├── scrape.py           # /api/scrape/*
│       ├── config.py           # /api/config/*
│       └── stats.py            # /api/stats
```

### 5.3 Files Requiring Modification

| File | Change | Effort |
|------|--------|--------|
| `cli.py` | Extract `run_scrape()` to service, use services | Medium |
| `engine.py` | Add async engine, pooling config | Low |
| `pydantic_models.py` | Add API response models | Low |
| `config.py` | Add `merge_search_filters()` | Low |
| `json_exporter.py` | Remove duplicate `listing_to_dict()` | Low |
| `repository.py` | Minor: ensure session can be injected | Low |

---

## 6. Phased Implementation Plan

### Phase 1: Service Layer Extraction (3-4 days)

**Goal:** Extract reusable business logic from CLI without breaking existing functionality.

**Tasks:**
1. Create `services/scrape_service.py`
   - Extract `run_scrape()` logic from `cli.py`
   - Add progress callback parameter
   - Return structured result object

2. Create `services/listing_service.py`
   - Unified `listing_to_dict()` method
   - Higher-level query methods

3. Update `cli.py` to use services
   - Validates extraction is correct
   - CLI continues to work unchanged

4. Add filter merging to `config.py`

**Deliverable:** CLI works using service layer; all tests pass.

### Phase 2: Database Improvements (1-2 days)

**Goal:** Prepare database layer for concurrent web access.

**Tasks:**
1. Add connection pooling configuration
2. Enable SQLite WAL mode
3. Add `DATABASE_URL` environment variable support
4. Add async session support (optional, for future)
5. Add `scrape_jobs` table for background job tracking

**Deliverable:** Database supports concurrent reads and configurable backends.

### Phase 3: FastAPI Foundation (3-4 days)

**Goal:** Implement read-only API endpoints.

**Tasks:**
1. Create FastAPI app with proper project structure
2. Implement dependency injection for sessions
3. Create API schemas (Pydantic response models)
4. Implement listing endpoints (list, get, delete)
5. Implement config endpoints
6. Implement stats endpoint
7. Implement export endpoints
8. Add OpenAPI documentation customization

**Deliverable:** Read-only API fully functional.

### Phase 4: Background Scraping (2-3 days)

**Goal:** Enable scraping via API with job tracking.

**Tasks:**
1. Add scrape job model and repository methods
2. Implement `POST /api/scrape/jobs` endpoint
3. Implement background task execution
4. Implement job status endpoint
5. Optional: Add WebSocket for real-time progress

**Deliverable:** Full API including async scraping.

### Phase 5: Web UI (Future)

**Options:**
- Server-side rendering with Jinja2 templates
- SPA with React/Vue (separate repo)
- HTMX for progressive enhancement

---

## 7. Summary of Recommendations

### Immediate Actions (Low Risk)

1. **Extract service layer** - This is the most valuable refactoring regardless of web UI
2. **Add `DATABASE_URL` support** - Easy to do, enables PostgreSQL later
3. **Remove duplicate code** - Consolidate `listing_to_dict()` functions

### Short-term (Medium Risk)

4. **Create FastAPI API layer** - Start with read-only endpoints
5. **Add connection pooling** - Required for concurrent access
6. **Implement background scraping** - Use FastAPI BackgroundTasks initially

### Long-term (Higher Risk)

7. **Migrate to PostgreSQL** - Only if multi-user or scaling needed
8. **Add task queue** - Celery/ARQ if background jobs need reliability
9. **WebSocket progress** - Nice-to-have for real-time updates

---

## 8. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| SQLite contention during concurrent scrapes | Medium | Medium | Use retry logic (exists), limit concurrent scrapes |
| Scraping job fails mid-way | Medium | Low | Store progress, allow resume |
| Browser resource leaks | Low | Medium | Proper cleanup in background tasks |
| API breaking changes | Low | Medium | Version API endpoints |

---

## Appendix A: Example Service Layer Code

### ScrapeService (extracted from CLI)

```python
# src/i4_scout/services/scrape_service.py
from dataclasses import dataclass
from typing import Callable, Protocol

@dataclass
class ScrapeProgress:
    page: int
    total_pages: int
    listings_found: int
    new_count: int
    updated_count: int
    current_listing: str | None = None

class ProgressCallback(Protocol):
    def __call__(self, progress: ScrapeProgress) -> None: ...

class ScrapeService:
    def __init__(self, session: Session, options_config: OptionsConfig):
        self._session = session
        self._options_config = options_config
        self._repo = ListingRepository(session)

    async def run_scrape(
        self,
        source: Source,
        max_pages: int,
        search_filters: SearchFilters | None = None,
        headless: bool = True,
        progress_callback: ProgressCallback | None = None,
    ) -> ScrapeResult:
        # ... extracted logic from cli.py run_scrape()
        pass
```

### ListingService

```python
# src/i4_scout/services/listing_service.py
from i4_scout.models.pydantic_models import ListingRead

class ListingService:
    def __init__(self, session: Session):
        self._repo = ListingRepository(session)

    def get_listings(
        self,
        source: Source | None = None,
        qualified_only: bool = False,
        min_score: float | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ListingRead], int]:
        listings = self._repo.get_listings(
            source=source,
            qualified_only=qualified_only,
            min_score=min_score,
            limit=limit,
            offset=offset,
        )
        total = self._repo.count_listings(source=source, qualified_only=qualified_only)
        return [ListingRead.model_validate(l) for l in listings], total
```

---

## Appendix B: FastAPI Dependency Injection Example

```python
# src/i4_scout/api/dependencies.py
from fastapi import Depends
from sqlalchemy.orm import Session
from i4_scout.database.engine import get_session_factory

def get_db():
    SessionLocal = get_session_factory()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

def get_listing_service(session: Session = Depends(get_db)):
    return ListingService(session)

# Usage in route
@router.get("/listings")
async def list_listings(
    service: ListingService = Depends(get_listing_service),
    qualified: bool = False,
    limit: int = 20,
):
    listings, total = service.get_listings(qualified_only=qualified, limit=limit)
    return {"listings": listings, "total": total}
```
