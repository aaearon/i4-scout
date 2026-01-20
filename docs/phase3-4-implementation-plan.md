# Implementation Plan: Phase 3 & Phase 4

## Overview
Implement site scrapers (Phase 3) and option matching engine (Phase 4) in parallel, following TDD methodology.

## Critical Files to Modify/Create

### Phase 3 - Site Scrapers
| File | Action | Purpose |
|------|--------|---------|
| `src/car_scraper/scrapers/autoscout24_base.py` | CREATE | Shared scraper logic for AS24 sites |
| `src/car_scraper/scrapers/autoscout24_de.py` | CREATE | DE-specific configuration |
| `src/car_scraper/scrapers/autoscout24_nl.py` | CREATE | NL-specific configuration |
| `tests/fixtures/autoscout24_de_search.html` | CREATE | HTML fixture from PoC |
| `tests/fixtures/autoscout24_de_detail.html` | CREATE | HTML fixture from PoC |
| `tests/fixtures/autoscout24_nl_search.html` | CREATE | HTML fixture from PoC |
| `tests/fixtures/autoscout24_nl_detail.html` | CREATE | HTML fixture from PoC |
| `tests/unit/test_autoscout24_parsing.py` | CREATE | Parser unit tests |

### Phase 4 - Option Matching
| File | Action | Purpose |
|------|--------|---------|
| `src/car_scraper/config.py` | CREATE | YAML config loader |
| `src/car_scraper/matching/normalizer.py` | CREATE | Text normalization |
| `src/car_scraper/matching/bundle_expander.py` | CREATE | Package expansion |
| `src/car_scraper/matching/option_matcher.py` | CREATE | Alias matching |
| `src/car_scraper/matching/scorer.py` | CREATE | Score calculation |
| `tests/unit/test_normalizer.py` | CREATE | Normalizer tests |
| `tests/unit/test_config.py` | CREATE | Config loader tests |
| `tests/unit/test_bundle_expander.py` | CREATE | Expander tests |
| `tests/unit/test_option_matcher.py` | CREATE | Matcher tests |
| `tests/unit/test_scorer.py` | CREATE | Scorer tests |

---

## Phase 3: Site Scrapers

### Architecture Decision
Create `AutoScout24BaseScraper` intermediate class:
- **Why**: DE and NL sites have identical DOM structure, differ only in URLs/locale
- **Benefit**: Subclasses become thin configuration wrappers

```
BaseScraper (ABC)
    └── AutoScout24BaseScraper (shared parsing)
            ├── AutoScout24DEScraper (locale: de-DE, URL: /angebote/)
            └── AutoScout24NLScraper (locale: nl-NL, URL: /aanbod/)
```

### Task 3.0: Copy HTML Fixtures (First)
1. Copy `poc/results/autoscout24_de/search_results.html` → `tests/fixtures/autoscout24_de_search.html`
2. Copy `poc/results/autoscout24_de/detail_page.html` → `tests/fixtures/autoscout24_de_detail.html`
3. Copy `poc/results/autoscout24_nl/search_results.html` → `tests/fixtures/autoscout24_nl_search.html`
4. Copy `poc/results/autoscout24_nl/detail_page.html` → `tests/fixtures/autoscout24_nl_detail.html`

### Task 3.1: Write Tests First (TDD)
Create `tests/unit/test_autoscout24_parsing.py`:

```python
# Test cases to implement:
- test_parse_listing_cards_extracts_expected_count()
- test_parse_listing_cards_extracts_url()
- test_parse_listing_cards_extracts_price_from_data_attr()
- test_parse_listing_cards_extracts_mileage()
- test_parse_listing_cards_extracts_first_registration()
- test_parse_listing_detail_extracts_options()
- test_parse_listing_detail_handles_missing_sections()
- test_get_search_url_includes_pagination()
```

### Task 3.2: Implement AutoScout24BaseScraper
Location: `src/car_scraper/scrapers/autoscout24_base.py`

Key implementation details:
1. **Listing cards** - Extract from `<article>` data attributes:
   - `data-guid` → external_id
   - `data-price` → price (int, already in EUR)
   - `data-mileage` → mileage_km
   - `data-first-registration` → first_registration (parse "MM-YYYY")
   - `href` containing `/angebote/` or `/aanbod/` → url

2. **Options extraction** - Two approaches:
   - Primary: Find `VehicleOverview_itemContainer` elements
   - Fallback: Regex split on capital letters from container text

3. **Abstract properties** (for subclasses):
   - `BASE_URL`: str
   - `SEARCH_PATH`: str ("/angebote/" vs "/aanbod/")
   - `LOCALE`: str

### Task 3.3: Implement DE/NL Scrapers
Thin subclasses that only set configuration:

**autoscout24_de.py**:
```python
class AutoScout24DEScraper(AutoScout24BaseScraper):
    source = Source.AUTOSCOUT24_DE
    BASE_URL = "https://www.autoscout24.de"
    SEARCH_PATH = "/lst/bmw/i4"
    LOCALE = "de-DE"
```

