"""Base scraper for AutoScout24 sites (DE/NL share same DOM structure)."""

import re
from abc import abstractmethod
from typing import Any, ClassVar

from bs4 import BeautifulSoup

from car_scraper.models.pydantic_models import ScrapedListing, Source
from car_scraper.scrapers.base import BaseScraper


class AutoScout24BaseScraper(BaseScraper):
    """Shared scraper logic for AutoScout24 DE and NL sites.

    Subclasses must set:
    - source: Source enum value
    - BASE_URL: Site base URL (e.g., "https://www.autoscout24.de")
    - SEARCH_PATH: Search path (e.g., "/lst/bmw/i4")
    - LOCALE: Locale code (e.g., "de-DE")

    The DOM structure is identical between DE and NL sites, only URLs differ.
    """

    # Class-level configuration - must be set by subclasses
    BASE_URL: ClassVar[str]
    SEARCH_PATH: ClassVar[str]
    LOCALE: ClassVar[str]

    # Equipment category labels to look for
    EQUIPMENT_CATEGORIES: ClassVar[list[str]] = [
        "Komfort",
        "Comfort",
        "Unterhaltung/Media",
        "Entertainment",
        "Sicherheit",
        "Safety",
        "Extras",
    ]

    def get_search_url(self, page: int = 1) -> str:
        """Generate search URL for the given page number.

        Args:
            page: Page number (1-indexed).

        Returns:
            Full URL for the search results page.
        """
        return self.get_search_url_static(page)

    @classmethod
    def get_search_url_static(cls, page: int = 1) -> str:
        """Static method for search URL generation (usable without instance).

        Args:
            page: Page number (1-indexed).

        Returns:
            Full URL for the search results page.
        """
        # AutoScout24 uses page parameter in URL
        params = [
            "atype=C",  # Car type
            "cy=D" if "de" in cls.BASE_URL else "cy=NL",  # Country
            "desc=0",  # Sort order
            "fregfrom=2022",  # First registration from
            f"page={page}",
            "sort=standard",
            "ustate=N%2CU",  # Used/New state
        ]
        return f"{cls.BASE_URL}{cls.SEARCH_PATH}?{'&'.join(params)}"

    async def parse_listing_cards(self, html: str) -> list[dict[str, Any]]:
        """Parse listing cards from search results HTML.

        Args:
            html: Raw HTML content of search results page.

        Returns:
            List of dicts with basic listing info.
        """
        return self.parse_listing_cards_sync(html)

    @classmethod
    def parse_listing_cards_sync(cls, html: str) -> list[dict[str, Any]]:
        """Synchronous parsing of listing cards (for testing).

        Extracts from <article> elements with data attributes:
        - data-guid → external_id
        - data-price → price (int, EUR)
        - data-mileage → mileage_km
        - data-first-registration → first_registration (MM/YYYY)
        - href containing /angebote/ or /aanbod/ → url
        - h2 text → title

        Args:
            html: Raw HTML content of search results page.

        Returns:
            List of dicts with basic listing info.
        """
        soup = BeautifulSoup(html, "html.parser")
        listings: list[dict[str, Any]] = []

        # Find all article elements with data-guid (listing cards)
        articles = soup.find_all("article", attrs={"data-guid": True})

        for article in articles:
            listing = cls._parse_article(article)
            if listing:
                listings.append(listing)

        return listings

    @classmethod
    def _parse_article(cls, article: Any) -> dict[str, Any] | None:
        """Parse a single article element into listing data.

        Args:
            article: BeautifulSoup article element.

        Returns:
            Dict with listing data or None if parsing fails.
        """
        try:
            # Extract data attributes
            external_id = article.get("data-guid")
            if not external_id:
                return None

            # Price from data attribute (already in EUR)
            price_str = article.get("data-price", "")
            price = int(price_str) if price_str and price_str.isdigit() else None

            # Mileage from data attribute
            mileage_str = article.get("data-mileage", "")
            mileage_km = int(mileage_str) if mileage_str and mileage_str.isdigit() else None

            # First registration - format "MM-YYYY" to "MM/YYYY"
            first_reg = article.get("data-first-registration", "")
            if first_reg and first_reg != "new":
                first_registration = first_reg.replace("-", "/")
            elif first_reg == "new":
                first_registration = "new"
            else:
                first_registration = None

            # Find URL from anchor tag (check both href and data-href attributes)
            url = None
            href = None
            # First try href attribute
            link = article.find("a", href=re.compile(r"/angebote/|/aanbod/"))
            if link and link.get("href"):
                href = link["href"]
            else:
                # Fall back to data-href attribute (AutoScout24 uses this for JS navigation)
                link = article.find("a", attrs={"data-href": re.compile(r"/angebote/|/aanbod/")})
                href = link.get("data-href") if link else None

            if href:
                # Make absolute URL if needed
                if href.startswith("/"):
                    url = f"{cls.BASE_URL}{href}"
                elif href.startswith("http"):
                    url = href
                else:
                    url = f"{cls.BASE_URL}/{href}"
            elif external_id:
                # Construct URL from GUID - AutoScout24 accepts /angebote/-{guid} format
                # Determine path based on locale (DE: angebote, NL: aanbod)
                path = "aanbod" if "autoscout24.nl" in cls.BASE_URL else "angebote"
                url = f"{cls.BASE_URL}/{path}/-{external_id}"

            # Find title from h2
            h2 = article.find("h2")
            title = h2.get_text(strip=True) if h2 else ""

            return {
                "external_id": external_id,
                "url": url,
                "title": title,
                "price": price,
                "mileage_km": mileage_km,
                "first_registration": first_registration,
                "source": cls.source if hasattr(cls, "source") else None,
            }

        except Exception:
            return None

    async def parse_listing_detail(self, html: str, url: str) -> ScrapedListing:
        """Parse full listing details from detail page HTML.

        Args:
            html: Raw HTML content of listing detail page.
            url: URL of the listing.

        Returns:
            ScrapedListing with all extracted data.
        """
        options = self.parse_options_sync(html)
        description = self.parse_description_sync(html)
        soup = BeautifulSoup(html, "html.parser")

        # Extract basic info from detail page
        title = ""
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)

        # Extract price
        price = None
        price_elem = soup.find(class_=re.compile(r"Price|price"))
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            # Extract numeric value
            price_match = re.search(r"[\d.]+", price_text.replace(".", ""))
            if price_match:
                price = int(price_match.group())

        return ScrapedListing(
            source=self.source,
            url=url,
            title=title,
            price=price,
            options_list=options,
            description=description,
        )

    @classmethod
    def parse_options_sync(cls, html: str) -> list[str]:
        """Extract options/equipment from detail page HTML.

        Looks for equipment sections (Komfort, Sicherheit, etc.) and extracts
        individual option names from ul/li elements within DataGrid structure.

        Args:
            html: Raw HTML content of detail page.

        Returns:
            List of option names (strings).
        """
        soup = BeautifulSoup(html, "html.parser")
        options: list[str] = []

        # Find all dd elements with DataGrid class containing option lists
        dd_elements = soup.find_all("dd", class_=re.compile(r"DataGrid_defaultDdStyle"))

        for dd in dd_elements:
            # Check if this dd contains a ul with options
            ul = dd.find("ul")
            if ul:
                # Get corresponding dt to check if it's an equipment category
                dt = dd.find_previous_sibling("dt")
                if dt:
                    label = dt.get_text(strip=True)
                    # Only process equipment-related sections
                    if any(cat in label for cat in cls.EQUIPMENT_CATEGORIES):
                        # Extract all li text
                        lis = ul.find_all("li", recursive=False)
                        for li in lis:
                            option_text = li.get_text(strip=True)
                            if option_text:
                                options.append(option_text)

        return options

    @classmethod
    def parse_description_sync(cls, html: str) -> str | None:
        """Extract vehicle description (Fahrzeugbeschreibung) from detail page.

        This section often contains detailed option codes and equipment info
        that dealers add manually.

        Args:
            html: Raw HTML content of detail page.

        Returns:
            Description text or None if not found.
        """
        soup = BeautifulSoup(html, "html.parser")

        # Look for Fahrzeugbeschreibung section (German: "Fahrzeugbeschreibung")
        # or "Description" in English/Dutch
        description_labels = [
            "Fahrzeugbeschreibung",
            "Beschreibung",
            "Description",
            "Omschrijving",
            "Voertuigomschrijving",
        ]

        # Method 1: Find by dt/dd structure with label
        for label in description_labels:
            dt = soup.find("dt", string=re.compile(label, re.IGNORECASE))
            if dt:
                dd = dt.find_next_sibling("dd")
                if dd:
                    return dd.get_text(separator="\n", strip=True)

        # Method 2: Find by class name patterns
        desc_patterns = [
            r"Description",
            r"VehicleDescription",
            r"description",
            r"seller-notes",
        ]
        for pattern in desc_patterns:
            desc_elem = soup.find(class_=re.compile(pattern, re.IGNORECASE))
            if desc_elem:
                text = desc_elem.get_text(separator="\n", strip=True)
                if len(text) > 50:  # Only return if substantial content
                    return text

        # Method 3: Look for data-testid attributes
        desc_elem = soup.find(attrs={"data-testid": re.compile(r"description", re.IGNORECASE)})
        if desc_elem:
            return desc_elem.get_text(separator="\n", strip=True)

        return None

    @property
    @abstractmethod
    def source(self) -> Source:
        """Return the Source enum value for this scraper."""
        ...
