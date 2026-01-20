# BMW i4 i4-scout - Implementation Plan

> **Note:** This plan must be saved to `docs/implementation-plan.md` before starting Phase 0.

## Overview
Python CLI tool to scrape BMW i4 eDrive40 listings from mobile.de, autoscout24.de, and autoscout24.nl, match against user-defined options, and store results in SQLite.

## Technical Stack
| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | Python 3.11+ | Rich ecosystem, async support |
| Browser | Playwright (async) | Modern, reliable, good stealth support |
| Anti-bot | playwright-stealth | Context-level evasion, configurable |
| ORM | SQLAlchemy 2.0 | Type-safe, async support |
| CLI | Typer + Rich | Modern CLI with pretty output |
| Validation | Pydantic 2.x | Config parsing, data validation |
| Config | YAML | User-provided options.yaml |
| Container | Docker (playwright base image) | Single container approach |

## Architecture Decisions

### 1. Scraper: Abstract Base Class (ABC)
Both internal analysis and Gemini agree - ABC provides code reuse for shared infrastructure while enforcing site-specific contracts.

```
BaseScraper (ABC)
├── shared: browser context, stealth, retry, rate limiting
├── abstract: get_search_url(), parse_listing_cards(), parse_listing_detail()
└── subclasses: MobileDeScraper, AutoScout24DeScraper, AutoScout24NlScraper
```

### 2. Anti-Bot Strategy
- **Primary:** playwright-stealth with `Stealth().use_async()` context manager
- **Context rotation:** New BrowserContext every N requests
- **Humanization:** Random delays (2-8s), mouse movement before clicks
- **User-agent:** Rotate realistic desktop Chrome UAs

### 3. Option Matching: Two-Pass Algorithm
1. **Normalize:** Lowercase, strip diacritics, remove punctuation
2. **Bundle expansion:** Detect packages, expand to constituent options
3. **Alias matching:** Match normalized text against flattened alias map

### 4. Database Schema
```sql
listings (id, source, url, price, mileage, year, vin, location_*, dealer_*,
          description, raw_options_text, photos_json, match_score, is_qualified,
          dedup_hash, first_seen_at, last_seen_at)

options (id, canonical_name, display_name, category, is_bundle)

listing_options (listing_id, option_id, raw_text, confidence)

price_history (id, listing_id, price, recorded_at)

scrape_sessions (id, source, started_at, completed_at, status, stats)
```

## Project Structure
```
i4-scout/
├── src/i4_scout/
│   ├── __init__.py
│   ├── cli.py                 # Typer CLI
│   ├── config.py              # Settings loader
│   ├── models/
│   │   ├── pydantic_models.py # Data validation
│   │   └── db_models.py       # SQLAlchemy ORM
│   ├── database/
│   │   ├── engine.py          # DB connection
│   │   └── repository.py      # CRUD operations
│   ├── scrapers/
│   │   ├── base.py            # BaseScraper ABC
│   │   ├── browser.py         # Playwright + stealth setup
│   │   ├── mobile_de.py
│   │   ├── autoscout24_de.py
│   │   └── autoscout24_nl.py
│   ├── matching/
│   │   ├── normalizer.py      # Text normalization
│   │   ├── bundle_expander.py # Package inference
│   │   ├── option_matcher.py  # Core matching
│   │   └── scorer.py          # Score calculation
│   └── export/
│       ├── csv_exporter.py
│       └── json_exporter.py
├── tests/
│   ├── unit/                  # Matcher, normalizer, scorer tests
│   ├── integration/           # DB, scraper with fixtures
│   └── fixtures/              # HTML snapshots, sample data
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── docs/
├── config/
│   └── options.yaml           # User's BMW i4 options config
├── data/                      # SQLite DB (gitignored)
├── pyproject.toml
└── README.md
```

## CLI Commands
```bash
i4-scout scrape --source mobile_de --max-pages 10
i4-scout list --qualified --min-score 80 --limit 20
i4-scout show <listing_id>
i4-scout export --format csv --qualified
i4-scout init-db
```

## Implementation Phases

### Parallelization Overview

