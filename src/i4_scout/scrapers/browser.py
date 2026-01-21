"""Browser automation with Playwright and stealth capabilities."""

import random
from dataclasses import dataclass, field
from typing import Any

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)
from playwright_stealth import Stealth  # type: ignore[import-untyped]

# Default realistic Chrome user agents
DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


@dataclass
class BrowserConfig:
    """Configuration for browser manager."""

    headless: bool = True
    locale: str = "de-DE"
    timezone_id: str = "Europe/Berlin"
    viewport_width: int = 1920
    viewport_height: int = 1080
    rotation_threshold: int = 10
    user_agents: list[str] = field(default_factory=lambda: DEFAULT_USER_AGENTS.copy())
    navigator_platform: str = "Win32"


class BrowserManager:
    """Manages Playwright browser with stealth and context rotation.

    Usage:
        async with BrowserManager(config) as manager:
            page = await manager.get_page()
            await page.goto("https://example.com")
    """

    def __init__(self, config: BrowserConfig | None = None) -> None:
        """Initialize browser manager.

        Args:
            config: Browser configuration. Uses defaults if not provided.
        """
        self._config = config or BrowserConfig()
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._stealth: Stealth | None = None
        self._stealth_cm: Any = None
        self._request_count: int = 0
        self._started: bool = False

    async def __aenter__(self) -> "BrowserManager":
        """Enter async context manager - start browser."""
        await self._start()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context manager - close browser."""
        await self._stop()

    async def _start(self) -> None:
        """Start the browser with stealth configuration."""
        if self._started:
            return

        languages = (self._config.locale, self._config.locale.split("-")[0], "en")

        self._stealth = Stealth(
            navigator_languages_override=languages,
            navigator_platform_override=self._config.navigator_platform,
        )

        self._stealth_cm = self._stealth.use_async(async_playwright())
        self._playwright = await self._stealth_cm.__aenter__()

        self._browser = await self._playwright.chromium.launch(
            headless=self._config.headless,
        )

        self._started = True

    async def _stop(self) -> None:
        """Stop the browser and cleanup."""
        if not self._started:
            return

        if self._context is not None:
            await self._context.close()
            self._context = None

        if self._browser is not None:
            await self._browser.close()
            self._browser = None

        if self._stealth_cm is not None:
            await self._stealth_cm.__aexit__(None, None, None)
            self._stealth_cm = None
            self._playwright = None

        self._started = False

    def _check_started(self) -> None:
        """Raise if manager is not started."""
        if not self._started:
            raise RuntimeError("BrowserManager not started. Use 'async with' context.")

    async def _rotate_context(self) -> None:
        """Close current context and create a new one."""
        if self._context is not None:
            await self._context.close()
            self._context = None
        self._request_count = 0

    async def get_context(self) -> BrowserContext:
        """Get or create a browser context.

        Automatically rotates context after reaching rotation threshold.

        Returns:
            BrowserContext with stealth applied.
        """
        self._check_started()

        if self._browser is None:
            raise RuntimeError("Browser not initialized")

        # Check if rotation is needed
        if (
            self._context is not None
            and self._request_count >= self._config.rotation_threshold
        ):
            await self._rotate_context()

        # Create new context if needed
        if self._context is None:
            user_agent = random.choice(self._config.user_agents)

            self._context = await self._browser.new_context(
                viewport={
                    "width": self._config.viewport_width,
                    "height": self._config.viewport_height,
                },
                locale=self._config.locale,
                timezone_id=self._config.timezone_id,
                user_agent=user_agent,
            )
            self._request_count = 0

        return self._context

    async def get_page(self) -> Page:
        """Get a new page from the current context.

        Returns:
            New Page instance.
        """
        context = await self.get_context()
        return await context.new_page()

    async def increment_request_count(self) -> None:
        """Increment the request counter for context rotation."""
        self._request_count += 1

    @property
    def request_count(self) -> int:
        """Get current request count."""
        return self._request_count

    @property
    def is_started(self) -> bool:
        """Check if manager is started."""
        return self._started
