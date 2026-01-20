"""AutoScout24 Netherlands scraper implementation."""

from typing import ClassVar

from car_scraper.models.pydantic_models import Source
from car_scraper.scrapers.autoscout24_base import AutoScout24BaseScraper


class AutoScout24NLScraper(AutoScout24BaseScraper):
    """Scraper for autoscout24.nl (Dutch market).

    Thin configuration wrapper around AutoScout24BaseScraper.
    All parsing logic is inherited from the base class.
    """

    BASE_URL: ClassVar[str] = "https://www.autoscout24.nl"
    SEARCH_PATH: ClassVar[str] = "/lst/bmw/i4"
    LOCALE: ClassVar[str] = "nl-NL"

    @property
    def source(self) -> Source:
        """Return the Source enum value for Dutch AutoScout24."""
        return Source.AUTOSCOUT24_NL
