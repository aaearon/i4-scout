# Web Interface Implementation Plan

**Purpose:** Multi-session LLM implementation guide for adding FastAPI web interface to i4-scout.
**Created:** 2026-01-21
**Git Branch:** `feature/web-interface`

---

## Quick Reference

```bash
# Environment setup
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Lint and type check
ruff check src/ tests/
mypy src/

# CLI verification
i4-scout list --json
i4-scout scrape autoscout24_de --max-pages 1 --json
```

---

## Session Context

When starting a new LLM session, provide this context:

> I'm implementing a FastAPI web interface for i4-scout. Read `docs/web-interface-implementation-plan.md` to see current progress. Continue from the first incomplete task.

---

## Phases Overview

| Phase | Focus | Status |
|-------|-------|--------|
| 1 | Service Layer | Complete |
| 2 | Database Improvements | Not Started |
| 3 | FastAPI Foundation | Not Started |
| 4 | Background Scraping | Not Started |

---

# Phase 1: Service Layer

**Goal:** Extract business logic from `cli.py` into reusable services.

## Understanding the Codebase

Key files to read before starting:
- `src/i4_scout/cli.py` - Lines 127-299 contain `run_scrape()` to extract
- `src/i4_scout/cli.py` - Lines 35-59 contain duplicate `listing_to_dict()`
- `src/i4_scout/database/repository.py` - Repository pattern with session injection
- `src/i4_scout/models/pydantic_models.py` - Existing models including `ListingRead`
- `src/i4_scout/export/json_exporter.py` - Has another `listing_to_dict()` duplicate

**Gotchas:**
- `listing.source` is stored as string in DB, not as `Source` enum
- Price is stored as EUR integer (45000 = 45,000 EUR), not cents
- `listing.matched_options` requires loaded relationships (use within session)

## Tasks

### Task 1.1: Add Pydantic Models
- [x] Add `ScrapeProgress` model to `pydantic_models.py`
- [x] Add `ScrapeResult` model to `pydantic_models.py`
- [x] Fix `ListingRead` to handle source as string (not needed - SQLAlchemy returns Source enum)
- [x] Write tests for new models
- [x] Run `pytest tests/unit/test_pydantic_models.py -v`

**Models to add:**
```python
class ScrapeProgress(BaseModel):
    """Progress update during scraping."""
    page: int
    total_pages: int
    listings_found: int
    new_count: int
    updated_count: int
    skipped_count: int
    current_listing: Optional[str] = None

class ScrapeResult(BaseModel):
    """Final result of a scrape operation."""
    total_found: int
    new_listings: int
    updated_listings: int
    skipped_unchanged: int
    fetched_details: int
```

### Task 1.2: Create ListingService
- [x] Create `src/i4_scout/services/__init__.py`
- [x] Create `src/i4_scout/services/listing_service.py`
- [x] Write tests first: `tests/unit/test_listing_service.py`
- [x] Implement `ListingService.get_listings()` returning `tuple[list[ListingRead], int]`
- [x] Implement `ListingService.get_listing()` returning `ListingRead | None`
- [x] Implement `ListingService.delete_listing()` returning `bool`
- [x] Run `pytest tests/unit/test_listing_service.py -v`

**Interface:**
```python
class ListingService:
    def __init__(self, session: Session) -> None:
        self._repo = ListingRepository(session)

    def get_listings(
        self,
        source: Source | None = None,
        qualified_only: bool = False,
        min_score: float | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ListingRead], int]: ...

    def get_listing(self, listing_id: int) -> ListingRead | None: ...
    def delete_listing(self, listing_id: int) -> bool: ...
```

### Task 1.3: Create ScrapeService
- [x] Create `src/i4_scout/services/scrape_service.py`
- [x] Write tests first: `tests/unit/test_scrape_service.py`
- [x] Extract logic from `cli.py:127-299` into `ScrapeService.run_scrape()`
- [x] Add progress callback support for CLI/API progress reporting
- [x] Run `pytest tests/unit/test_scrape_service.py -v`

**Interface:**
```python
class ScrapeService:
    def __init__(self, session: Session, options_config: OptionsConfig) -> None:
        self._session = session
        self._options_config = options_config
        self._repo = ListingRepository(session)

    async def run_scrape(
        self,
        source: Source,
        max_pages: int,
        search_filters: SearchFilters | None = None,
        headless: bool = True,
        use_cache: bool = True,
        progress_callback: Callable[[ScrapeProgress], None] | None = None,
    ) -> ScrapeResult: ...
```

### Task 1.4: Add Config Helper
- [x] Add `merge_search_filters()` to `config.py`
- [x] Write test for merge function
- [x] Run `pytest tests/unit/test_config.py -v`

