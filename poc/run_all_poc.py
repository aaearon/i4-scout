#!/usr/bin/env python3
"""
Run all PoC scripts and generate a summary report.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

from poc_mobile_de import run_poc as run_mobile_de
from poc_autoscout24_de import run_poc as run_autoscout24_de
from poc_autoscout24_nl import run_poc as run_autoscout24_nl


RESULTS_DIR = Path(__file__).parent / "results"


async def main():
    """Run all PoC scripts sequentially."""
    print("\n" + "=" * 70)
    print("BMW i4 eDrive40 Scraper - Full PoC Validation")
    print("=" * 70)
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 70)

    results = {}

    # Run each PoC
    print("\n[1/3] Running mobile.de PoC...")
    results["mobile_de"] = await run_mobile_de()

    print("\n[2/3] Running autoscout24.de PoC...")
    results["autoscout24_de"] = await run_autoscout24_de()

    print("\n[3/3] Running autoscout24.nl PoC...")
    results["autoscout24_nl"] = await run_autoscout24_nl()

    # Generate summary
    print("\n" + "=" * 70)
    print("POC SUMMARY")
    print("=" * 70)

    passed = 0
    failed = 0

    for site, result in results.items():
        status = "PASS" if result["success"] else "FAIL"
        if result["success"]:
            passed += 1
        else:
            failed += 1
        print(f"  {site:20s}: {status}")
        print(f"    - Listings: {len(result['listings'])}")
        print(f"    - Options: {len(result['options'])}")
        print(f"    - Pagination: {'Yes' if result['pagination_success'] else 'No'}")
        if result["errors"]:
            print(f"    - Errors: {result['errors']}")

    print("\n" + "-" * 70)
    print(f"TOTAL: {passed}/3 PASSED, {failed}/3 FAILED")

    # Gate decision
    if passed == 3:
        print("\nGATE DECISION: PROCEED to Phase 1")
    elif passed >= 1:
        print("\nGATE DECISION: PARTIAL SUCCESS - Review workarounds")
    else:
        print("\nGATE DECISION: STOP - Investigate alternatives")

    print("=" * 70)

    # Save combined results
    with open(RESULTS_DIR / "poc_summary.json", "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "passed": passed,
            "failed": failed,
            "results": results,
        }, f, indent=2, ensure_ascii=False)

    # Generate summary markdown
    generate_summary_markdown(results, passed, failed)

    return results


def generate_summary_markdown(results: dict, passed: int, failed: int):
    """Generate summary markdown report."""
    timestamp = datetime.now().isoformat()

    if passed == 3:
        gate_decision = "PROCEED to Phase 1"
    elif passed >= 1:
        gate_decision = "PARTIAL SUCCESS - Review workarounds"
    else:
        gate_decision = "STOP - Investigate alternatives"

    report = f"""# BMW i4 eDrive40 Scraper - PoC Summary

**Timestamp:** {timestamp}
**Gate Decision:** {gate_decision}
**Result:** {passed}/3 sites passed

## Site Results

| Site | Status | Listings | Options | Pagination |
|------|--------|----------|---------|------------|
"""

    for site, result in results.items():
        status = "PASS" if result["success"] else "FAIL"
        report += f"| {site} | {status} | {len(result['listings'])} | {len(result['options'])} | {'Yes' if result['pagination_success'] else 'No'} |\n"

    report += "\n## Individual Reports\n\n"
    for site in results:
        report += f"- [{site}]({site}/report.md)\n"

    report += "\n## Errors Summary\n\n"
    for site, result in results.items():
        if result["errors"]:
            report += f"### {site}\n"
            for err in result["errors"]:
                report += f"- {err}\n"
            report += "\n"

    report += """
## Next Steps

"""
    if passed == 3:
        report += """All sites passed! Proceed to Phase 1:
1. Create project structure
2. Implement Pydantic models
3. Set up SQLAlchemy ORM
4. Begin scraper infrastructure
"""
    elif passed >= 1:
        report += """Partial success. Consider:
1. Investigate failed sites for specific issues
2. Implement workarounds (proxy rotation, longer delays)
3. Decide whether to proceed with passing sites only
"""
    else:
        report += """All sites failed. Investigate:
1. Check if sites have changed their structure
2. Consider different anti-bot strategies
3. Evaluate alternative approaches (APIs, RSS feeds)
"""

    with open(RESULTS_DIR / "POC_SUMMARY.md", "w") as f:
        f.write(report)


if __name__ == "__main__":
    asyncio.run(main())
