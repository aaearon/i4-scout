# Plan: HTMX + Jinja2 Web Frontend Dashboard

## Overview

Build a full-featured web dashboard using HTMX + Jinja2, embedded in FastAPI. Server-rendered HTML with minimal JavaScript, single deployment.

**Status Legend:** `[ ]` = Not started, `[~]` = In progress, `[x]` = Complete

## Technology Stack

- **UI Framework:** Pico CSS (~10KB) - classless, dark mode, mobile responsive
- **Interactivity:** HTMX (~14KB) - partial page updates, polling
- **Templates:** Jinja2 - integrates with FastAPI
- **Hosting:** Embedded in FastAPI via StaticFiles and Jinja2Templates

---

## Phase 1: Foundation Setup

**Status:** `[ ]` Not Started

**Goal:** Template infrastructure and static file serving

### Tasks

- [ ] **1.1** Create directory structure
  - [ ] Create `src/i4_scout/static/css/`
  - [ ] Create `src/i4_scout/static/js/`
  - [ ] Create `src/i4_scout/api/templates/`
  - [ ] Create `src/i4_scout/api/templates/components/`
  - [ ] Create `src/i4_scout/api/templates/pages/`
  - [ ] Create `src/i4_scout/api/templates/partials/`

- [ ] **1.2** Download static assets
  - [ ] Download Pico CSS to `src/i4_scout/static/css/pico.min.css`
    - URL: https://unpkg.com/@picocss/pico@2/css/pico.min.css
  - [ ] Download HTMX to `src/i4_scout/static/js/htmx.min.js`
    - URL: https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js

- [ ] **1.3** Create custom CSS (`src/i4_scout/static/css/custom.css`)
  - [ ] HTMX loading indicator styles
  - [ ] Qualified/not-qualified badge styles
  - [ ] Stats grid layout
  - [ ] Table responsive styles

- [ ] **1.4** Modify FastAPI app (`src/i4_scout/api/main.py`)
  - [ ] Import StaticFiles and Jinja2Templates
  - [ ] Mount static files at `/static`
  - [ ] Initialize Jinja2Templates and store on `app.state`
  - [ ] Import and include web router
  - [ ] Import and include partials router

- [ ] **1.5** Add template dependency (`src/i4_scout/api/dependencies.py`)
  - [ ] Create `get_templates()` function
  - [ ] Create `TemplatesDep` type alias

- [ ] **1.6** Create base template (`src/i4_scout/api/templates/base.html`)
  - [ ] HTML5 doctype with dark mode support
  - [ ] Include Pico CSS and custom CSS
  - [ ] Include HTMX script
  - [ ] Navigation with links to Dashboard, Listings, Scrape
  - [ ] Main content block
  - [ ] Footer with version

- [ ] **1.7** Create web routes file (`src/i4_scout/api/routes/web.py`)
  - [ ] Create router
  - [ ] Add placeholder dashboard route at `/`

- [ ] **1.8** Create partials routes file (`src/i4_scout/api/routes/partials.py`)
  - [ ] Create router with `/partials` prefix

### Verification
- [ ] `i4-scout serve` starts without errors
- [ ] `GET /static/css/pico.min.css` returns CSS
- [ ] `GET /static/js/htmx.min.js` returns JS
- [ ] `GET /` returns HTML page

### Commit
```
feat(web): add template and static file infrastructure (Phase 1)
```

---

## Phase 2: Dashboard Page

**Status:** `[ ]` Not Started

**Goal:** Stats overview with auto-refresh

### Tasks

- [ ] **2.1** Create stats cards component (`src/i4_scout/api/templates/components/stats_cards.html`)
  - [ ] Total listings card
  - [ ] Qualified listings card
  - [ ] Average price card
  - [ ] Average mileage card
  - [ ] Average score card
  - [ ] Listings by source table

- [ ] **2.2** Create listing card component (`src/i4_scout/api/templates/components/listing_card.html`)
  - [ ] Title, price, mileage
  - [ ] Qualified badge
  - [ ] Link to detail

- [ ] **2.3** Create dashboard page (`src/i4_scout/api/templates/pages/dashboard.html`)
  - [ ] Extend base template
  - [ ] Stats section with `hx-trigger="load, every 60s"`
  - [ ] Recent qualified listings section

