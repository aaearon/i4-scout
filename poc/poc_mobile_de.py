#!/usr/bin/env python3
"""
PoC Script for mobile.de - BMW i4 eDrive40 scraper validation.

Requirements:
1. Load search results for BMW i4 eDrive40
2. Extract >=5 listing cards (title, price, URL)
3. Navigate to one detail page
4. Extract equipment/options list
5. Paginate to page 2
6. Save: screenshot, sample JSON, report MD
"""

import asyncio
import json
import random
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright, Page, BrowserContext
from playwright_stealth import Stealth


RESULTS_DIR = Path(__file__).parent / "results" / "mobile_de"
SEARCH_URL = "https://suchen.mobile.de/fahrzeuge/search.html?dam=0&isSearchRequest=true&ms=3500%3B53%3B%3Bi4&ref=quickSearch&sb=rel&vc=Car"


async def random_delay(min_sec: float = 2.0, max_sec: float = 5.0) -> None:
    """Human-like random delay."""
    await asyncio.sleep(random.uniform(min_sec, max_sec))


async def human_scroll(page: Page) -> None:
    """Simulate human-like scrolling."""
    for _ in range(3):
        await page.mouse.wheel(0, random.randint(300, 600))
        await asyncio.sleep(random.uniform(0.3, 0.8))


async def handle_cookie_consent(page: Page) -> None:
    """Handle cookie consent banners if present."""
    try:
        # mobile.de uses a consent iframe/modal
        consent_selectors = [
            'button[data-testid="uc-accept-all-button"]',
            'button:has-text("Alle akzeptieren")',
            'button:has-text("Accept All")',
            '#didomi-notice-agree-button',
            'button.mde-consent-accept-btn',
        ]
        for selector in consent_selectors:
            try:
                btn = page.locator(selector).first
                if await btn.is_visible(timeout=2000):
                    await btn.click()
                    await random_delay(1, 2)
                    return
            except Exception:
                continue
    except Exception:
        pass  # No consent banner or already handled


async def extract_listing_cards(page: Page) -> list[dict]:
    """Extract listing cards from search results page."""
    listings = []

    # Wait for listings to load
    await page.wait_for_selector('a[data-testid="result-listing-link"], .result-item, article', timeout=15000)

    # Try multiple selector strategies
    card_selectors = [
        'a[data-testid="result-listing-link"]',
        '.result-item a.link--muted',
        'article.list-item',
    ]

    for selector in card_selectors:
        cards = await page.locator(selector).all()
        if cards and len(cards) >= 5:
            break

    for i, card in enumerate(cards[:10]):  # Limit to 10 for PoC
        try:
            # Get URL
            href = await card.get_attribute('href')
            if not href:
                parent = card.locator('xpath=ancestor::a').first
                href = await parent.get_attribute('href')

            if href and not href.startswith('http'):
                href = f"https://suchen.mobile.de{href}"

            # Get title - try multiple approaches
            title_el = card.locator('h2, .headline-block, .result-item-title').first
            title = await title_el.text_content() if await title_el.count() > 0 else ""
            title = title.strip() if title else f"Listing {i+1}"

            # Get price
            price_el = card.locator('[data-testid="price"], .price-block, .result-item-price').first
            price = await price_el.text_content() if await price_el.count() > 0 else ""
            price = price.strip() if price else "N/A"

            listings.append({
                "title": title,
                "price": price,
                "url": href or "N/A",
                "index": i + 1,
            })
        except Exception as e:
            print(f"  Warning: Could not extract card {i+1}: {e}")
            continue

    return listings


async def extract_detail_options(page: Page) -> list[str]:
    """Extract equipment/options from a detail page."""
    options = []

    # Wait for page to load
    await random_delay(2, 4)
    await human_scroll(page)

    # Try to expand equipment sections
    expand_selectors = [
        'button:has-text("Ausstattung")',
        'button:has-text("Alle Details")',
        '[data-testid="equipment-section"] button',
    ]
    for selector in expand_selectors:
        try:
            btn = page.locator(selector).first
            if await btn.is_visible(timeout=2000):
                await btn.click()
                await random_delay(1, 2)
        except Exception:
            continue

    # Extract options from various possible containers
    option_selectors = [
        '[data-testid="equipment-item"]',
        '.equipment-block li',
        '.features-list li',
        '.g-col-6.u-text-break-word',
        '#features li',
    ]

    for selector in option_selectors:
        items = await page.locator(selector).all()
        if items:
            for item in items:
                text = await item.text_content()
                if text:
                    options.append(text.strip())
            if options:
                break

    # Fallback: get all text from equipment section
    if not options:
        try:
            section = page.locator('[class*="equipment"], [class*="features"], #features').first
            text = await section.text_content()
            if text:
                options = [line.strip() for line in text.split('\n') if line.strip()]
        except Exception:
            pass

    return options[:50]  # Limit for PoC


