"""Scraper modules."""

from i4_scout.scrapers.base import BaseScraper, ScraperConfig
from i4_scout.scrapers.browser import BrowserConfig, BrowserManager

__all__ = ["BaseScraper", "BrowserConfig", "BrowserManager", "ScraperConfig"]
