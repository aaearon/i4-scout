"""FastAPI dependency injection for database sessions and services."""

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from i4_scout.config import load_options_config, load_search_filters
from i4_scout.database.engine import get_session_factory
from i4_scout.models.pydantic_models import OptionsConfig, SearchFilters
from i4_scout.services.listing_service import ListingService


def get_db() -> Generator[Session, None, None]:
    """Dependency that provides a database session.

    Yields:
        Database session that is automatically closed after use.
    """
    session_factory = get_session_factory()
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def get_listing_service(
    session: Annotated[Session, Depends(get_db)],
) -> ListingService:
    """Dependency that provides a ListingService instance.

    Args:
        session: Database session from get_db dependency.

    Returns:
        ListingService instance.
    """
    return ListingService(session)


def get_options_config() -> OptionsConfig:
    """Dependency that provides the options configuration.

    Returns:
        Loaded OptionsConfig from config file.
    """
    return load_options_config()


def get_search_filters() -> SearchFilters:
    """Dependency that provides search filters configuration.

    Returns:
        Loaded SearchFilters from config file.
    """
    return load_search_filters()


# Type aliases for cleaner dependency injection
DbSession = Annotated[Session, Depends(get_db)]
ListingServiceDep = Annotated[ListingService, Depends(get_listing_service)]
OptionsConfigDep = Annotated[OptionsConfig, Depends(get_options_config)]
SearchFiltersDep = Annotated[SearchFilters, Depends(get_search_filters)]
