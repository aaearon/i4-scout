# CLI Simplification Implementation

Implemented on 2026-01-24.

## Summary

Removed redundant CLI commands (`list`, `show`, `export`, `enrich`) as the application moves to web-first, replacing them with API endpoints.

## Changes Made

### Phase 1: Export API

1. **Created Export API Tests** (`tests/integration/test_api_export.py`)
   - CSV export tests (all listings, with filters, empty database, content-disposition)
   - JSON export tests (all listings, with filters, min score, empty database)
   - Validation tests (invalid format returns 422, default format is CSV)

2. **Created Export Route** (`src/i4_scout/api/routes/export.py`)
   - `GET /api/export/listings` endpoint
   - Supports `format=csv` (default) or `format=json`
   - Supports all listing filters (source, qualified_only, min_score, price, mileage, year, country, search, has_issue)
   - Returns file with `Content-Disposition: attachment` header

3. **Registered Export Router** (`src/i4_scout/api/main.py`)
   - Added `export.router` at `/api/export`

4. **Added Export Button to Web UI** (`src/i4_scout/api/templates/components/filter_form.html`)
   - Export dropdown button with CSV/JSON options
   - Builds URL with current filter form values
   - Added CSS for dropdown styling

### Phase 2: CLI Command Removal

5. **Simplified CLI** (`src/i4_scout/cli.py`)
   - Removed: `list_listings()`, `show()`, `export()`, `enrich()` commands
   - Removed: `_listing_read_to_dict()` helper
   - Removed: Unused imports (`export_to_csv`, `export_to_json`, `InvalidFileError`, `ListingNotFoundError`)
   - Kept: `scrape()`, `recalculate_scores()`, `serve()`, `output_json()`, `_create_progress_callback()`

6. **Updated CLI Tests** (`tests/integration/test_cli.py`)
   - Removed: `TestListCommand`, `TestShowCommand`, `TestExportCommand`, `TestJsonOutput`
   - Added: `TestHelpOption`, `TestRemovedCommands`
   - Kept: Fixtures, `TestVersionOption`

7. **Updated Docker Compose** (`docker/docker-compose.yml`)
   - Removed: `list` and `export` services
   - Kept: `scraper`, `scrape-de`, `scrape-nl`

### Phase 3: Documentation Updates

8. **Updated CLAUDE.md**
   - Removed list/export CLI examples from Common Commands
   - Simplified LLM-Friendly Output section (removed list/show examples)
   - Updated CLI description to show only: scrape, recalculate-scores, serve
   - Simplified PDF Enrichment section (removed CLI, kept API)
   - Added Export API endpoint documentation

9. **Updated README.md**
   - Updated Quick Start (removed list, show, export commands)
   - Simplified CLI Commands table (3 commands instead of 7)
   - Updated Docker section (removed list and export services)
   - Added note: "For listing/export/enrichment features, use the web interface or REST API"

## Verification

```bash
# Tests pass
pytest tests/integration/test_cli.py tests/integration/test_api_export.py -v
# => 18 passed

# Linting passes
ruff check src/i4_scout/cli.py src/i4_scout/api/routes/export.py
# => All checks passed!

# CLI shows only expected commands
i4-scout --help
# => scrape, recalculate-scores, serve

# Removed commands fail properly
i4-scout list
# => Error: No such command 'list'
```

## Files Changed

| File | Action |
|------|--------|
| `src/i4_scout/api/routes/export.py` | Created |
| `tests/integration/test_api_export.py` | Created |
| `src/i4_scout/api/main.py` | Modified |
| `src/i4_scout/api/templates/components/filter_form.html` | Modified |
| `src/i4_scout/static/css/custom.css` | Modified |
| `src/i4_scout/cli.py` | Modified (removed 4 commands) |
| `tests/integration/test_cli.py` | Modified (removed test classes) |
| `docker/docker-compose.yml` | Modified (removed services) |
| `CLAUDE.md` | Modified |
| `README.md` | Modified |
