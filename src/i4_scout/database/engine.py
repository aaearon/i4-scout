"""Database engine and session management."""

import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from i4_scout.models.db_models import Base

# Default database path
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "i4_scout.db"


def _get_db_path() -> Path:
    """Get database path from environment variable or default."""
    env_path = os.environ.get("I4_SCOUT_DB_PATH")
    if env_path:
        return Path(env_path)
    return DEFAULT_DB_PATH


def get_database_url(db_path: Path | None = None) -> str:
    """Get database URL from environment or construct from path.

    Args:
        db_path: Optional path to SQLite database file.

    Returns:
        Database URL string (e.g., "sqlite:///..." or "postgresql://...").

    Priority:
        1. DATABASE_URL environment variable (for PostgreSQL/external databases)
        2. Explicit db_path argument
        3. I4_SCOUT_DB_PATH environment variable
        4. Default path (data/i4_scout.db)
    """
    if url := os.environ.get("DATABASE_URL"):
        return url
    path = db_path or _get_db_path()
    return f"sqlite:///{path}"


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine(db_path: Path | str | None = None, echo: bool = False) -> Engine:
    """Get or create the SQLAlchemy engine.

    Args:
        db_path: Path to SQLite database file. Defaults to data/i4_scout.db.
        echo: Whether to echo SQL statements.

    Returns:
        SQLAlchemy Engine instance.

    Features:
        - Supports DATABASE_URL env var for PostgreSQL/external databases
        - Enables WAL mode for SQLite (better concurrent access)
        - Configures connection pooling
        - Auto-creates tables on first use (idempotent)
    """
    global _engine

    if _engine is None:
        # Convert db_path to Path if provided as string
        path_obj = Path(db_path) if db_path else None

        # Get database URL (checks DATABASE_URL env var first)
        database_url = get_database_url(db_path=path_obj)

        # Configure connection args based on database type
        connect_args: dict[str, object] = {}
        if database_url.startswith("sqlite"):
            connect_args = {
                "check_same_thread": False,
                "timeout": 30,  # SQLite busy timeout in seconds
            }
            # Ensure parent directory exists for SQLite
            if path_obj is None and not os.environ.get("DATABASE_URL"):
                path_obj = _get_db_path()
            if path_obj:
                path_obj.parent.mkdir(parents=True, exist_ok=True)

        # Create engine with connection pooling settings
        # Note: pool_size and pool_recycle are only applicable to pool-based engines
        # SQLite with check_same_thread=False uses NullPool by default
        engine_kwargs: dict[str, object] = {
            "echo": echo,
        }

        if connect_args:
            engine_kwargs["connect_args"] = connect_args

        # Add pool settings for non-SQLite databases
        if not database_url.startswith("sqlite"):
            engine_kwargs["pool_size"] = 5
            engine_kwargs["pool_recycle"] = 3600

        _engine = create_engine(database_url, **engine_kwargs)

        # Enable WAL mode for SQLite (better concurrent read/write access)
        if database_url.startswith("sqlite"):
            with _engine.connect() as conn:
                conn.execute(text("PRAGMA journal_mode=WAL"))
                conn.commit()

        # Auto-create tables (idempotent - safe to call on every startup)
        Base.metadata.create_all(_engine)

    return _engine


def get_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    """Get or create the session factory.

    Args:
        engine: SQLAlchemy engine. If None, uses default engine.

    Returns:
        Session factory.
    """
    global _SessionLocal

    if _SessionLocal is None:
        if engine is None:
            engine = get_engine()
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    return _SessionLocal


@contextmanager
def get_session(engine: Engine | None = None) -> Generator[Session, None, None]:
    """Get a database session as a context manager.

    Args:
        engine: SQLAlchemy engine. If None, uses default engine.

    Yields:
        Database session.
    """
    session_factory = get_session_factory(engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def init_db(db_path: Path | str | None = None, echo: bool = False) -> Engine:
    """Initialize the database, creating all tables.

    Note: This is now just an alias for get_engine(), which auto-creates
    tables on first use. Kept for backwards compatibility with tests.

    Args:
        db_path: Path to SQLite database file.
        echo: Whether to echo SQL statements.

    Returns:
        SQLAlchemy Engine instance.
    """
    return get_engine(db_path, echo)


def reset_engine() -> None:
    """Reset the global engine and session factory. Useful for testing."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