```
Phase 0 (PoC)
├── 0.1 Setup ──────────────────────────┐
│                                       ▼
├── 0.2.1 mobile.de PoC ───────────────┬──► 0.3 Gate Decision
├── 0.2.2 autoscout24.de PoC ──────────┤    (wait for all)
└── 0.2.3 autoscout24.nl PoC ──────────┘

Phase 1 (Foundation) - after Phase 0 gate passes
├── 1.1 pyproject.toml ────────────────┐
│                                      ▼
├── 1.2.1 Pydantic models ─────────────┬──► 1.3 DB models (needs 1.2.1)
├── 1.2.2 Directory structure ─────────┤
└── 1.2.3 CLI skeleton ────────────────┘
                                       ▼
                               1.4 DB engine (needs 1.3)
                                       ▼
                               1.5 Tests

Phase 2 (Scraper Infra) + Phase 4 (Matching) - CAN RUN IN PARALLEL

Phase 2:                               Phase 4:
├── 2.1 Browser setup ────┐            ├── 4.1 Normalizer ────────────┐
│                         ▼            ├── 4.2 Config loader ─────────┤
├── 2.2 BaseScraper ──────┤            │                              ▼
│                         ▼            ├── 4.3 Bundle expander ───────┤
└── 2.3 Repository ───────┘            ├── 4.4 Option matcher ────────┤
                                       └── 4.5 Scorer ────────────────┘

Phase 3 (Site Scrapers) - after Phase 2, parallel within phase
├── 3.1 mobile.de ─────────────────────┐
├── 3.2 autoscout24.de ────────────────┼──► 3.4 Tests (wait for all)
└── 3.3 autoscout24.nl ────────────────┘

Phase 5 (Integration) - after Phases 3 + 4
├── 5.1 Scrape command ────────────────┐
├── 5.2 List/show commands ────────────┼──► 5.4 Export command
└── 5.3 Exporters ─────────────────────┘

Phase 6 (Docker & Docs) - after Phase 5
├── 6.1 Dockerfile ────────────────────┐
├── 6.2 docker-compose ────────────────┼──► parallel
└── 6.3 Documentation ─────────────────┘
```

---

### Phase 0: Proof of Concept (GATE)

**Goal:** Validate scraping feasibility before full investment.
**Status:** `[x] COMPLETED - 2026-01-20`

#### Results Summary

| Site | Status | Listings | Options | Notes |
|------|--------|----------|---------|-------|
| autoscout24.de | PASS | 10 | 50 | Full functionality |
| autoscout24.nl | PASS | 10 | 50 | Full functionality |
| mobile.de | FAIL | 0 | 0 | Bot detection ("Zugriff verweigert") |

#### Task 0.1: Environment Setup
| ID | Task | Status | Depends On | Parallel |
|----|------|--------|------------|----------|
| 0.1.1 | Create venv with Python 3.11+ | `[x]` | - | - |
| 0.1.2 | Install playwright, playwright-stealth | `[x]` | 0.1.1 | - |
| 0.1.3 | Run `playwright install chromium` | `[x]` | 0.1.2 | - |
| 0.1.4 | Create `poc/` and `poc/results/` directories | `[x]` | - | Yes |

#### Task 0.2: Site PoC Scripts (PARALLEL)
| ID | Task | Status | Depends On | Parallel |
|----|------|--------|------------|----------|
| 0.2.1 | Write `poc/poc_mobile_de.py` | `[x]` | 0.1.3 | Yes |
| 0.2.2 | Write `poc/poc_autoscout24_de.py` | `[x]` | 0.1.3 | Yes |
| 0.2.3 | Write `poc/poc_autoscout24_nl.py` | `[x]` | 0.1.3 | Yes |
| 0.2.4 | Run all PoC scripts, collect results | `[x]` | 0.2.1-3 | - |

#### Task 0.3: Gate Decision
| ID | Task | Status | Depends On |
|----|------|--------|------------|
| 0.3.1 | Review PoC results for all 3 sites | `[x]` | 0.2.4 |
| 0.3.2 | Document blockers and workarounds | `[x]` | 0.3.1 |
| 0.3.3 | Make go/no-go decision | `[x]` | 0.3.2 |

