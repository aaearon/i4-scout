# Fix Delisting Bug and Photo Loading Issues

**Date:** 2026-01-23
**Status:** Implemented

## Summary of Issues Found

### Issue 1: Delisting Bug (CONFIRMED)
- **Evidence**: ALL 40 delisted listings had `consecutive_misses = 1` (not 2)
- **Expected**: Status should only be `DELISTED` when `consecutive_misses >= 2`
- **Root cause**: Stale object state in `scrape_service.py`

### Issue 2: Missing Photos
- 71/246 listings (29%) have photos, 175/246 (71%) have empty arrays
- Photo extraction code works correctly (tests pass)
- **Cause**: Detail pages skipped due to price-unchanged optimization (skip existing listings)

---

## Root Cause Analysis

The bug was in `_update_lifecycle_after_scrape()` in `scrape_service.py`:

```python
# Step 1: Fetch objects with CURRENT consecutive_misses values
active_listings = self._repo.get_active_listings_by_source(source)

# Step 2: DB updated (increments consecutive_misses)
self._repo.increment_consecutive_misses(unseen_active_ids)

# Step 3: Loop uses STALE objects (still have PRE-increment values)
for listing in active_listings:
    if listing.id in unseen_active_ids:
        if listing.consecutive_misses >= 1:  # STALE VALUE!
            self._repo.update_listing_status(listing.id, ListingStatus.DELISTED)
```

**The critical issue**: When `update_listing_status()` was called, it fetched the listing object from SQLAlchemy's identity map (which had the stale `consecutive_misses` value). When the status change was committed, SQLAlchemy wrote back ALL dirty attributes, including the stale `consecutive_misses = 1` value, overwriting the incremented value of 2.

---

## Fix 1: Atomic Database Operation

Added a new method `mark_listings_at_delist_threshold()` in `repository.py` that performs an atomic bulk update:

```python
@with_db_retry
def mark_listings_at_delist_threshold(self, listing_ids: list[int]) -> int:
    """Mark active listings with consecutive_misses >= 2 as delisted."""
    if not listing_ids:
        return 0

    now = datetime.now(timezone.utc)
    updated = (
        self._session.query(Listing)
        .filter(
            Listing.id.in_(listing_ids),
            Listing.consecutive_misses >= 2,
            Listing.status == ListingStatus.ACTIVE,
        )
        .update(
            {
                Listing.status: ListingStatus.DELISTED,
                Listing.status_changed_at: now,
            },
            synchronize_session=False,
        )
    )
    self._session.commit()
    return updated
```

This checks the ACTUAL database value of `consecutive_misses` rather than relying on stale session objects.

---

## Fix 2: Updated Scrape Service

Replaced the stale-object loop with a call to the atomic method:

```python
def _update_lifecycle_after_scrape(
    self, source: Source, seen_listing_ids: list[int]
) -> None:
    # ... (unchanged setup code)

    # Reset misses for seen listings
    self._repo.reset_consecutive_misses(list(seen_set))

    # Increment misses for unseen listings
    self._repo.increment_consecutive_misses(unseen_active_ids)

    # Mark listings as delisted if they've missed 2+ scrapes (atomic operation)
    delisted_count = self._repo.mark_listings_at_delist_threshold(unseen_active_ids)
    if delisted_count > 0:
        logger.info("Marked %d listings as delisted", delisted_count)
```

---

## Fix 3: Reset Incorrectly Delisted Listings

Ran one-time SQL fix to reset all 40 incorrectly delisted listings:

```sql
UPDATE listings
SET status = 'ACTIVE', consecutive_misses = 0
WHERE status = 'DELISTED';
```

---

## Fix 4: Photos for Existing Listings

Photos were missing because the scraper skips detail pages for existing listings if the price hasn't changed (optimization). To backfill photos:

```bash
i4-scout scrape autoscout24_de --force-refresh
i4-scout scrape autoscout24_nl --force-refresh
```

---

## Files Modified

- `src/i4_scout/database/repository.py` - Added `mark_listings_at_delist_threshold()`
- `src/i4_scout/services/scrape_service.py` - Updated `_update_lifecycle_after_scrape()`
- `tests/unit/test_repository_lifecycle.py` - Added tests for new method
- `tests/unit/test_scrape_service_lifecycle.py` - Updated tests for new behavior

---

## Verification

### Test Results
All 26 lifecycle-related tests pass:
- `TestMarkListingsAtDelistThreshold::test_marks_listings_with_two_misses` - Verifies 2 misses triggers delist
- `TestMarkListingsAtDelistThreshold::test_does_not_mark_listings_with_one_miss` - Verifies 1 miss doesn't delist
- `TestMarkListingsAtDelistThreshold::test_atomic_operation_preserves_consecutive_misses` - Key test for bug fix

### Manual Verification Steps
1. Run scrape → verify new listings tracked
2. Run scrape with listing absent → `consecutive_misses = 1`, status = ACTIVE
3. Run scrape 3rd time with listing absent → `consecutive_misses = 2`, status = DELISTED
4. Verify `consecutive_misses = 2` (not 1) after delisting
