"""Scraper modules."""

from car_scraper.scrapers.base import BaseScraper, ScraperConfig
from car_scraper.scrapers.browser import BrowserConfig, BrowserManager

__all__ = ["BaseScraper", "BrowserConfig", "BrowserManager", "ScraperConfig"]