**Gate Decision: PROCEED with AutoScout24 sites, defer mobile.de**

- AutoScout24 (DE + NL): Both sites work reliably with playwright-stealth
- mobile.de: Strong bot detection requires advanced countermeasures (residential proxies, CAPTCHA solving)
- See `poc/results/POC_SUMMARY.md` for detailed analysis

---

### Phase 1: Project Foundation

**Goal:** Establish project structure, models, and database.
**Status:** `[x] COMPLETED`
**Depends On:** Phase 0 gate pass

#### Task 1.1: Project Init
| ID | Task | Status | Depends On | Parallel | Output |
|----|------|--------|------------|----------|--------|
| 1.1.1 | Create `pyproject.toml` with dependencies | `[x]` | - | - | `pyproject.toml` |
| 1.1.2 | Create project venv, install deps | `[x]` | 1.1.1 | - | `.venv/` |
| 1.1.3 | Initialize git repository | `[x]` | 1.1.1 | Yes | `.git/` |
| 1.1.4 | Create `.gitignore` | `[x]` | - | Yes | `.gitignore` |

#### Task 1.2: Structure & Models (PARALLEL after 1.1)
| ID | Task | Status | Depends On | Parallel | Output |
|----|------|--------|------------|----------|--------|
| 1.2.1 | Create directory structure | `[x]` | 1.1.2 | Yes | `src/`, `tests/`, etc. |
| 1.2.2 | Write Pydantic models | `[x]` | 1.1.2 | Yes | `models/pydantic_models.py` |
| 1.2.3 | Write CLI skeleton (Typer) | `[x]` | 1.1.2 | Yes | `cli.py` |

#### Task 1.3: Database Layer
| ID | Task | Status | Depends On | Parallel | Output |
|----|------|--------|------------|----------|--------|
| 1.3.1 | Write SQLAlchemy ORM models | `[x]` | 1.2.2 | - | `models/db_models.py` |
| 1.3.2 | Write DB engine setup | `[x]` | 1.3.1 | - | `database/engine.py` |
| 1.3.3 | Write init-db CLI command | `[x]` | 1.3.2, 1.2.3 | - | `cli.py` |

#### Task 1.4: Foundation Tests
| ID | Task | Status | Depends On | Parallel | Output |
|----|------|--------|------------|----------|--------|
| 1.4.1 | Write Pydantic model tests | `[x]` | 1.2.2 | Yes | `tests/unit/test_models.py` |
| 1.4.2 | Write DB model tests | `[x]` | 1.3.2 | Yes | `tests/unit/test_db.py` |
| 1.4.3 | Run all Phase 1 tests | `[x]` | 1.4.1-2 | - | - |

---

### Phase 2: Scraper Infrastructure

**Goal:** Create browser automation and base scraper framework.
**Status:** `[x] COMPLETED - 2026-01-20`
**Depends On:** Phase 1 complete
**Can Run Parallel With:** Phase 4

#### Task 2.1: Browser Automation
| ID | Task | Status | Depends On | Parallel | Output |
|----|------|--------|------------|----------|--------|
| 2.1.1 | Write Playwright+stealth browser manager | `[x]` | Phase 1 | - | `scrapers/browser.py` |
| 2.1.2 | Add context rotation, humanization | `[x]` | 2.1.1 | - | `scrapers/browser.py` |
| 2.1.3 | Write browser stealth test | `[x]` | 2.1.2 | - | `tests/integration/test_browser.py` |

#### Task 2.2: Base Scraper
| ID | Task | Status | Depends On | Parallel | Output |
|----|------|--------|------------|----------|--------|
| 2.2.1 | Write BaseScraper ABC | `[x]` | 2.1.1 | - | `scrapers/base.py` |
| 2.2.2 | Add retry logic (tenacity) | `[x]` | 2.2.1 | - | `scrapers/base.py` |
| 2.2.3 | Add rate limiting | `[x]` | 2.2.1 | Yes | `scrapers/base.py` |

