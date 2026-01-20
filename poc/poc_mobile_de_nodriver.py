#!/usr/bin/env python3
"""
PoC Script for mobile.de using nodriver - bypass bot detection.

nodriver is the successor to undetected-chromedriver and communicates
directly via Chrome DevTools Protocol, avoiding WebDriver detection.
"""

import asyncio
import json
import random
from datetime import datetime
from pathlib import Path

import nodriver as uc


RESULTS_DIR = Path(__file__).parent / "results" / "mobile_de_nodriver"
SEARCH_URL = "https://suchen.mobile.de/fahrzeuge/search.html?dam=0&isSearchRequest=true&ms=3500%3B53%3B%3Bi4&ref=quickSearch&sb=rel&vc=Car"


async def random_delay(min_sec: float = 2.0, max_sec: float = 5.0) -> None:
    """Human-like random delay."""
    await asyncio.sleep(random.uniform(min_sec, max_sec))


async def run_poc():
    """Main PoC execution with nodriver."""
    print(f"\n{'='*60}")
    print("mobile.de PoC - nodriver (undetected)")
    print(f"{'='*60}")
    print(f"Started: {datetime.now().isoformat()}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    results = {
        "site": "mobile.de",
        "method": "nodriver",
        "search_url": SEARCH_URL,
        "timestamp": datetime.now().isoformat(),
        "success": False,
        "page_loaded": False,
        "listings_found": 0,
        "errors": [],
    }

    try:
        print("\n[1/4] Starting nodriver browser...")
        # Start browser with nodriver using Playwright's Chromium
        chrome_path = "/home/tim/.cache/ms-playwright/chromium-1200/chrome-linux64/chrome"
        browser = await uc.start(
            headless=True,
            lang="de-DE",
            browser_executable_path=chrome_path,
        )

        print("\n[2/4] Navigating to mobile.de search...")
        page = await browser.get(SEARCH_URL)

        # Wait for page to load
        await random_delay(5, 8)

        # Check page title
        title = await page.evaluate("document.title")
        print(f"      Page title: {title}")

        # Take screenshot
        await page.save_screenshot(str(RESULTS_DIR / "search_results.png"))
        print("      Screenshot saved: search_results.png")

        # Get page content
        content = await page.get_content()
        with open(RESULTS_DIR / "search_results.html", "w", encoding="utf-8") as f:
            f.write(content)
        print("      DOM saved: search_results.html")

        # Check for access denied
        if "Zugriff verweigert" in content or "Access denied" in content:
            results["errors"].append("Access denied - bot detection triggered")
            print("\n[ERROR] Access denied - bot detection still triggered!")
        else:
            results["page_loaded"] = True
            print("\n[3/4] Page loaded successfully! Checking for listings...")

            # Try to find listing elements
            # mobile.de uses various selectors for listings
            listing_count = await page.evaluate("""
                () => {
                    const selectors = [
                        'a[data-testid="result-listing-link"]',
                        '.result-item',
                        '.cBox-body--resultitem',
                        'article.list-item'
                    ];
                    for (const selector of selectors) {
                        const elements = document.querySelectorAll(selector);
                        if (elements.length > 0) return elements.length;
                    }
                    return 0;
                }
            """)

            results["listings_found"] = listing_count
            print(f"      Found {listing_count} listing elements")

            if listing_count > 0:
                results["success"] = True

                # Extract sample listings
                print("\n[4/4] Extracting sample listings...")
                sample_listings = await page.evaluate("""
                    () => {
                        const listings = [];
                        const links = document.querySelectorAll('a[data-testid="result-listing-link"], .result-item a');
                        for (let i = 0; i < Math.min(links.length, 5); i++) {
                            const link = links[i];
                            listings.push({
                                title: link.textContent?.trim().substring(0, 80) || 'N/A',
                                url: link.href || 'N/A'
                            });
                        }
                        return listings;
                    }
                """)

                for listing in sample_listings:
                    print(f"      - {listing.get('title', 'N/A')[:50]}...")

                results["sample_listings"] = sample_listings

        await browser.stop()

    except Exception as e:
        results["errors"].append(str(e))
        print(f"\n[ERROR] {e}")

    # Save results
    with open(RESULTS_DIR / "results.json", "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"PoC Result: {'PASS' if results['success'] else 'FAIL'}")
    if results["page_loaded"] and not results["success"]:
        print("Note: Page loaded but no listings found (may need selector adjustment)")
    print(f"{'='*60}")

    return results


if __name__ == "__main__":
    uc.loop().run_until_complete(run_poc())
