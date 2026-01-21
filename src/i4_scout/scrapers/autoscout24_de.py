"""AutoScout24 Germany scraper implementation."""

from typing import ClassVar

from i4_scout.models.pydantic_models import Source
from i4_scout.scrapers.autoscout24_base import AutoScout24BaseScraper


class AutoScout24DEScraper(AutoScout24BaseScraper):
    """Scraper for autoscout24.de (German market).

    Thin configuration wrapper around AutoScout24BaseScraper.
    All parsing logic is inherited from the base class.
    """

    BASE_URL: ClassVar[str] = "https://www.autoscout24.de"
    SEARCH_PATH: ClassVar[str] = "/lst/bmw/i4"
    LOCALE: ClassVar[str] = "de-DE"

    @property
    def source(self) -> Source:  # type: ignore[override]
        """Return the Source enum value for German AutoScout24."""
        return Source.AUTOSCOUT24_DE
