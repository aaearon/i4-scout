# SQLite Database Retry Logic Implementation Plan

## Overview

Add retry logic for SQLite "database is locked" errors to handle concurrent database operations during web scraping.

## Status: COMPLETED

## Files Modified

| File | Change |
|------|--------|
| `src/i4_scout/database/engine.py` | Added SQLite busy timeout (30s) |
| `src/i4_scout/database/repository.py` | Added retry decorator, applied to 9 write methods |
| `tests/unit/test_repository_retry.py` | New file: tests for retry logic |
| `CLAUDE.md` | Updated architecture documentation |

## Implementation Details

### 1. Engine Changes (`engine.py`)

Added `timeout: 30` to `connect_args`:

```python
_engine = create_engine(
    f"sqlite:///{db_path}",
    echo=echo,
    connect_args={
        "check_same_thread": False,
        "timeout": 30,  # SQLite busy timeout in seconds
    },
)
```

### 2. Retry Decorator (`repository.py`)

Added imports and constants:

```python
import functools
from collections.abc import Callable
from typing import TypeVar

from sqlalchemy.exc import OperationalError
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from typing_extensions import ParamSpec

P = ParamSpec("P")
R = TypeVar("R")

# Retry configuration for database operations
DB_RETRY_MAX_ATTEMPTS = 5
DB_RETRY_WAIT_MIN = 1  # seconds
DB_RETRY_WAIT_MAX = 8  # seconds
DB_RETRY_WAIT_MULTIPLIER = 2
```

Added decorator:

```python
def with_db_retry(func: Callable[P, R]) -> Callable[P, R]:
    """Decorator to retry database operations on SQLite lock errors."""
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        for attempt in Retrying(
            retry=retry_if_exception_type(OperationalError),
            stop=stop_after_attempt(DB_RETRY_MAX_ATTEMPTS),
            wait=wait_exponential(
                multiplier=DB_RETRY_WAIT_MULTIPLIER,
                min=DB_RETRY_WAIT_MIN,
                max=DB_RETRY_WAIT_MAX,
            ),
            reraise=True,
        ):
            with attempt:
                return func(*args, **kwargs)
        raise RuntimeError("Retry logic failed unexpectedly")
    return wrapper
```

### 3. Methods Decorated with `@with_db_retry`

Applied to these 9 write methods in `ListingRepository`:

1. `create_listing()`
2. `bulk_create_listings()`
3. `update_listing()`
4. `delete_listing()`
5. `upsert_listing()`
6. `record_price_change()`
7. `add_option_to_listing()`
8. `clear_listing_options()`
9. `get_or_create_option()`

### 4. Tests (`tests/unit/test_repository_retry.py`)

Created 6 tests:

1. `test_retry_on_operational_error` - Verifies retries occur on OperationalError
2. `test_no_retry_on_other_exceptions` - Verifies non-retryable errors raise immediately
3. `test_max_retries_exhausted` - Verifies OperationalError raised after 5 attempts
4. `test_retry_count_matches_config` - Verifies exactly 5 calls on persistent failure
5. `test_preserves_function_metadata` - Verifies decorator preserves function metadata
6. `test_success_on_first_try` - Verifies immediate return on success

## Verification Results

```bash
# All 202 tests pass
pytest tests/ -v

# Retry-specific tests pass
pytest tests/unit/test_repository_retry.py -v
# 6 passed

# Lint passes for new code
ruff check src/i4_scout/database/repository.py tests/unit/test_repository_retry.py
# All checks passed!
```
