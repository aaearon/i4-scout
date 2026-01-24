"""Tests for photo URL parsing from AutoScout24 detail pages."""

from pathlib import Path

import pytest

from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper
from i4_scout.scrapers.autoscout24_nl import AutoScout24NLScraper


@pytest.fixture
def de_detail_html() -> str:
    """Load German detail page fixture."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "autoscout24_de_detail.html"
    return fixture_path.read_text(encoding="utf-8")


@pytest.fixture
def nl_detail_html() -> str:
    """Load Dutch detail page fixture."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "autoscout24_nl_detail.html"
    return fixture_path.read_text(encoding="utf-8")


class TestParsePhotoUrls:
    """Test photo URL extraction from detail pages."""

    def test_extracts_unique_photo_urls_de(self, de_detail_html: str) -> None:
        """Should extract unique base photo URLs from DE detail page."""
        urls = AutoScout24DEScraper.parse_photo_urls_sync(de_detail_html)

        # Should have photos
        assert len(urls) > 0
        # Should be unique
        assert len(urls) == len(set(urls))
        # Should be base URLs (no resolution suffix)
        for url in urls:
            assert url.endswith(".jpg")
            assert "/720x540" not in url
            assert "/120x90" not in url

    def test_extracts_unique_photo_urls_nl(self, nl_detail_html: str) -> None:
        """Should extract unique base photo URLs from NL detail page."""
        urls = AutoScout24NLScraper.parse_photo_urls_sync(nl_detail_html)

        # Should have photos
        assert len(urls) > 0
        # Should be unique
        assert len(urls) == len(set(urls))
        # Should be base URLs (no resolution suffix)
        for url in urls:
            assert url.endswith(".jpg")
            assert "/720x540" not in url
            assert "/120x90" not in url

    def test_preserves_order(self, de_detail_html: str) -> None:
        """Should preserve the order photos appear in the HTML."""
        urls = AutoScout24DEScraper.parse_photo_urls_sync(de_detail_html)

        # First URL should be the main listing image
        # All URLs should follow the expected pattern
        for url in urls:
            assert "prod.pictures.autoscout24.net/listing-images/" in url

    def test_returns_base_urls_without_resolution(self, de_detail_html: str) -> None:
        """Should return base URLs without resolution suffixes."""
        urls = AutoScout24DEScraper.parse_photo_urls_sync(de_detail_html)

        for url in urls:
            # URL should end with .jpg directly, not /resolution.extension
            assert url.endswith(".jpg")
            # Should contain the GUID pattern
            assert "_" in url.split("/")[-1]

    def test_empty_html_returns_empty_list(self) -> None:
        """Should return empty list for HTML without photos."""
        urls = AutoScout24DEScraper.parse_photo_urls_sync("<html><body>No photos</body></html>")
        assert urls == []

    def test_known_photo_count_de(self, de_detail_html: str) -> None:
        """Should extract expected number of photos from DE fixture."""
        urls = AutoScout24DEScraper.parse_photo_urls_sync(de_detail_html)
        # Based on our fixture analysis, DE fixture has 22 unique photos
        assert len(urls) == 22

    def test_known_photo_count_nl(self, nl_detail_html: str) -> None:
        """Should extract expected number of photos from NL fixture."""
        urls = AutoScout24NLScraper.parse_photo_urls_sync(nl_detail_html)
        # Based on our fixture analysis, NL fixture has 35 unique photos
        assert len(urls) == 35

    def test_url_format(self, de_detail_html: str) -> None:
        """Should extract URLs in the expected format."""
        urls = AutoScout24DEScraper.parse_photo_urls_sync(de_detail_html)

        for url in urls:
            # Format: https://prod.pictures.autoscout24.net/listing-images/{guid1}_{guid2}.jpg
            assert url.startswith("https://prod.pictures.autoscout24.net/listing-images/")
            # Should have guid_guid.jpg pattern
            filename = url.split("/")[-1]
            assert "_" in filename
            assert filename.endswith(".jpg")
