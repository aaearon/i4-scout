"""Database engine and session management."""

from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from car_scraper.models.db_models import Base

# Default database path
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "car_scraper.db"

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine(db_path: Path | str | None = None, echo: bool = False) -> Engine:
    """Get or create the SQLAlchemy engine.

    Args:
        db_path: Path to SQLite database file. Defaults to data/car_scraper.db.
        echo: Whether to echo SQL statements.

    Returns:
        SQLAlchemy Engine instance.
    """
    global _engine

    if _engine is None:
        if db_path is None:
            db_path = DEFAULT_DB_PATH

        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        _engine = create_engine(
            f"sqlite:///{db_path}",
            echo=echo,
            connect_args={"check_same_thread": False},
        )

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

    Args:
        db_path: Path to SQLite database file.
        echo: Whether to echo SQL statements.

    Returns:
        SQLAlchemy Engine instance.
    """
    engine = get_engine(db_path, echo)
    Base.metadata.create_all(engine)
    return engine


def reset_engine() -> None:
    """Reset the global engine and session factory. Useful for testing."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
