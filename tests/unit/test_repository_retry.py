"""Tests for database retry logic."""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import OperationalError

from i4_scout.database.repository import (
    DB_RETRY_MAX_ATTEMPTS,
    with_db_retry,
)


class TestWithDbRetry:
    """Tests for the with_db_retry decorator."""

    def test_retry_on_operational_error(self) -> None:
        """Verify retries occur on OperationalError and succeeds after transient failure."""
        mock_func = MagicMock()
        # Fail twice, then succeed
        mock_func.side_effect = [
            OperationalError("database is locked", None, None),
            OperationalError("database is locked", None, None),
            "success",
        ]

        @with_db_retry
        def decorated_func() -> str:
            return mock_func()

        with patch("i4_scout.database.repository.wait_exponential", return_value=0):
            result = decorated_func()

        assert result == "success"
        assert mock_func.call_count == 3

    def test_no_retry_on_other_exceptions(self) -> None:
        """Verify non-retryable errors raise immediately without retry."""
        mock_func = MagicMock()
        mock_func.side_effect = ValueError("some other error")

        @with_db_retry
        def decorated_func() -> str:
            return mock_func()

        with pytest.raises(ValueError, match="some other error"):
            decorated_func()

        # Should only be called once (no retry)
        assert mock_func.call_count == 1

    def test_max_retries_exhausted(self) -> None:
        """Verify OperationalError raised after max failed attempts."""
        mock_func = MagicMock()
        # Always fail with OperationalError
        mock_func.side_effect = OperationalError("database is locked", None, None)

        @with_db_retry
        def decorated_func() -> str:
            return mock_func()

        with (
            patch("i4_scout.database.repository.wait_exponential", return_value=0),
            pytest.raises(OperationalError),
        ):
            decorated_func()

        assert mock_func.call_count == DB_RETRY_MAX_ATTEMPTS

    def test_retry_count_matches_config(self) -> None:
        """Verify exactly DB_RETRY_MAX_ATTEMPTS calls made on persistent failure."""
        call_count = 0

        @with_db_retry
        def decorated_func() -> str:
            nonlocal call_count
            call_count += 1
            raise OperationalError("database is locked", None, None)

        with (
            patch("i4_scout.database.repository.wait_exponential", return_value=0),
            pytest.raises(OperationalError),
        ):
            decorated_func()

        assert call_count == DB_RETRY_MAX_ATTEMPTS

    def test_preserves_function_metadata(self) -> None:
        """Verify decorator preserves original function metadata."""

        @with_db_retry
        def my_function() -> str:
            """My docstring."""
            return "result"

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."

    def test_success_on_first_try(self) -> None:
        """Verify function returns immediately on success without retry."""
        mock_func = MagicMock(return_value="success")

        @with_db_retry
        def decorated_func() -> str:
            return mock_func()

        result = decorated_func()

        assert result == "success"
        assert mock_func.call_count == 1