**autoscout24_nl.py**:
```python
class AutoScout24NLScraper(AutoScout24BaseScraper):
    source = Source.AUTOSCOUT24_NL
    BASE_URL = "https://www.autoscout24.nl"
    SEARCH_PATH = "/lst/bmw/i4"
    LOCALE = "nl-NL"
```

---

## Phase 4: Option Matching

### Task 4.1: Text Normalizer
Location: `src/car_scraper/matching/normalizer.py`

Algorithm:
1. Lowercase: `text.lower()`
2. German ß handling: `.replace("ß", "ss")`
3. Normalize diacritics: `unicodedata.normalize('NFKD', text)`
4. Strip diacritics: `''.join(c for c in text if not unicodedata.combining(c))`
5. Remove punctuation: keep alphanumeric + spaces
6. Collapse whitespace: single spaces

Test cases:
- `"Sitzheizung"` → `"sitzheizung"`
- `"Wärmepumpe"` → `"warmepumpe"`
- `"Größe"` → `"grosse"`
- `"Head-Up Display"` → `"head up display"`
- `"360° Kamera"` → `"360 kamera"`

### Task 4.2: YAML Config Loader
Location: `src/car_scraper/config.py`

Features:
- Load YAML from path or use default `config/options.yaml`
- Validate against existing `OptionsConfig` Pydantic model
- Return frozen `OptionsConfig` instance

```python
def load_options_config(path: Path | None = None) -> OptionsConfig:
    """Load and validate options configuration from YAML."""
```

### Task 4.3: Bundle Expander
Location: `src/car_scraper/matching/bundle_expander.py`

Two-pass approach (config-driven):
1. Check if bundle name found in listing options
2. If found, inject `bundle_contents` into effective options list

```python
def expand_bundles(
    raw_options: list[str],
    config: OptionsConfig
) -> list[str]:
    """Expand detected bundles to their constituent options."""
```

### Task 4.4: Option Matcher
Location: `src/car_scraper/matching/option_matcher.py`

Algorithm:
1. Normalize all listing options
2. Expand bundles
3. Build flattened alias map from config (normalized)
4. Match each normalized listing option against alias map
5. Return `MatchResult` with categorized matches

```python
def match_options(
    raw_options: list[str],
    config: OptionsConfig
) -> MatchResult:
    """Match listing options against config aliases."""
```

### Task 4.5: Scorer
Location: `src/car_scraper/matching/scorer.py`

Formula (from implementation plan):
```python
score = (required_matched * 100) + (nice_to_have_matched * 10)
max_score = (len(required) * 100) + (len(nice_to_have) * 10)
normalized_score = (score / max_score) * 100
is_qualified = required_matched == len(required) and not has_dealbreaker
```

---

## Implementation Order (Parallelization)

```
Phase 3 Stream                    Phase 4 Stream
─────────────                     ─────────────
3.0 Copy fixtures ──────────┐     4.1 normalizer.py + tests ────┐
                            │                                    │
3.1 Write parser tests ─────┤     4.2 config.py + tests ────────┤
                            │                                    │
3.2 autoscout24_base.py ────┤     4.3 bundle_expander.py ───────┤
                            │                                    │
3.3 autoscout24_de.py ──────┤     4.4 option_matcher.py ────────┤
3.3 autoscout24_nl.py ──────┘     4.5 scorer.py + tests ────────┘
                            │                                    │
                            └──────────► Run full test suite ◄───┘
```

---

## Verification Plan

1. **Unit tests**: `pytest tests/unit/ -v`
2. **Integration tests**: `pytest tests/integration/ -v`
3. **Full suite**: `pytest tests/ -v` (expect 73+ tests passing)
4. **Manual test** (optional):
   ```bash
   # Test parsing with fixture
   python -c "
   from car_scraper.scrapers.autoscout24_de import AutoScout24DEScraper
   from pathlib import Path
   html = Path('tests/fixtures/autoscout24_de_search.html').read_text()
   # ... instantiate and parse
   "
   ```

---

## Git Workflow

1. Create feature branch: `git checkout -b feature/phase3-4-scrapers-matching`
2. Commit in logical chunks:
   - `feat(scrapers): add HTML fixtures from PoC`
   - `feat(matching): add text normalizer with tests`
   - `feat(config): add YAML config loader`
   - `feat(scrapers): add AutoScout24BaseScraper`
   - `feat(matching): add bundle expander and option matcher`
   - `feat(scrapers): add DE and NL scraper implementations`
   - `feat(matching): add scorer`
3. Final: merge to main after all tests pass

---

## Dependencies

No new dependencies required:
- `beautifulsoup4` - Already in project (HTML parsing)
- `pyyaml` - Already in project (YAML loading)
- `unicodedata` - Standard library (normalization)
- `re` - Standard library (regex)