- [ ] **2.4** Implement dashboard route (`src/i4_scout/api/routes/web.py`)
  - [ ] `GET /` - Render dashboard with stats
  - [ ] Fetch stats using existing service
  - [ ] Fetch recent qualified listings

- [ ] **2.5** Implement stats partial (`src/i4_scout/api/routes/partials.py`)
  - [ ] `GET /partials/stats` - Return stats cards HTML fragment

- [ ] **2.6** Implement recent qualified partial (`src/i4_scout/api/routes/partials.py`)
  - [ ] `GET /partials/recent-qualified` - Return listing cards HTML fragment

### Verification
- [ ] `GET /` renders dashboard with stats
- [ ] Stats display correct counts and averages
- [ ] Stats auto-refresh (check network tab)
- [ ] Recent qualified listings load via HTMX

### Commit
```
feat(web): add dashboard page with stats (Phase 2)
```

---

## Phase 3: Listings Page with Filters

**Status:** `[ ]` Not Started

**Goal:** Full listings table with filtering, sorting, pagination

### Tasks

- [ ] **3.1** Create filter form component (`src/i4_scout/api/templates/components/filter_form.html`)
  - [ ] Source dropdown (All, AutoScout24 DE, AutoScout24 NL)
  - [ ] Qualified only checkbox
  - [ ] Min score input
  - [ ] Price min/max inputs
  - [ ] Mileage max input
  - [ ] Year min/max inputs
  - [ ] Country input
  - [ ] Search text input with debounce
  - [ ] Sort by dropdown (price, mileage, score, date)
  - [ ] Sort order dropdown (asc, desc)
  - [ ] Form uses `hx-get`, `hx-target`, `hx-push-url`

- [ ] **3.2** Create listing row component (`src/i4_scout/api/templates/components/listing_row.html`)
  - [ ] ID, title (truncated), price, mileage, score, qualified badge, source
  - [ ] Click opens detail modal via HTMX

- [ ] **3.3** Create pagination component (`src/i4_scout/api/templates/components/pagination.html`)
  - [ ] Previous/Next links with HTMX
  - [ ] Current page indicator
  - [ ] Total count display

- [ ] **3.4** Create listings table partial (`src/i4_scout/api/templates/partials/listings_table.html`)
  - [ ] Table with header row
  - [ ] Include listing rows
  - [ ] Include pagination
  - [ ] Empty state message

- [ ] **3.5** Create listings page (`src/i4_scout/api/templates/pages/listings.html`)
  - [ ] Extend base template
  - [ ] Include filter form
  - [ ] Listings table container
  - [ ] Detail modal (dialog element)
  - [ ] Script to open modal on HTMX swap

- [ ] **3.6** Implement listings page route (`src/i4_scout/api/routes/web.py`)
  - [ ] `GET /listings` - Render page with initial listings
  - [ ] Accept all filter query params
  - [ ] Pass current filters to template

- [ ] **3.7** Implement listings partial (`src/i4_scout/api/routes/partials.py`)
  - [ ] `GET /partials/listings` - Return table HTML fragment
  - [ ] Accept all filter query params
  - [ ] Return paginated results

### Verification
- [ ] `GET /listings` renders page with filter form
- [ ] Changing filters updates table without full reload
- [ ] URL updates with filter state
- [ ] Pagination works correctly
- [ ] Search debounces input
- [ ] Sorting works

### Commit
```
feat(web): add listings page with filters and pagination (Phase 3)
```

---

## Phase 4: Listing Detail View

**Status:** `[ ]` Not Started

**Goal:** Single listing detail with price history

### Tasks

- [ ] **4.1** Create price chart component (`src/i4_scout/api/templates/components/price_chart.html`)
  - [ ] Table with date, price, change columns
  - [ ] Calculate and display price changes
  - [ ] Empty state message

- [ ] **4.2** Create listing detail content (`src/i4_scout/api/templates/partials/listing_detail_content.html`)
  - [ ] Full title
  - [ ] Price, mileage, year
  - [ ] Location (city, country)
  - [ ] Dealer name and type
  - [ ] Match score and qualified status
  - [ ] Matched options list
  - [ ] First seen / last seen dates
  - [ ] Price history section (loads via HTMX)
  - [ ] External link to source
  - [ ] Delete button with confirmation

