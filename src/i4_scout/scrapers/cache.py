"""HTML caching for scraper to avoid redundant requests."""

import hashlib
import json
import time
from pathlib import Path
from typing import NamedTuple


class CacheEntry(NamedTuple):
    """Cached HTML content with metadata."""

    html: str
    url: str
    timestamp: float
    etag: str | None = None


class HTMLCache:
    """File-based cache for scraped HTML content.

    Cache strategy:
    - Search pages: 1 hour TTL (listings change frequently)
    - Detail pages: 24 hours TTL (content rarely changes)
    - Uses URL hash as filename for fast lookup
    """

    SEARCH_TTL_SECONDS = 3600  # 1 hour
    DETAIL_TTL_SECONDS = 86400  # 24 hours

    def __init__(self, cache_dir: Path | str | None = None):
        """Initialize cache.

        Args:
            cache_dir: Directory for cache files. Defaults to .cache/html
        """
        if cache_dir is None:
            cache_dir = Path(__file__).parent.parent.parent.parent / ".cache" / "html"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _url_hash(self, url: str) -> str:
        """Generate stable hash from URL."""
        return hashlib.sha256(url.encode()).hexdigest()[:16]

    def _cache_path(self, url: str) -> Path:
        """Get cache file path for URL."""
        return self.cache_dir / f"{self._url_hash(url)}.json"

    def _is_search_url(self, url: str) -> bool:
        """Check if URL is a search page (vs detail page)."""
        return "/lst/" in url or "/aanbod?" in url or "page=" in url

    def get(self, url: str) -> CacheEntry | None:
        """Get cached HTML if valid.

        Args:
            url: URL to look up.

        Returns:
            CacheEntry if found and not expired, None otherwise.
        """
        cache_path = self._cache_path(url)
        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            entry = CacheEntry(
                html=data["html"],
                url=data["url"],
                timestamp=data["timestamp"],
                etag=data.get("etag"),
            )

            # Check TTL
            ttl = self.SEARCH_TTL_SECONDS if self._is_search_url(url) else self.DETAIL_TTL_SECONDS
            age = time.time() - entry.timestamp
            if age > ttl:
                return None

            return entry

        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    def set(self, url: str, html: str, etag: str | None = None) -> None:
        """Store HTML in cache.

        Args:
            url: URL of the page.
            html: HTML content.
            etag: Optional ETag header for future conditional requests.
        """
        cache_path = self._cache_path(url)
        data = {
            "url": url,
            "html": html,
            "timestamp": time.time(),
            "etag": etag,
        }

        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def get_etag(self, url: str) -> str | None:
        """Get stored ETag for conditional request.

        Args:
            url: URL to look up.

        Returns:
            ETag string if available, None otherwise.
        """
        cache_path = self._cache_path(url)
        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("etag")
        except (json.JSONDecodeError, KeyError):
            return None

    def clear(self) -> int:
        """Clear all cached files.

        Returns:
            Number of files removed.
        """
        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()
            count += 1
        return count

    def clear_expired(self) -> int:
        """Remove expired cache entries.

        Returns:
            Number of files removed.
        """
        count = 0
        now = time.time()

        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                url = data.get("url", "")
                timestamp = data.get("timestamp", 0)
                ttl = self.SEARCH_TTL_SECONDS if self._is_search_url(url) else self.DETAIL_TTL_SECONDS

                if now - timestamp > ttl:
                    cache_file.unlink()
                    count += 1
            except (json.JSONDecodeError, KeyError):
                cache_file.unlink()
                count += 1

        return count

    def stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dict with cache stats.
        """
        total = 0
        expired = 0
        search_pages = 0
        detail_pages = 0
        now = time.time()

        for cache_file in self.cache_dir.glob("*.json"):
            total += 1
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                url = data.get("url", "")
                timestamp = data.get("timestamp", 0)
                ttl = self.SEARCH_TTL_SECONDS if self._is_search_url(url) else self.DETAIL_TTL_SECONDS

                if now - timestamp > ttl:
                    expired += 1

                if self._is_search_url(url):
                    search_pages += 1
                else:
                    detail_pages += 1
            except (json.JSONDecodeError, KeyError):
                expired += 1

        return {
            "total": total,
            "expired": expired,
            "valid": total - expired,
            "search_pages": search_pages,
            "detail_pages": detail_pages,
        }


# Global cache instance
_cache: HTMLCache | None = None


def get_cache() -> HTMLCache:
    """Get global cache instance."""
    global _cache
    if _cache is None:
        _cache = HTMLCache()
    return _cache
