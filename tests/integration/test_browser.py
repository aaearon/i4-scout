"""Integration tests for the browser manager."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from i4_scout.scrapers.browser import BrowserConfig, BrowserManager


class TestBrowserConfig:
    """Tests for BrowserConfig dataclass."""

    def test_default_values(self):
        """BrowserConfig should have sensible defaults."""
        config = BrowserConfig()

        assert config.headless is True
        assert config.locale == "de-DE"
        assert config.timezone_id == "Europe/Berlin"
        assert config.viewport_width == 1920
        assert config.viewport_height == 1080
        assert config.rotation_threshold == 10
        assert config.user_agents is not None
        assert len(config.user_agents) > 0

    def test_custom_values(self):
        """BrowserConfig should accept custom values."""
        config = BrowserConfig(
            headless=False,
            locale="nl-NL",
            timezone_id="Europe/Amsterdam",
            viewport_width=1280,
            viewport_height=720,
            rotation_threshold=5,
        )

        assert config.headless is False
        assert config.locale == "nl-NL"
        assert config.timezone_id == "Europe/Amsterdam"
        assert config.viewport_width == 1280
        assert config.viewport_height == 720
        assert config.rotation_threshold == 5


class TestBrowserManager:
    """Tests for BrowserManager."""

    @pytest.mark.asyncio
    async def test_context_manager_lifecycle(self):
        """BrowserManager should work as async context manager."""
        with patch("i4_scout.scrapers.browser.async_playwright"), \
             patch("i4_scout.scrapers.browser.Stealth") as mock_stealth:
            # Setup mocks
            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_page = AsyncMock()
            mock_browser.new_context.return_value = mock_context
            mock_context.new_page.return_value = mock_page

            mock_p = AsyncMock()
            mock_p.chromium.launch.return_value = mock_browser

            mock_stealth_instance = MagicMock()
            mock_stealth_instance.use_async.return_value.__aenter__ = AsyncMock(return_value=mock_p)
            mock_stealth_instance.use_async.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_stealth.return_value = mock_stealth_instance

            config = BrowserConfig()
            manager = BrowserManager(config)

            async with manager:
                assert manager._browser is not None

            # Verify browser was closed
            mock_browser.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_context_creates_new_context(self):
        """get_context should create a new browser context."""
        with patch("i4_scout.scrapers.browser.async_playwright"), \
             patch("i4_scout.scrapers.browser.Stealth") as mock_stealth:
            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_browser.new_context.return_value = mock_context

            mock_p = AsyncMock()
            mock_p.chromium.launch.return_value = mock_browser

            mock_stealth_instance = MagicMock()
            mock_stealth_instance.use_async.return_value.__aenter__ = AsyncMock(return_value=mock_p)
            mock_stealth_instance.use_async.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_stealth.return_value = mock_stealth_instance

            config = BrowserConfig()
            manager = BrowserManager(config)

            async with manager:
                context = await manager.get_context()
                assert context is not None
                mock_browser.new_context.assert_called()

    @pytest.mark.asyncio
    async def test_context_rotation_after_threshold(self):
        """Context should rotate after reaching request threshold."""
        with patch("i4_scout.scrapers.browser.async_playwright"), \
             patch("i4_scout.scrapers.browser.Stealth") as mock_stealth:
            mock_browser = AsyncMock()
            mock_context1 = AsyncMock()
            mock_context2 = AsyncMock()
            mock_browser.new_context.side_effect = [mock_context1, mock_context2]

            mock_p = AsyncMock()
            mock_p.chromium.launch.return_value = mock_browser

            mock_stealth_instance = MagicMock()
            mock_stealth_instance.use_async.return_value.__aenter__ = AsyncMock(return_value=mock_p)
            mock_stealth_instance.use_async.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_stealth.return_value = mock_stealth_instance

            config = BrowserConfig(rotation_threshold=3)
            manager = BrowserManager(config)

            async with manager:
                # First 3 requests should use same context
                await manager.get_context()
                await manager.increment_request_count()
                await manager.increment_request_count()
                await manager.increment_request_count()

                # 4th request should trigger rotation
                await manager.get_context()

                # Should have created 2 contexts
                assert mock_browser.new_context.call_count == 2
                # First context should have been closed
                mock_context1.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_page_returns_page(self):
        """get_page should return a page from the current context."""
        with patch("i4_scout.scrapers.browser.async_playwright"), \
             patch("i4_scout.scrapers.browser.Stealth") as mock_stealth:
            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_page = AsyncMock()
            mock_browser.new_context.return_value = mock_context
            mock_context.new_page.return_value = mock_page

            mock_p = AsyncMock()
            mock_p.chromium.launch.return_value = mock_browser

            mock_stealth_instance = MagicMock()
            mock_stealth_instance.use_async.return_value.__aenter__ = AsyncMock(return_value=mock_p)
            mock_stealth_instance.use_async.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_stealth.return_value = mock_stealth_instance

            config = BrowserConfig()
            manager = BrowserManager(config)

            async with manager:
                page = await manager.get_page()
                assert page is mock_page

    @pytest.mark.asyncio
    async def test_user_agent_rotation(self):
        """User agent should be selected from configured list."""
        with patch("i4_scout.scrapers.browser.async_playwright"), \
             patch("i4_scout.scrapers.browser.Stealth") as mock_stealth:
            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_browser.new_context.return_value = mock_context

            mock_p = AsyncMock()
            mock_p.chromium.launch.return_value = mock_browser

            mock_stealth_instance = MagicMock()
            mock_stealth_instance.use_async.return_value.__aenter__ = AsyncMock(return_value=mock_p)
            mock_stealth_instance.use_async.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_stealth.return_value = mock_stealth_instance

            custom_agents = ["Agent1", "Agent2"]
            config = BrowserConfig(user_agents=custom_agents)
            manager = BrowserManager(config)

            async with manager:
                await manager.get_context()
                call_kwargs = mock_browser.new_context.call_args.kwargs
                assert call_kwargs.get("user_agent") in custom_agents

    @pytest.mark.asyncio
    async def test_stealth_configuration(self):
        """Stealth should be configured with correct language and platform."""
        with patch("i4_scout.scrapers.browser.async_playwright"), \
             patch("i4_scout.scrapers.browser.Stealth") as mock_stealth:
            mock_browser = AsyncMock()
            mock_p = AsyncMock()
            mock_p.chromium.launch.return_value = mock_browser

            mock_stealth_instance = MagicMock()
            mock_stealth_instance.use_async.return_value.__aenter__ = AsyncMock(return_value=mock_p)
            mock_stealth_instance.use_async.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_stealth.return_value = mock_stealth_instance

            config = BrowserConfig(locale="de-DE")
            manager = BrowserManager(config)

            async with manager:
                pass

            mock_stealth.assert_called_once()
            call_kwargs = mock_stealth.call_args.kwargs
            assert "de-DE" in call_kwargs.get("navigator_languages_override", ())


class TestBrowserManagerNotStarted:
    """Tests for BrowserManager when not started."""

    @pytest.mark.asyncio
    async def test_get_context_raises_when_not_started(self):
        """get_context should raise when manager not started."""
        config = BrowserConfig()
        manager = BrowserManager(config)

        with pytest.raises(RuntimeError, match="not started"):
            await manager.get_context()

    @pytest.mark.asyncio
    async def test_get_page_raises_when_not_started(self):
        """get_page should raise when manager not started."""
        config = BrowserConfig()
        manager = BrowserManager(config)

        with pytest.raises(RuntimeError, match="not started"):
            await manager.get_page()
