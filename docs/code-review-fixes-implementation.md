# Code Review Fixes Implementation

## Summary

Fixed all 6 issues identified in the AI code review of dashboard widget enhancements.

## Changes Made

### 1. Missing JavaScript Dependency (CRITICAL) - FIXED

**File:** `src/i4_scout/api/templates/base.html`

Added `favorites.js` to the base template so `toggleFavorite()` is available globally on all pages including the dashboard.

### 2. Encapsulation Violation (HIGH) - FIXED

**Files:**
- `src/i4_scout/services/listing_service.py`
- `src/i4_scout/api/routes/partials.py`

Renamed `_to_listing_read` to `to_listing_read` (removed underscore prefix) to indicate it's part of the public API. Updated all 4 call sites in partials.py.

### 3. Negative Hours Edge Case (MEDIUM) - FIXED

**File:** `src/i4_scout/api/templates/macros.html`

The widget_icons macro includes the `>= 0` check in the condition:
```jinja2
{% if change_hours_ago >= 0 and change_hours_ago < 24 %}
```

### 4. Deprecated datetime.utcnow() (MEDIUM) - FIXED

**File:** `src/i4_scout/api/routes/partials.py`

Replaced `datetime.utcnow()` with `datetime.now(timezone.utc)` at lines 272, 774, and 808.

**Additional fix:** Updated `listing_service.py` to make `last_price_change_at` timezone-aware by calling `replace(tzinfo=timezone.utc)` on the naive datetime from SQLite.

### 5. Widget Icons Macro (LOW) - FIXED

**New file:** `src/i4_scout/api/templates/macros.html`

Created a centralized macros file with `widget_icons` macro that includes all status icons (delisted, issue, updated, document, notes).

**Updated files:**
- `src/i4_scout/api/templates/components/near_miss.html`
- `src/i4_scout/api/templates/components/price_drops.html`

Both templates now import and use the macro instead of duplicating the icon HTML.

### 6. Hardcoded Popover Width (LOW) - FIXED

**File:** `src/i4_scout/api/templates/pages/dashboard.html`

Extracted the magic number `400` to a `NOTES_POPOVER_WIDTH` constant at the top of the script.

## Files Modified

| File | Action |
|------|--------|
| `src/i4_scout/api/templates/base.html` | Add favorites.js script |
| `src/i4_scout/services/listing_service.py` | Rename method, add timezone handling |
| `src/i4_scout/api/routes/partials.py` | Update method calls, fix datetime import |
| `src/i4_scout/api/templates/macros.html` | **NEW** - Create macros file |
| `src/i4_scout/api/templates/components/near_miss.html` | Use macro |
| `src/i4_scout/api/templates/components/price_drops.html` | Use macro |
| `src/i4_scout/api/templates/pages/dashboard.html` | Extract popover width constant |

## Verification

All checks pass:
- `ruff check` - All checks passed
- `mypy` - Success: no issues found
- `pytest tests/ -v -k "partial or dashboard"` - 55 passed
