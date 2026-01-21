"""FastAPI dependency injection for database sessions and services."""

from collections.abc import Generator
from pathlib import Path
from typing import Annotated

from fastapi import Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from i4_scout.config import load_options_config, load_search_filters
from i4_scout.database.engine import get_session_factory
from i4_scout.models.pydantic_models import OptionsConfig, SearchFilters
from i4_scout.services.listing_service import ListingService

# Template directory path
TEMPLATES_DIR = Path(__file__).parent / "templates"


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


# Templates singleton (created once on first use)
_templates: Jinja2Templates | None = None


def get_templates() -> Jinja2Templates:
    """Dependency that provides Jinja2 templates.

    Returns:
        Jinja2Templates instance configured for this app.
    """
    global _templates
    if _templates is None:
        _templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    return _templates


# Type aliases for cleaner dependency injection
DbSession = Annotated[Session, Depends(get_db)]
ListingServiceDep = Annotated[ListingService, Depends(get_listing_service)]
OptionsConfigDep = Annotated[OptionsConfig, Depends(get_options_config)]
SearchFiltersDep = Annotated[SearchFilters, Depends(get_search_filters)]
TemplatesDep = Annotated[Jinja2Templates, Depends(get_templates)]
