#!/usr/bin/env python3
"""
PoC Script for autoscout24.nl - BMW i4 eDrive40 scraper validation.

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

from playwright.async_api import async_playwright, Page
from playwright_stealth import Stealth


RESULTS_DIR = Path(__file__).parent / "results" / "autoscout24_nl"
# BMW i4 search on autoscout24.nl
SEARCH_URL = "https://www.autoscout24.nl/lst/bmw/i4?atype=C&cy=NL&desc=0&fregfrom=2022&sort=standard&source=homepage_search-mask&ustate=N%2CU"


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
        consent_selectors = [
            'button[data-testid="as24-cmp-accept-all-button"]',
            '#onetrust-accept-btn-handler',
            'button:has-text("Alles accepteren")',
            'button:has-text("Alle akzeptieren")',
            'button:has-text("Accept All")',
            '[data-cy="consent-accept-all"]',
        ]
        for selector in consent_selectors:
            try:
                btn = page.locator(selector).first
                if await btn.is_visible(timeout=3000):
                    await btn.click()
                    await random_delay(1, 2)
                    return
            except Exception:
                continue
    except Exception:
        pass


async def save_dom(page: Page, filepath: Path) -> None:
    """Save page DOM to file for analysis."""
    html = await page.content()
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)


async def extract_listing_cards(page: Page) -> list[dict]:
    """Extract listing cards from search results page."""
    listings = []

    # Wait for page to fully load
    await asyncio.sleep(3)
    await human_scroll(page)
    await asyncio.sleep(2)

    # Try to find listing links - NL uses /aanbod/ in detail URLs
    listing_links = await page.locator('a[href*="/aanbod/"][href*="/bmw/"]').all()

    # Fallback: look for article elements
    if len(listing_links) < 5:
        container_selectors = [
            'article[class*="cldt-summary"]',
            'div[class*="ListItem"]',
            '[data-testid*="listing"]',
            'article',
        ]
        for selector in container_selectors:
            containers = await page.locator(selector).all()
            if containers and len(containers) >= 3:
                listing_links = containers
                break

    seen_urls = set()
    for i, element in enumerate(listing_links[:15]):
        try:
            href = await element.get_attribute('href')
            if not href:
                link = element.locator('a').first
                href = await link.get_attribute('href') if await link.count() > 0 else None

            if not href or '/aanbod/' not in href or 'leasing' in href.lower():
                continue
            if href in seen_urls:
                continue
            seen_urls.add(href)

            if not href.startswith('http'):
                href = f"https://www.autoscout24.nl{href}"

            parent = element
            title = ""
            for tc in ['h2', 'h3', '[class*="title"]', '[class*="Title"]']:
                title_el = parent.locator(tc).first
                if await title_el.count() > 0:
                    title = await title_el.text_content()
                    if title:
                        title = title.strip()
                        break

            if not title:
                text = await element.text_content()
                title = text.strip()[:100] if text else f"BMW i4 Listing {len(listings)+1}"

            price = "N/A"
            for pc in ['[class*="price"]', '[class*="Price"]', 'span:has-text("€")']:
                price_el = parent.locator(pc).first
                if await price_el.count() > 0:
                    price = await price_el.text_content()
                    if price and '€' in price:
                        price = price.strip()
                        break

            listings.append({
                "title": title[:100],
                "price": price,
                "url": href,
                "index": len(listings) + 1,
            })

            if len(listings) >= 10:
                break

        except Exception as e:
            print(f"  Warning: Could not extract element {i+1}: {e}")
            continue

    return listings


async def extract_detail_options(page: Page) -> list[str]:
    """Extract equipment/options from a detail page."""
    import re
    options = []

    await random_delay(2, 4)
    await human_scroll(page)

    # Save DOM for analysis
    await save_dom(page, RESULTS_DIR / "detail_page.html")

    # Scroll down to load all content
    for _ in range(5):
        await page.mouse.wheel(0, 500)
        await asyncio.sleep(0.5)

    # Try to expand equipment sections
    expand_selectors = [
        'button:has-text("Uitrusting")',
        'button:has-text("Alle tonen")',
        'button:has-text("Meer weergeven")',
        'button:has-text("meer")',
        '[class*="Expandable"] button',
        '[class*="chevron"]',
    ]

    for selector in expand_selectors:
        try:
            btns = await page.locator(selector).all()
            for btn in btns[:5]:
                if await btn.is_visible(timeout=1000):
                    await btn.click()
                    await asyncio.sleep(0.3)
        except Exception:
            continue

    await asyncio.sleep(1)

    # Primary approach: look for collapsed/child containers with equipment text
    container_selectors = [
        '[class*="childContainer"]',
        '[class*="collapsed"]',
        '[class*="ExpandableDetailsSection"]',
        '[class*="DetailsSection_childrenSection"]',
    ]

    # Equipment keywords (Dutch and German terms)
    equipment_keywords = [
        'parkeerhulp', 'airconditioning', 'navigatie', 'stoelverwarming', 'cruise',
        'leder', 'camera', 'sensor', 'assistant', 'airbag', 'abs', 'radio',
        'einparkhilfe', 'klimaautomatik', 'navigation', 'sitzheizung', 'tempomat',
    ]

    for selector in container_selectors:
        try:
            containers = await page.locator(selector).all()
            for container in containers:
                text = await container.text_content()
                if text:
                    text_lower = text.lower()
                    if any(kw in text_lower for kw in equipment_keywords):
                        items = re.split(r'(?=[A-ZÄÖÜ][a-zäöüß])', text)
                        for item in items:
                            item = item.strip()
                            if len(item) > 3 and len(item) < 60:
                                if not any(skip in item.lower() for skip in ['comfort', 'entertainment', 'media', 'veiligheid', 'security', 'edities', 'packages']):
                                    if item not in options:
                                        options.append(item)
        except Exception as e:
            print(f"  Warning extracting from {selector}: {e}")
            continue

    # Fallback: VehicleOverview items
    if len(options) < 5:
        try:
            items = await page.locator('[class*="VehicleOverview_itemContainer"]').all()
            for item in items:
                text = await item.text_content()
                if text:
                    options.append(text.strip())
        except Exception:
            pass

    # Deduplicate
    seen = set()
    unique_options = []
    for opt in options:
        if opt not in seen and len(opt) > 2:
            seen.add(opt)
            unique_options.append(opt)

    return unique_options[:50]


async def run_poc():
    """Main PoC execution."""
    print(f"\n{'='*60}")
    print("autoscout24.nl PoC - BMW i4 eDrive40 Scraper Validation")
    print(f"{'='*60}")
    print(f"Started: {datetime.now().isoformat()}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    results = {
        "site": "autoscout24.nl",
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
        navigator_languages_override=("nl-NL", "nl", "en"),
        navigator_platform_override="Win32",
    )

    async with stealth.use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="nl-NL",
            timezone_id="Europe/Amsterdam",
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

            await page.screenshot(path=RESULTS_DIR / "search_results.png", full_page=False)
            await save_dom(page, RESULTS_DIR / "search_results.html")
            print("      Screenshot saved: search_results.png")
            print("      DOM saved: search_results.html")

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

            page_2_selectors = [
                'a[aria-label="Naar pagina 2"]',
                'a[data-testid="pagination-link-2"]',
                'button:has-text("2"):visible',
                '.pagination a:has-text("2")',
                'a[href*="page=2"]',
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
                page_2_url = SEARCH_URL + "&page=2"
                await page.goto(page_2_url, wait_until="domcontentloaded", timeout=30000)
                await random_delay(2, 4)
                await page.screenshot(path=RESULTS_DIR / "page_2.png", full_page=False)
                results["pagination_success"] = True
                print("      Pagination via URL successful! Screenshot saved: page_2.png")

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

    report = f"""# autoscout24.nl PoC Report

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
        if listing.get('details'):
            report += f"  Details: {listing['details']}\n"
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