- [ ] **4.3** Create listing detail page (`src/i4_scout/api/templates/pages/listing_detail.html`)
  - [ ] Extend base template
  - [ ] Include detail content
  - [ ] Back to listings link

- [ ] **4.4** Implement detail page route (`src/i4_scout/api/routes/web.py`)
  - [ ] `GET /listings/{id}` - Render detail page
  - [ ] Handle 404 if not found

- [ ] **4.5** Implement detail partial (`src/i4_scout/api/routes/partials.py`)
  - [ ] `GET /partials/listing/{id}` - Return detail HTML fragment
  - [ ] For modal loading

- [ ] **4.6** Implement price chart partial (`src/i4_scout/api/routes/partials.py`)
  - [ ] `GET /partials/listing/{id}/price-chart` - Return price history HTML

### Verification
- [ ] `GET /listings/{id}` renders detail page
- [ ] Clicking listing row opens modal with detail
- [ ] Price history loads and displays correctly
- [ ] Delete button works with confirmation
- [ ] External link opens in new tab

### Commit
```
feat(web): add listing detail view with price history (Phase 4)
```

---

## Phase 5: Scrape Control Page

**Status:** `[ ]` Not Started

**Goal:** Start scrapes and monitor progress in real-time

### Tasks

- [ ] **5.1** Create scrape form component (`src/i4_scout/api/templates/components/scrape_form.html`)
  - [ ] Source dropdown
  - [ ] Max pages input
  - [ ] Submit button with loading indicator
  - [ ] Form posts to API with HTMX

- [ ] **5.2** Create scrape job row component (`src/i4_scout/api/templates/components/scrape_job_row.html`)
  - [ ] Job ID, source, status
  - [ ] Progress (current page) for running jobs
  - [ ] Counts: found, new, updated
  - [ ] Start time
  - [ ] Auto-poll running jobs via `hx-trigger="every 2s"`

- [ ] **5.3** Create scrape jobs list partial (`src/i4_scout/api/templates/partials/scrape_jobs_list.html`)
  - [ ] Table with header
  - [ ] Include job rows
  - [ ] Empty state message

- [ ] **5.4** Create scrape page (`src/i4_scout/api/templates/pages/scrape.html`)
  - [ ] Extend base template
  - [ ] Scrape form section
  - [ ] Result message area
  - [ ] Recent jobs section

- [ ] **5.5** Implement scrape page route (`src/i4_scout/api/routes/web.py`)
  - [ ] `GET /scrape` - Render scrape control page

- [ ] **5.6** Implement scrape partials (`src/i4_scout/api/routes/partials.py`)
  - [ ] `GET /partials/scrape/jobs` - Return jobs list HTML
  - [ ] `GET /partials/scrape/job/{id}` - Return single job row HTML

- [ ] **5.7** Modify scrape API for HTMX response (`src/i4_scout/api/routes/scrape.py`)
  - [ ] Check for `HX-Request` header
  - [ ] Return HTML success message for HTMX requests
  - [ ] Send `HX-Trigger: jobCreated` header to refresh list

### Verification
- [ ] `GET /scrape` renders scrape control page
- [ ] Form submits and shows success message
- [ ] Jobs list refreshes on new job
- [ ] Running jobs poll every 2 seconds
- [ ] Completed jobs show final counts
- [ ] Failed jobs show error indication

### Commit
```
feat(web): add scrape control page with live progress (Phase 5)
```

---

## Phase 6: Polish and Testing

**Status:** `[ ]` Not Started

**Goal:** Final touches, tests, documentation

### Tasks

- [ ] **6.1** Add loading indicators
  - [ ] Add `hx-indicator` to all HTMX requests
  - [ ] Create loading spinner CSS
  - [ ] Show indicators during requests

- [ ] **6.2** Add error handling
  - [ ] Handle API errors gracefully
  - [ ] Display error messages to user
  - [ ] Handle 404 pages

- [ ] **6.3** Mobile responsiveness
  - [ ] Test on mobile viewport
  - [ ] Ensure tables scroll horizontally
  - [ ] Adjust filter form layout for mobile

- [ ] **6.4** Dark mode toggle (optional)
  - [ ] Add toggle button in nav
  - [ ] Store preference in localStorage
  - [ ] Apply theme on load

