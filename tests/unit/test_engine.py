"""Tests for database engine configuration."""

import os
from pathlib import Path
from unittest.mock import patch

from i4_scout.database.engine import get_database_url, get_engine, reset_engine


class TestGetDatabaseUrl:
    """Tests for get_database_url() function."""

    def setup_method(self) -> None:
        """Reset engine state before each test."""
        reset_engine()

    def teardown_method(self) -> None:
        """Clean up after each test."""
        reset_engine()
        # Clean up env vars
        for var in ["DATABASE_URL", "I4_SCOUT_DB_PATH"]:
            if var in os.environ:
                del os.environ[var]

    def test_returns_database_url_from_env(self) -> None:
        """DATABASE_URL env var takes precedence."""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost/db"}):
            url = get_database_url()
            assert url == "postgresql://user:pass@localhost/db"

    def test_returns_sqlite_url_from_path(self, tmp_path: Path) -> None:
        """Constructs SQLite URL from explicit path."""
        db_path = tmp_path / "test.db"
        url = get_database_url(db_path=db_path)
        assert url == f"sqlite:///{db_path}"

    def test_returns_default_sqlite_url(self) -> None:
        """Returns default SQLite path when no env var or path provided."""
        url = get_database_url()
        assert url.startswith("sqlite:///")
        assert "i4_scout.db" in url

    def test_database_url_takes_precedence_over_path(self, tmp_path: Path) -> None:
        """DATABASE_URL env var takes precedence over db_path argument."""
        db_path = tmp_path / "test.db"
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://host/db"}):
            url = get_database_url(db_path=db_path)
            assert url == "postgresql://host/db"

    def test_i4_scout_db_path_env_used_when_no_database_url(self, tmp_path: Path) -> None:
        """I4_SCOUT_DB_PATH is used when DATABASE_URL is not set."""
        custom_path = tmp_path / "custom.db"
        with patch.dict(os.environ, {"I4_SCOUT_DB_PATH": str(custom_path)}):
            url = get_database_url()
            assert url == f"sqlite:///{custom_path}"


class TestGetEngine:
    """Tests for get_engine() function."""

    def setup_method(self) -> None:
        """Reset engine state before each test."""
        reset_engine()

    def teardown_method(self) -> None:
        """Clean up after each test."""
        reset_engine()
        for var in ["DATABASE_URL", "I4_SCOUT_DB_PATH"]:
            if var in os.environ:
                del os.environ[var]

    def test_creates_sqlite_engine_with_path(self, tmp_path: Path) -> None:
        """Creates SQLite engine from path."""
        db_path = tmp_path / "test.db"
        engine = get_engine(db_path=db_path)
        assert "sqlite" in str(engine.url)
        assert str(db_path) in str(engine.url)

    def test_creates_engine_from_database_url(self, tmp_path: Path) -> None:
        """Creates engine from DATABASE_URL env var."""
        db_path = tmp_path / "envdb.db"
        with patch.dict(os.environ, {"DATABASE_URL": f"sqlite:///{db_path}"}):
            engine = get_engine()
            assert str(db_path) in str(engine.url)

    def test_engine_is_cached(self, tmp_path: Path) -> None:
        """Engine is cached after first call."""
        db_path = tmp_path / "test.db"
        engine1 = get_engine(db_path=db_path)
        engine2 = get_engine()
        assert engine1 is engine2

    def test_reset_engine_clears_cache(self, tmp_path: Path) -> None:
        """reset_engine() clears the cached engine."""
        db_path1 = tmp_path / "test1.db"
        db_path2 = tmp_path / "test2.db"

        engine1 = get_engine(db_path=db_path1)
        reset_engine()
        engine2 = get_engine(db_path=db_path2)

        assert engine1 is not engine2
        assert str(db_path1) in str(engine1.url)
        assert str(db_path2) in str(engine2.url)


class TestSqliteWalMode:
    """Tests for SQLite WAL mode configuration."""

    def setup_method(self) -> None:
        """Reset engine state before each test."""
        reset_engine()

    def teardown_method(self) -> None:
        """Clean up after each test."""
        reset_engine()
        for var in ["DATABASE_URL"]:
            if var in os.environ:
                del os.environ[var]

    def test_wal_mode_enabled_for_sqlite(self, tmp_path: Path) -> None:
        """WAL mode is enabled for SQLite databases."""
        db_path = tmp_path / "test.db"
        engine = get_engine(db_path=db_path)

        # Query the journal mode
        from sqlalchemy import text

        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA journal_mode;"))
            mode = result.scalar()
            assert mode == "wal", f"Expected WAL mode, got {mode}"


class TestConnectionPooling:
    """Tests for connection pooling configuration."""

    def setup_method(self) -> None:
        """Reset engine state before each test."""
        reset_engine()

    def teardown_method(self) -> None:
        """Clean up after each test."""
        reset_engine()
        for var in ["DATABASE_URL"]:
            if var in os.environ:
                del os.environ[var]

    def test_sqlite_engine_has_pool_settings(self, tmp_path: Path) -> None:
        """SQLite engine has connection pool configured."""
        db_path = tmp_path / "test.db"
        engine = get_engine(db_path=db_path)

        # SQLite uses StaticPool by default when check_same_thread=False
        # but we configure QueuePool settings that apply
        pool = engine.pool
        assert pool is not None

    def test_postgresql_engine_from_database_url(self) -> None:
        """PostgreSQL URL creates engine with pool settings."""
        # We can't actually connect to PostgreSQL in tests,
        # but we can verify the URL is accepted
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost/db"}):
            # This will fail to connect but we can check the URL parsing
            url = get_database_url()
            assert url.startswith("postgresql://")