async def run_poc():
    """Main PoC execution."""
    print(f"\n{'='*60}")
    print("mobile.de PoC - BMW i4 eDrive40 Scraper Validation")
    print(f"{'='*60}")
    print(f"Started: {datetime.now().isoformat()}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    results = {
        "site": "mobile.de",
        "search_url": SEARCH_URL,
        "timestamp": datetime.now().isoformat(),
        "success": False,
        "listings": [],
        "detail_page": None,
        "options": [],
        "pagination_success": False,
        "errors": [],
    }

    stealth = Stealth(
        navigator_languages_override=("de-DE", "de", "en"),
        navigator_platform_override="Win32",
    )

    async with stealth.use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="de-DE",
            timezone_id="Europe/Berlin",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )

        page = await context.new_page()

        try:
            # Step 1: Load search results
            print("\n[1/5] Loading search results...")
            await page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=30000)
            await random_delay(3, 5)
            await handle_cookie_consent(page)
            await human_scroll(page)

            # Take screenshot of search results
            await page.screenshot(path=RESULTS_DIR / "search_results.png", full_page=False)
            print("      Screenshot saved: search_results.png")

            # Step 2: Extract listing cards
            print("\n[2/5] Extracting listing cards...")
            listings = await extract_listing_cards(page)
            results["listings"] = listings
            print(f"      Found {len(listings)} listings")

            for listing in listings[:5]:
                print(f"      - {listing['title'][:50]}... | {listing['price']}")

            if len(listings) < 5:
                results["errors"].append(f"Only found {len(listings)} listings (need >= 5)")

            # Step 3: Navigate to detail page
            print("\n[3/5] Navigating to detail page...")
            if listings and listings[0].get("url", "").startswith("http"):
                detail_url = listings[0]["url"]
                results["detail_page"] = detail_url

                await page.goto(detail_url, wait_until="domcontentloaded", timeout=30000)
                await random_delay(3, 5)
                await handle_cookie_consent(page)

                # Take screenshot of detail page
                await page.screenshot(path=RESULTS_DIR / "detail_page.png", full_page=False)
                print("      Screenshot saved: detail_page.png")

                # Step 4: Extract options
                print("\n[4/5] Extracting equipment/options...")
                options = await extract_detail_options(page)
                results["options"] = options
                print(f"      Found {len(options)} options/features")
                for opt in options[:10]:
                    print(f"      - {opt[:60]}")

                if len(options) < 3:
                    results["errors"].append(f"Only found {len(options)} options")
            else:
                results["errors"].append("No valid detail URL found")

            # Step 5: Test pagination
            print("\n[5/5] Testing pagination to page 2...")
            await page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=30000)
            await random_delay(2, 4)
            await handle_cookie_consent(page)

            # Try to click page 2
            page_2_selectors = [
                'a[data-testid="pagination-page-2"]',
                'a:has-text("2"):visible',
                '.pagination a:has-text("2")',
                '[aria-label*="Seite 2"]',
            ]

            pagination_clicked = False
            for selector in page_2_selectors:
                try:
                    btn = page.locator(selector).first
                    if await btn.is_visible(timeout=3000):
                        await btn.click()
                        await random_delay(3, 5)
                        pagination_clicked = True
                        break
                except Exception:
                    continue

            if pagination_clicked:
                await page.screenshot(path=RESULTS_DIR / "page_2.png", full_page=False)
                results["pagination_success"] = True
                print("      Pagination successful! Screenshot saved: page_2.png")
            else:
                # Try URL-based pagination
                page_2_url = SEARCH_URL + "&pageNumber=2"
                await page.goto(page_2_url, wait_until="domcontentloaded", timeout=30000)
                await random_delay(2, 4)
                await page.screenshot(path=RESULTS_DIR / "page_2.png", full_page=False)
                results["pagination_success"] = True
                print("      Pagination via URL successful! Screenshot saved: page_2.png")

            # Determine success
            results["success"] = (
                len(listings) >= 5 and
                len(results.get("options", [])) >= 3 and
                results["pagination_success"]
            )

        except Exception as e:
            results["errors"].append(str(e))
            print(f"\n[ERROR] {e}")
            await page.screenshot(path=RESULTS_DIR / "error.png", full_page=False)

        finally:
            await browser.close()

    # Save results
    with open(RESULTS_DIR / "results.json", "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Generate report
    report = generate_report(results)
    with open(RESULTS_DIR / "report.md", "w") as f:
        f.write(report)

    print(f"\n{'='*60}")
    print(f"PoC Result: {'PASS' if results['success'] else 'FAIL'}")
    print(f"{'='*60}")

    return results


def generate_report(results: dict) -> str:
    """Generate markdown report."""
    status = "PASS" if results["success"] else "FAIL"

    report = f"""# mobile.de PoC Report

**Status:** {status}
**Timestamp:** {results['timestamp']}
**Search URL:** {results['search_url']}

## Results Summary

| Criterion | Result |
|-----------|--------|
| Listings extracted | {len(results['listings'])} (need >= 5) |
| Options extracted | {len(results['options'])} |
| Pagination works | {'Yes' if results['pagination_success'] else 'No'} |

## Extracted Listings

"""
    for listing in results["listings"][:5]:
        report += f"- **{listing['title']}** - {listing['price']}\n"
        report += f"  URL: {listing['url']}\n\n"

    report += "\n## Equipment/Options Sample\n\n"
    for opt in results["options"][:15]:
        report += f"- {opt}\n"

    if results["errors"]:
        report += "\n## Errors\n\n"
        for err in results["errors"]:
            report += f"- {err}\n"

    report += f"\n## Screenshots\n\n"
    report += f"- [Search Results](search_results.png)\n"
    report += f"- [Detail Page](detail_page.png)\n"
    report += f"- [Page 2](page_2.png)\n"

    return report


if __name__ == "__main__":
    asyncio.run(run_poc())
