# BMW i4 eDrive40 Scraper - PoC Summary

**Date:** 2026-01-20
**Status:** PARTIAL SUCCESS (2/3 sites passed)

## Executive Summary

| Site | Status | Listings | Options | Pagination | Blocker |
|------|--------|----------|---------|------------|---------|
| autoscout24.de | PASS | 10 | 50 | Yes | None |
| autoscout24.nl | PASS | 10 | 50 | Yes | None |
| mobile.de | FAIL | 0 | 0 | No | Bot detection ("Zugriff verweigert") |

## Gate Decision

**Recommendation: PROCEED with AutoScout24 sites, defer mobile.de**

### Rationale

1. **AutoScout24 (DE + NL):** Both sites work reliably with playwright-stealth
   - Successfully extract listings, prices, and equipment details
   - Pagination works via URL parameters
   - Same codebase can serve both sites with minimal changes

2. **mobile.de:** Strong bot detection blocks access
   - Returns "Zugriff verweigert" (Access Denied) immediately
   - Would require advanced countermeasures:
     - Residential proxy rotation
     - Browser fingerprint spoofing
     - CAPTCHA solving service
     - Potentially non-headless browser with display

### Proposed Path Forward

1. **Phase 1+:** Implement full scraper for AutoScout24 DE and NL
2. **Future:** Investigate mobile.de workarounds:
   - Residential proxy services (e.g., Bright Data, Oxylabs)
   - Playwright with undetected-chromedriver patterns
   - Official API access (if available)

## Detailed Results

### autoscout24.de - PASS

**Search URL:** `https://www.autoscout24.de/lst/bmw/i4?atype=C&cy=D&desc=0&fregfrom=2022&sort=standard&source=homepage_search-mask&ustate=N%2CU`

**Sample Listings Extracted:**
- BMW i4 eDrive40 Gran Coupe DAB Tempomat Klimaaut. - €34,990
- BMW i4 eDrive40 Gran Coupe AHK+Navi+Pano+SHZ+HiFi - €34,845
- BMW i4 eDrive40 Gran Coupe | Live Cockpit Plus - €36,901

**Sample Equipment Extracted:**
- Einparkhilfe (Parking assist)
- Kamera (Camera)
- Sensoren hinten/vorne (Sensors)
- Klimaautomatik (Climate control)
- Lederausstattung (Leather)
- Navigationssystem (Navigation)
- Sitzheizung (Seat heating)
- Tempomat (Cruise control)

### autoscout24.nl - PASS

**Search URL:** `https://www.autoscout24.nl/lst/bmw/i4?atype=C&cy=NL&desc=0&fregfrom=2022&sort=standard&source=homepage_search-mask&ustate=N%2CU`

**Sample Listings Extracted:**
- BMW i4 eDrive40 High Executive M Sport - €47,950
- BMW i4 eDrive40 High Exec. M-Sport | HUD | Leer - €39,900
- BMW i4 eDrive35 High Executive M-Sport | Harman/Kardon - €44,950

**Sample Equipment Extracted (Dutch):**
- Airconditioning
- Automatische klimaatregeling, 2 zones
- Cruise Control
- Lederen bekleding (Leather upholstery)
- Navigatiesysteem (Navigation system)

### mobile.de - FAIL

**Search URL:** `https://suchen.mobile.de/fahrzeuge/search.html?dam=0&isSearchRequest=true&ms=3500%3B53%3B%3Bi4&ref=quickSearch&sb=rel&vc=Car`

**Error:** "Zugriff verweigert" (Access Denied)
- Reference Error: 0.8f477b5c.1768935224.2b58b98
- Bot detection triggered despite playwright-stealth

**Screenshot:** Shows access denied page with contact information

## Technical Notes

### Working Approach (AutoScout24)

```python
# Stealth configuration that works
stealth = Stealth(
    navigator_languages_override=("de-DE", "de", "en"),
    navigator_platform_override="Win32",
)

# Browser context settings
context = await browser.new_context(
    viewport={"width": 1920, "height": 1080},
    locale="de-DE",
    timezone_id="Europe/Berlin",
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36..."
)
```

### Equipment Extraction Pattern

AutoScout24 stores equipment in collapsed `childContainer` elements. Key approach:
1. Scroll to load content
2. Click expand buttons
3. Find containers with equipment keywords
4. Split text on capital letters to extract individual items

### Selector Strategy

**Listings:**
- Primary: `a[href*="/angebote/"][href*="/bmw/"]` (DE)
- Primary: `a[href*="/aanbod/"][href*="/bmw/"]` (NL)

**Equipment:**
- Containers: `[class*="childContainer"]`, `[class*="collapsed"]`
- Keywords: einparkhilfe, klimaautomatik, navigation, sitzheizung, etc.

## Files Generated

```
poc/results/
├── autoscout24_de/
│   ├── search_results.png
│   ├── search_results.html
│   ├── detail_page.png
│   ├── detail_page.html
│   ├── page_2.png
│   ├── results.json
│   └── report.md
├── autoscout24_nl/
│   ├── (same structure)
├── mobile_de/
│   ├── search_results.png  (shows access denied)
│   ├── results.json
│   └── report.md
└── POC_SUMMARY.md
```

## Recommendations for Phase 1

1. **Proceed with AutoScout24 implementation**
2. **Create unified BaseScraper** that handles both DE and NL variants
3. **Implement robust error handling** for transient failures
4. **Add rate limiting** (2-5 second delays between requests)
5. **Context rotation** every 10-20 requests
6. **Consider mobile.de** in a future phase with proxy infrastructure
