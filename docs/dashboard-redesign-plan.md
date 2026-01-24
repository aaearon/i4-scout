# Dashboard Redesign Implementation Plan

## Overview

Redesigned the dashboard from static aggregate statistics to an actionable, insight-driven interface with:

1. **Market Pulse** - 7-day velocity showing new/delisted/net listings
2. **Price Drops** - Buying opportunities with recent price reductions
3. **Near-Miss Listings** - High-score listings close to qualifying
4. **Feature Rarity** - Which options are hardest to find
5. **Your Favorites** - Status of starred listings

## Implementation

### Repository Methods Added

Located in `src/i4_scout/database/repository.py`:

- `get_listings_with_price_drops(days=7, limit=10)` - Returns listings with current price lower than original
- `get_near_miss_listings(threshold=80.0, limit=10)` - Returns unqualified listings with high scores
- `get_market_velocity(days=7)` - Returns new/delisted/net counts plus active and qualified totals
- `get_option_frequency(status=ACTIVE)` - Returns option counts and percentages across listings

### Partial Endpoints Added

Located in `src/i4_scout/api/routes/partials.py`:

- `GET /partials/market-velocity` - Market pulse widget
- `GET /partials/price-drops` - Price drops widget
- `GET /partials/near-miss` - Near-miss listings widget
- `GET /partials/feature-rarity` - Feature rarity widget
- `GET /partials/favorites` - Favorites widget (loads from localStorage IDs)

### Widget Templates Created

Located in `src/i4_scout/api/templates/components/`:

- `market_velocity.html` - 3-stat grid (new/delisted/net) + active/qualified totals
- `price_drops.html` - List of price drop items with original/current prices
- `near_miss.html` - List of high-score unqualified listings with missing options
- `feature_rarity.html` - Bar charts showing rarest and most common options
- `favorites.html` - List of favorited listings with status indicators

### CSS Styles Added

Located in `src/i4_scout/static/css/custom.css`:

- Widget base styles (header, footer, empty state)
- Dashboard grid layout (2-column responsive)
- Market velocity stats cards
- Price drops list styling
- Near-miss listing cards
- Feature rarity bar charts
- Favorites list styling

### Dashboard Template Updated

Located in `src/i4_scout/api/templates/pages/dashboard.html`:

- Full-width Market Pulse widget at top
- 2-column grid with Price Drops, Near-Miss, Feature Rarity, Favorites
- HTMX-powered lazy loading for all widgets
- JavaScript to load favorites from localStorage and fetch details

## Testing

### Unit Tests

File: `tests/unit/test_repository_dashboard.py`

- TestGetListingsWithPriceDrops (4 tests)
- TestGetNearMissListings (5 tests)
- TestGetMarketVelocity (4 tests)
- TestGetOptionFrequency (4 tests)

### Integration Tests

File: `tests/integration/test_dashboard_partials.py`

- TestMarketVelocityPartial (3 tests)
- TestPriceDropsPartial (3 tests)
- TestNearMissPartial (4 tests)
- TestFeatureRarityPartial (3 tests)
- TestFavoritesPartial (5 tests)

## Files Modified

| File | Changes |
|------|---------|
| `src/i4_scout/database/repository.py` | Added 4 dashboard query methods |
| `src/i4_scout/api/routes/partials.py` | Added 5 partial endpoints |
| `src/i4_scout/api/templates/pages/dashboard.html` | Complete redesign |
| `src/i4_scout/api/templates/components/*.html` | 5 new widget templates |
| `src/i4_scout/static/css/custom.css` | Widget styling |
| `CLAUDE.md` | Updated documentation |
| `tests/unit/test_repository_dashboard.py` | New file with 17 tests |
| `tests/integration/test_dashboard_partials.py` | New file with 18 tests |

## Verification

```bash
# Run unit tests
pytest tests/unit/test_repository_dashboard.py -v

# Run integration tests
pytest tests/integration/test_dashboard_partials.py -v

# Run linting
ruff check src/i4_scout/database/repository.py src/i4_scout/api/routes/partials.py

# Run type checking
mypy src/i4_scout/database/repository.py src/i4_scout/api/routes/partials.py --ignore-missing-imports

# Manual verification
i4-scout serve --reload
# Navigate to http://localhost:8000/
```