- [ ] **6.5** Write integration tests (`tests/integration/test_web_routes.py`)
  - [ ] Test dashboard renders with stats
  - [ ] Test listings page renders with filters
  - [ ] Test listings partial returns HTML
  - [ ] Test detail page renders
  - [ ] Test scrape page renders
  - [ ] Test partials return correct content

- [ ] **6.6** Update documentation
  - [ ] Update `CLAUDE.md` with web interface section
  - [ ] Document routes and features
  - [ ] Add screenshots (optional)

### Verification
- [ ] All pages render correctly
- [ ] HTMX interactions work (filters, pagination, modals, polling)
- [ ] Mobile responsive
- [ ] All tests pass: `pytest tests/ -v`
- [ ] Lint passes: `ruff check src/`

### Commit
```
feat(web): complete web frontend with tests (Phase 6)
```

---

## File Reference

### Files to Create
| File | Phase | Description |
|------|-------|-------------|
| `src/i4_scout/static/css/pico.min.css` | 1 | Pico CSS framework |
| `src/i4_scout/static/css/custom.css` | 1 | Custom styles |
| `src/i4_scout/static/js/htmx.min.js` | 1 | HTMX library |
| `src/i4_scout/api/templates/base.html` | 1 | Base layout |
| `src/i4_scout/api/routes/web.py` | 1 | HTML page routes |
| `src/i4_scout/api/routes/partials.py` | 1 | HTMX partial routes |
| `src/i4_scout/api/templates/components/stats_cards.html` | 2 | Stats cards |
| `src/i4_scout/api/templates/components/listing_card.html` | 2 | Listing card |
| `src/i4_scout/api/templates/pages/dashboard.html` | 2 | Dashboard page |
| `src/i4_scout/api/templates/components/filter_form.html` | 3 | Filter form |
| `src/i4_scout/api/templates/components/listing_row.html` | 3 | Table row |
| `src/i4_scout/api/templates/components/pagination.html` | 3 | Pagination |
| `src/i4_scout/api/templates/partials/listings_table.html` | 3 | Listings table |
| `src/i4_scout/api/templates/pages/listings.html` | 3 | Listings page |
| `src/i4_scout/api/templates/components/price_chart.html` | 4 | Price history |
| `src/i4_scout/api/templates/partials/listing_detail_content.html` | 4 | Detail content |
| `src/i4_scout/api/templates/pages/listing_detail.html` | 4 | Detail page |
| `src/i4_scout/api/templates/components/scrape_form.html` | 5 | Scrape form |
| `src/i4_scout/api/templates/components/scrape_job_row.html` | 5 | Job row |
| `src/i4_scout/api/templates/partials/scrape_jobs_list.html` | 5 | Jobs list |
| `src/i4_scout/api/templates/pages/scrape.html` | 5 | Scrape page |
| `tests/integration/test_web_routes.py` | 6 | Web tests |

### Files to Modify
| File | Phase | Changes |
|------|-------|---------|
| `src/i4_scout/api/main.py` | 1 | Add templates, static, routers |
| `src/i4_scout/api/dependencies.py` | 1 | Add TemplatesDep |
| `src/i4_scout/api/routes/scrape.py` | 5 | HTMX response support |
| `CLAUDE.md` | 6 | Document web interface |

---

## HTMX Patterns Quick Reference

| Pattern | Code | Use Case |
|---------|------|----------|
| Load partial | `hx-get="/partials/x" hx-target="#y"` | Filters update table |
| On page load | `hx-trigger="load"` | Initial data fetch |
| Polling | `hx-trigger="every 2s"` | Scrape progress |
| URL state | `hx-push-url="true"` | Bookmarkable filters |
| Loading | `hx-indicator="#spinner"` | Show spinner |
| Replace self | `hx-swap="outerHTML"` | Update job row |
| Confirm | `hx-confirm="Delete?"` | Delete confirmation |
| Event trigger | Response header `HX-Trigger: event` | Refresh list |

---

## Session Handoff Notes

When resuming work:
1. Check this file for current status
2. Find the first `[ ]` Not Started phase
3. Work through tasks in order, marking `[x]` when complete
4. Run verification steps before committing
5. Update phase status to `[x]` Complete when done