#### Task 2.3: Repository Layer
| ID | Task | Status | Depends On | Parallel | Output |
|----|------|--------|------------|----------|--------|
| 2.3.1 | Write CRUD operations | `[x]` | Phase 1 | Yes | `database/repository.py` |
| 2.3.2 | Add upsert/dedup logic | `[x]` | 2.3.1 | - | `database/repository.py` |
| 2.3.3 | Write repository tests | `[x]` | 2.3.2 | - | `tests/integration/test_repository.py` |

---

### Phase 3: Site Scrapers

**Goal:** Implement scrapers for all 3 target sites.
**Status:** `[x] COMPLETED - 2026-01-20` (AutoScout24 DE/NL only; mobile.de deferred)
**Depends On:** Phase 2 complete

#### Task 3.1-3.3: Site Implementations (PARALLEL)
| ID | Task | Status | Depends On | Parallel | Output |
|----|------|--------|------------|----------|--------|
| 3.1.1 | Implement mobile.de scraper | `[-]` | Phase 2 | Yes | DEFERRED (bot detection) |
| 3.1.2 | Write mobile.de parser tests | `[-]` | 3.1.1 | - | DEFERRED |
| 3.2.1 | Implement autoscout24.de scraper | `[x]` | Phase 2 | Yes | `scrapers/autoscout24_de.py` |
| 3.2.2 | Write autoscout24.de parser tests | `[x]` | 3.2.1 | - | `tests/unit/test_autoscout24_parsing.py` |
| 3.3.1 | Implement autoscout24.nl scraper | `[x]` | Phase 2 | Yes | `scrapers/autoscout24_nl.py` |
| 3.3.2 | Write autoscout24.nl parser tests | `[x]` | 3.3.1 | - | `tests/unit/test_autoscout24_parsing.py` |

#### Task 3.4: Test Fixtures
| ID | Task | Status | Depends On | Parallel | Output |
|----|------|--------|------------|----------|--------|
| 3.4.1 | Capture HTML fixtures from PoC | `[x]` | 3.1-3.3 | - | `tests/fixtures/` |
| 3.4.2 | Run all scraper tests | `[x]` | 3.4.1 | - | 16 tests passing |

---

### Phase 4: Option Matching

**Goal:** Implement options matching against user's YAML config.
**Status:** `[x] COMPLETED - 2026-01-20`
**Depends On:** Phase 1 complete
**Can Run Parallel With:** Phase 2

#### Task 4.1: Text Processing (PARALLEL)
| ID | Task | Status | Depends On | Parallel | Output |
|----|------|--------|------------|----------|--------|
| 4.1.1 | Write text normalizer | `[x]` | Phase 1 | Yes | `matching/normalizer.py` |
| 4.1.2 | Write normalizer tests | `[x]` | 4.1.1 | - | `tests/unit/test_normalizer.py` |
| 4.2.1 | Write YAML config loader | `[x]` | Phase 1 | Yes | `config.py` |
| 4.2.2 | Write config loader tests | `[x]` | 4.2.1 | - | `tests/unit/test_config.py` |

#### Task 4.3: Matching Engine
| ID | Task | Status | Depends On | Parallel | Output |
|----|------|--------|------------|----------|--------|
| 4.3.1 | Write bundle expander | `[x]` | 4.2.1 | - | `matching/bundle_expander.py` |
| 4.3.2 | Write option matcher | `[x]` | 4.1.1, 4.2.1 | - | `matching/option_matcher.py` |
| 4.3.3 | Write scorer | `[x]` | 4.3.2 | - | `matching/scorer.py` |
| 4.3.4 | Write matching tests | `[x]` | 4.3.1-3 | - | `tests/unit/test_bundle_expander.py`, `test_option_matcher.py`, `test_scorer.py` |

---

### Phase 5: Integration & CLI

**Goal:** Wire all components together into working CLI.
**Status:** `[x] Complete`
**Depends On:** Phases 3 + 4 complete

#### Task 5.1: Core Commands
| ID | Task | Status | Depends On | Parallel | Output |
|----|------|--------|------------|----------|--------|
| 5.1.1 | Implement `scrape` command | `[x]` | Phases 3+4 | - | `cli.py` |
| 5.1.2 | Implement `list` command | `[x]` | 5.1.1 | Yes | `cli.py` |
| 5.1.3 | Implement `show` command | `[x]` | 5.1.1 | Yes | `cli.py` |