**Function:**
```python
def merge_search_filters(
    config_filters: SearchFilters,
    overrides: dict[str, Any],
) -> SearchFilters:
    """Merge CLI/API overrides with config filters. Overrides take precedence."""
    return SearchFilters(
        price_max_eur=overrides.get("price_max") or config_filters.price_max_eur,
        mileage_max_km=overrides.get("mileage_max") or config_filters.mileage_max_km,
        year_min=overrides.get("year_min") or config_filters.year_min,
        year_max=config_filters.year_max,
        countries=overrides.get("countries") or config_filters.countries,
    )
```

### Task 1.5: Refactor CLI
- [x] Update `scrape` command to use `ScrapeService`
- [x] Update `list` command to use `ListingService`
- [x] Update `show` command to use `ListingService`
- [x] Remove `listing_to_dict()` function (lines 35-59)
- [x] Remove `run_scrape()` function (lines 127-299)
- [x] Run `pytest tests/integration/test_cli.py -v`

### Task 1.6: Update json_exporter
- [x] Replace `listing_to_dict()` with `ListingRead.model_validate()`
- [x] Update `export_to_json()` to use Pydantic serialization
- [x] Run `pytest tests/ -v` (full test suite)

### Task 1.7: Phase 1 Verification
- [x] `pytest tests/ -v` - all tests pass (181 passed)
- [x] `ruff check src/ tests/` - no lint errors in new files
- [x] `mypy src/` - no type errors in new files
- [x] `i4-scout list --json` - returns valid JSON
- [x] `i4-scout show 1 --json` - returns valid JSON
- [x] `i4-scout scrape autoscout24_de --max-pages 1 --json` - works (not tested live)
- [x] Create commit: `feat(services): add service layer (Phase 1 complete)`

---

# Phase 2: Database Improvements

**Goal:** Prepare database for concurrent web access.

## Tasks

### Task 2.1: Add DATABASE_URL Support
- [ ] Update `engine.py` to check `DATABASE_URL` env var
- [ ] Add `get_database_url()` helper function
- [ ] Write test for DATABASE_URL handling
- [ ] Run `pytest tests/unit/test_engine.py -v` (create if needed)

**Code:**
```python
def get_database_url(db_path: Path | None = None) -> str:
    """Get database URL from environment or construct from path."""
    if url := os.environ.get("DATABASE_URL"):
        return url
    path = db_path or _get_db_path()
    return f"sqlite:///{path}"
```

### Task 2.2: Add Connection Pooling and WAL Mode
- [ ] Update `get_engine()` with pooling config
- [ ] Add WAL mode for SQLite databases
- [ ] Handle PostgreSQL vs SQLite connection args
- [ ] Run tests

**Code:**
```python
def get_engine(db_path: Path | str | None = None, echo: bool = False) -> Engine:
    global _engine
    if _engine is None:
        database_url = get_database_url(db_path)

        connect_args = {}
        if database_url.startswith("sqlite"):
            connect_args = {"check_same_thread": False, "timeout": 30}

        _engine = create_engine(
            database_url,
            echo=echo,
            connect_args=connect_args,
            pool_size=5,
            pool_recycle=3600,
        )

        # Enable WAL mode for SQLite
        if database_url.startswith("sqlite"):
            with _engine.connect() as conn:
                conn.execute(text("PRAGMA journal_mode=WAL"))
                conn.commit()

    return _engine
```

### Task 2.3: Add ScrapeJob Model
- [ ] Add `ScrapeJob` class to `db_models.py`
- [ ] Add migration or update `init_db()` to create table
- [ ] Write repository methods for job CRUD
- [ ] Write tests for job repository
- [ ] Run `pytest tests/ -v`

**Model:**
```python
class ScrapeJob(Base):
    """Background scrape job tracking."""
    __tablename__ = "scrape_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    max_pages: Mapped[int] = mapped_column(Integer, default=50)
    search_filters_json: Mapped[Optional[str]] = mapped_column(Text)

    current_page: Mapped[int] = mapped_column(Integer, default=0)
    total_found: Mapped[int] = mapped_column(Integer, default=0)
    new_listings: Mapped[int] = mapped_column(Integer, default=0)
    updated_listings: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
```

### Task 2.4: Phase 2 Verification
- [ ] DATABASE_URL env var works with PostgreSQL URL
- [ ] SQLite WAL mode enabled (check with `PRAGMA journal_mode;`)
- [ ] ScrapeJob table created
- [ ] All tests pass
- [ ] Create commit: `feat(db): database improvements (Phase 2 complete)`

---

# Phase 3: FastAPI Foundation

**Goal:** Implement read-only API endpoints.

## Tasks

### Task 3.1: Add Dependencies
- [ ] Add `fastapi>=0.109.0` to `pyproject.toml` dependencies
- [ ] Add `uvicorn[standard]>=0.27.0` to dependencies
- [ ] Add `httpx>=0.26.0` to dev dependencies
- [ ] Run `pip install -e ".[dev]"`

### Task 3.2: Create API Package Structure
- [ ] Create `src/i4_scout/api/__init__.py`
- [ ] Create `src/i4_scout/api/main.py` with app factory
- [ ] Create `src/i4_scout/api/dependencies.py` with `get_db()` and service deps
- [ ] Create `src/i4_scout/api/schemas.py` with response models
- [ ] Create `src/i4_scout/api/routes/__init__.py`

