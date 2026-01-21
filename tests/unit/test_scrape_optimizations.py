"""Unit tests for scraper performance optimizations."""

import time
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from i4_scout.database.repository import ListingRepository
from i4_scout.models.db_models import Base
from i4_scout.models.pydantic_models import ListingCreate, Source
from i4_scout.scrapers.cache import HTMLCache


@pytest.fixture
def db_session():
    """Create an in-memory database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


@pytest.fixture
def repository(db_session):
    """Create a repository instance with test session."""
    return ListingRepository(db_session)


class TestSkipUnchangedLogic:
    """Tests for skipping unchanged listings during scrape."""

    def test_should_skip_when_url_exists_with_same_price(self, repository):
        """Should skip detail fetch when listing exists with same price."""
        # Create existing listing
        repository.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://autoscout24.de/listing/123",
                title="BMW i4 eDrive40",
                price=45000,
            )
        )

        # Check if we should skip
        should_skip = repository.listing_exists_with_price(
            url="https://autoscout24.de/listing/123",
            price=45000,
        )

        assert should_skip is True

    def test_should_not_skip_when_price_changed(self, repository):
        """Should fetch detail when price has changed."""
        # Create existing listing
        repository.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://autoscout24.de/listing/123",
                title="BMW i4 eDrive40",
                price=45000,
            )
        )

        # Check with different price (price drop)
        should_skip = repository.listing_exists_with_price(
            url="https://autoscout24.de/listing/123",
            price=42000,
        )

        assert should_skip is False

    def test_should_not_skip_new_listings(self, repository):
        """Should fetch detail for new listings."""
        should_skip = repository.listing_exists_with_price(
            url="https://autoscout24.de/listing/new",
            price=45000,
        )

        assert should_skip is False


class TestSkipCountTracking:
    """Tests for tracking skip/fetch counts."""

    def test_counts_calculation(self, repository):
        """Should correctly calculate skip and fetch counts."""
        # Create some existing listings with known prices
        for i in range(3):
            repository.create_listing(
                ListingCreate(
                    source=Source.AUTOSCOUT24_DE,
                    url=f"https://autoscout24.de/listing/{i}",
                    title=f"BMW i4 #{i}",
                    price=45000 + (i * 1000),
                )
            )

        # Simulate search results from scraper
        search_results = [
            # Existing with same price (skip)
            {"url": "https://autoscout24.de/listing/0", "price": 45000},
            # Existing with price change (fetch)
            {"url": "https://autoscout24.de/listing/1", "price": 40000},
            # New listing (fetch)
            {"url": "https://autoscout24.de/listing/new", "price": 50000},
            # Existing with same price (skip)
            {"url": "https://autoscout24.de/listing/2", "price": 47000},
        ]

        skip_count = 0
        fetch_count = 0

        for result in search_results:
            if repository.listing_exists_with_price(result["url"], result["price"]):
                skip_count += 1
            else:
                fetch_count += 1

        assert skip_count == 2  # listings 0 and 2
        assert fetch_count == 2  # listing 1 (price changed) and new listing


class TestHTMLCaching:
    """Tests for HTML caching behavior."""

    @pytest.fixture
    def cache(self, tmp_path: Path) -> HTMLCache:
        """Create a cache with a temporary directory."""
        return HTMLCache(cache_dir=tmp_path / "cache")

    def test_cache_stores_and_retrieves_html(self, cache: HTMLCache):
        """Should store HTML and retrieve it within TTL."""
        url = "https://autoscout24.de/listing/123"
        html = "<html><body>Test content</body></html>"

        cache.set(url, html)
        entry = cache.get(url)

        assert entry is not None
        assert entry.html == html
        assert entry.url == url

    def test_cache_miss_for_nonexistent_url(self, cache: HTMLCache):
        """Should return None for URLs not in cache."""
        entry = cache.get("https://nonexistent.com/page")

        assert entry is None

    def test_search_page_uses_shorter_ttl(self, cache: HTMLCache):
        """Search pages should have 1-hour TTL."""
        # Verify TTL classification
        search_url = "https://autoscout24.de/lst/bmw-i4"
        assert cache._is_search_url(search_url) is True

        detail_url = "https://autoscout24.de/angebote/bmw-i4-123"
        assert cache._is_search_url(detail_url) is False

    def test_detail_page_uses_longer_ttl(self, cache: HTMLCache):
        """Detail pages should have 24-hour TTL."""
        assert cache.DETAIL_TTL_SECONDS == 86400  # 24 hours
        assert cache.SEARCH_TTL_SECONDS == 3600   # 1 hour

    def test_cache_respects_ttl(self, cache: HTMLCache):
        """Should not return expired entries."""
        url = "https://autoscout24.de/angebote/123"
        html = "<html>Content</html>"

        # Store with manipulated timestamp (in the past)
        cache.set(url, html)

        # Manually expire the entry by modifying the file
        cache_path = cache._cache_path(url)
        import json
        with open(cache_path) as f:
            data = json.load(f)
        data["timestamp"] = time.time() - 100000  # Way past TTL
        with open(cache_path, "w") as f:
            json.dump(data, f)

        # Should not retrieve expired entry
        entry = cache.get(url)
        assert entry is None

    def test_cache_url_hashing_is_consistent(self, cache: HTMLCache):
        """Same URL should produce same hash."""
        url = "https://autoscout24.de/listing/abc"
        hash1 = cache._url_hash(url)
        hash2 = cache._url_hash(url)

        assert hash1 == hash2
        assert len(hash1) == 16  # Truncated SHA256

    def test_cache_clear_removes_all_entries(self, cache: HTMLCache):
        """clear() should remove all cached files."""
        # Add some entries
        for i in range(5):
            cache.set(f"https://example.com/{i}", f"<html>{i}</html>")

        count = cache.clear()

        assert count == 5
        assert cache.get("https://example.com/0") is None

    def test_cache_stats_reports_correctly(self, cache: HTMLCache):
        """stats() should report cache statistics."""
        # Add search page
        cache.set("https://autoscout24.de/lst/search", "<html>Search</html>")
        # Add detail page
        cache.set("https://autoscout24.de/angebote/123", "<html>Detail</html>")

        stats = cache.stats()

        assert stats["total"] == 2
        assert stats["search_pages"] == 1
        assert stats["detail_pages"] == 1
        assert stats["valid"] == 2
        assert stats["expired"] == 0