#### Task 5.2: Export (PARALLEL)
| ID | Task | Status | Depends On | Parallel | Output |
|----|------|--------|------------|----------|--------|
| 5.2.1 | Write CSV exporter | `[x]` | Phase 3 | Yes | `export/csv_exporter.py` |
| 5.2.2 | Write JSON exporter | `[x]` | Phase 3 | Yes | `export/json_exporter.py` |
| 5.2.3 | Implement `export` command | `[x]` | 5.2.1-2 | - | `cli.py` |

#### Task 5.3: Integration Tests
| ID | Task | Status | Depends On | Parallel | Output |
|----|------|--------|------------|----------|--------|
| 5.3.1 | Write CLI integration tests | `[x]` | 5.1-2 | - | `tests/integration/test_cli.py` |
| 5.3.2 | Run full test suite | `[x]` | 5.3.1 | - | - |

---

### Phase 6: Docker & Documentation

**Goal:** Containerize and document the application.
**Status:** `[x] Complete`
**Depends On:** Phase 5 complete

#### Task 6.1: Docker (PARALLEL)
| ID | Task | Status | Depends On | Parallel | Output |
|----|------|--------|------------|----------|--------|
| 6.1.1 | Write Dockerfile | `[x]` | Phase 5 | Yes | `docker/Dockerfile` |
| 6.1.2 | Write docker-compose.yml | `[x]` | 6.1.1 | - | `docker/docker-compose.yml` |
| 6.1.3 | Test Docker build and run | `[ ]` | 6.1.2 | - | - |

#### Task 6.2: Documentation (PARALLEL)
| ID | Task | Status | Depends On | Parallel | Output |
|----|------|--------|------------|----------|--------|
| 6.2.1 | Write README.md | `[x]` | Phase 5 | Yes | `README.md` |
| 6.2.2 | Write options config docs | `[x]` | Phase 4 | Yes | `docs/options-config.md` |
| 6.2.3 | Write scraper development guide | `[ ]` | Phase 3 | Yes | `docs/scraper-development.md` |
| 6.2.4 | Final commit and tag v0.1.0 | `[x]` | 6.1-2 | - | - |

## Key Implementation Details

### Stealth Browser Setup
```python
from playwright_stealth import Stealth

async def create_browser_context():
    stealth = Stealth(
        navigator_languages_override=("de-DE", "de", "en"),
        navigator_platform_override="Win32"
    )
    async with stealth.use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            locale='de-DE',
            timezone_id='Europe/Berlin'
        )
        yield context
```

### Match Score Calculation
```python
def calculate_score(matched_options: set[str], config: OptionsConfig) -> tuple[float, bool]:
    required_matched = sum(1 for o in config.required if o.name in matched_options)
    nice_to_have_matched = sum(1 for o in config.nice_to_have if o.name in matched_options)

    score = (required_matched * 100) + (nice_to_have_matched * 10)
    max_score = (len(config.required) * 100) + (len(config.nice_to_have) * 10)

    is_qualified = required_matched == len(config.required)
    normalized = (score / max_score) * 100 if max_score > 0 else 0

    return normalized, is_qualified
```

## Dependencies
```toml
dependencies = [
    "playwright>=1.40.0",
    "playwright-stealth>=1.0.0",
    "sqlalchemy>=2.0.0",
    "typer>=0.9.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "pyyaml>=6.0",
    "tenacity>=8.2.0",
    "rich>=13.0.0",
]
```

## Verification Plan
1. **Unit tests:** `pytest tests/unit/ -v`
2. **Integration tests:** `pytest tests/integration/ -v`
3. **Stealth verification:** Run against bot.sannysoft.com
4. **Manual test:** `i4-scout scrape --source mobile_de --max-pages 1`
5. **Docker test:** `docker-compose run scraper scrape --source mobile_de`

## Notes
- User's options.yaml already provided - copy to `config/options.yaml`
- LCI identification: production_date >= 2024-06, iDrive 8.5
- Innovationspaket II bundles: HUD + Parking Assistant Plus + Driving Assistant Pro
- Dedup by attributes since VIN often unavailable in listings