### Task 3.3: Implement Listings Endpoints
- [ ] Create `src/i4_scout/api/routes/listings.py`
- [ ] Implement `GET /api/listings` with pagination and filters
- [ ] Implement `GET /api/listings/{id}` for single listing
- [ ] Implement `GET /api/listings/{id}/price-history`
- [ ] Implement `DELETE /api/listings/{id}`
- [ ] Write tests: `tests/integration/test_api_listings.py`
- [ ] Run tests

### Task 3.4: Implement Config Endpoints
- [ ] Create `src/i4_scout/api/routes/config.py`
- [ ] Implement `GET /api/config/options`
- [ ] Implement `GET /api/config/filters`
- [ ] Write tests
- [ ] Run tests

### Task 3.5: Implement Stats Endpoint
- [ ] Create `src/i4_scout/api/routes/stats.py`
- [ ] Implement `GET /api/stats` with aggregated data
- [ ] Write tests
- [ ] Run tests

### Task 3.6: Add Serve Command
- [ ] Add `serve` command to `cli.py`
- [ ] Test server startup
- [ ] Verify OpenAPI docs at `/docs`

**Command:**
```python
@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h"),
    port: int = typer.Option(8000, "--port", "-p"),
    reload: bool = typer.Option(False, "--reload", "-r"),
) -> None:
    """Start the API server."""
    import uvicorn
    uvicorn.run("i4_scout.api.main:app", host=host, port=port, reload=reload)
```

### Task 3.7: Phase 3 Verification
- [ ] `i4-scout serve` starts server on port 8000
- [ ] `GET /api/listings` returns paginated listings
- [ ] `GET /api/listings/{id}` returns single listing
- [ ] `GET /api/stats` returns statistics
- [ ] OpenAPI docs available at `http://localhost:8000/docs`
- [ ] All tests pass
- [ ] Create commit: `feat(api): FastAPI foundation (Phase 3 complete)`

---

# Phase 4: Background Scraping

**Goal:** Enable async scraping via API with job tracking.

## Tasks

### Task 4.1: Create JobService
- [ ] Create `src/i4_scout/services/job_service.py`
- [ ] Implement `create_job()`, `get_job()`, `get_recent_jobs()`
- [ ] Implement `update_status()`, `update_progress()`
- [ ] Implement `complete_job()`, `fail_job()`
- [ ] Implement `cleanup_old_jobs()`
- [ ] Write tests: `tests/unit/test_job_service.py`
- [ ] Run tests

### Task 4.2: Implement Scrape Endpoints
- [ ] Create `src/i4_scout/api/routes/scrape.py`
- [ ] Implement `POST /api/scrape/jobs` to create job
- [ ] Implement `GET /api/scrape/jobs` to list recent jobs
- [ ] Implement `GET /api/scrape/jobs/{id}` for status/progress
- [ ] Write tests: `tests/integration/test_api_scrape.py`
- [ ] Run tests

### Task 4.3: Implement Background Execution
- [ ] Add `run_scrape_job()` background task function
- [ ] Wire up `BackgroundTasks` in POST endpoint
- [ ] Ensure proper error handling and status updates
- [ ] Test background execution manually
- [ ] Write integration test for full scrape cycle

### Task 4.4: Phase 4 Verification
- [ ] `POST /api/scrape/jobs` creates job and returns immediately
- [ ] `GET /api/scrape/jobs/{id}` shows progress during execution
- [ ] Job status updates to "completed" when done
- [ ] Job status updates to "failed" on error
- [ ] All tests pass
- [ ] Create commit: `feat(api): background scraping (Phase 4 complete)`

---

# Final Verification

- [ ] Full test suite passes: `pytest tests/ -v`
- [ ] Lint passes: `ruff check src/ tests/`
- [ ] Type check passes: `mypy src/`
- [ ] CLI still works as expected
- [ ] API server starts and responds
- [ ] Background scraping works end-to-end
- [ ] Documentation updated
- [ ] Merge feature branch to main

---

# Risk Mitigation

| Risk | Mitigation |
|------|------------|
| CLI breaks during refactor | Run tests after each task; keep backward compatibility |
| Session lifecycle issues | Services accept session in constructor; caller manages lifecycle |
| SQLite contention | Limit concurrent scrapes to 1; use existing retry logic |
| Background task failures | Comprehensive error handling; job status tracking |
| Memory leaks from Playwright | Proper browser cleanup in background tasks |

---

# Commit Guidelines

Follow conventional commits:
- `feat(scope): description` - New feature
- `fix(scope): description` - Bug fix
- `refactor(scope): description` - Code refactoring
- `test(scope): description` - Test additions/changes
- `docs(scope): description` - Documentation

Scopes: `models`, `services`, `cli`, `api`, `db`, `export`
