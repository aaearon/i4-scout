"""CLI interface for i4-scout."""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from i4_scout import __version__
from i4_scout.config import load_options_config, load_search_filters
from i4_scout.database.engine import get_session, init_db
from i4_scout.database.repository import ListingRepository
from i4_scout.export.csv_exporter import export_to_csv
from i4_scout.export.json_exporter import export_to_json
from i4_scout.matching.option_matcher import match_options
from i4_scout.matching.scorer import calculate_score
from i4_scout.models.pydantic_models import ListingCreate, SearchFilters, Source
from i4_scout.scrapers.autoscout24_de import AutoScout24DEScraper
from i4_scout.scrapers.autoscout24_nl import AutoScout24NLScraper
from i4_scout.scrapers.browser import BrowserConfig, BrowserManager

app = typer.Typer(
    name="i4-scout",
    help="BMW i4 eDrive40 listing scraper for AutoScout24 DE/NL",
    add_completion=False,
)
console = Console()


def listing_to_dict(listing: Any) -> dict[str, Any]:
    """Convert a Listing ORM object to a JSON-serializable dict."""
    return {
        "id": listing.id,
        "source": listing.source.value if listing.source else None,
        "external_id": listing.external_id,
        "url": listing.url,
        "title": listing.title,
        "price": listing.price,
        "mileage_km": listing.mileage_km,
        "year": listing.year,
        "first_registration": listing.first_registration,
        "vin": listing.vin,
        "location_city": listing.location_city,
        "location_zip": listing.location_zip,
        "location_country": listing.location_country,
        "dealer_name": listing.dealer_name,
        "dealer_type": listing.dealer_type,
        "description": listing.description,
        "match_score": listing.match_score,
        "is_qualified": listing.is_qualified,
        "matched_options": listing.matched_options,
        "first_seen_at": listing.first_seen_at.isoformat() if listing.first_seen_at else None,
        "last_seen_at": listing.last_seen_at.isoformat() if listing.last_seen_at else None,
    }


def output_json(data: Any) -> None:
    """Output JSON to stdout (for LLM consumption)."""
    print(json.dumps(data, indent=2, ensure_ascii=False))


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"i4-scout version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """BMW i4 eDrive40 listing scraper."""
    pass


@app.command()
def init_database(
    db_path: Path | None = typer.Option(
        None,
        "--db",
        "-d",
        help="Path to SQLite database file.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-V",
        help="Show SQL statements.",
    ),
) -> None:
    """Initialize the database, creating all tables."""
    console.print("[bold blue]Initializing database...[/bold blue]")

    try:
        init_db(db_path, echo=verbose)
        db_location = db_path or "data/i4_scout.db"
        console.print(f"[green]Database initialized at: {db_location}[/green]")
    except Exception as e:
        console.print(f"[red]Error initializing database: {e}[/red]")
        raise typer.Exit(1) from e


def get_scraper_class(source: Source) -> type:
    """Get the scraper class for a source."""
    scrapers = {
        Source.AUTOSCOUT24_DE: AutoScout24DEScraper,
        Source.AUTOSCOUT24_NL: AutoScout24NLScraper,
    }
    if source not in scrapers:
        raise ValueError(f"No scraper available for {source.value}")
    return scrapers[source]


async def run_scrape(
    source: Source,
    max_pages: int,
    headless: bool,
    config_path: Path | None,
    quiet: bool = False,
    search_filters: SearchFilters | None = None,
    use_cache: bool = True,
) -> dict[str, int]:
    """Run the scraping process.

    Args:
        source: The source to scrape.
        max_pages: Maximum pages to scrape.
        headless: Run browser in headless mode.
        config_path: Path to options config YAML.
        quiet: Suppress progress output (for JSON mode).
        search_filters: Optional search filters to apply.
        use_cache: Whether to use HTML caching.

    Returns:
        Dict with counts: total_found, new_listings, updated_listings, skipped_unchanged, fetched_details.
    """
    # Load options config
    options_config = load_options_config(config_path)

    # Setup browser
    browser_config = BrowserConfig(headless=headless)
    scraper_class = get_scraper_class(source)

    total_found = 0
    new_count = 0
    updated_count = 0
    skipped_count = 0
    fetched_count = 0
    pages_scraped = 0

    async with BrowserManager(browser_config) as browser:
        scraper = scraper_class(browser)
        page = await browser.get_page()

        # Scrape search pages
        for page_num in range(1, max_pages + 1):
            if not quiet:
                console.print(f"\n[bold]Page {page_num}[/bold] - Fetching search results...", end="")

            try:
                listings_data = await scraper.scrape_search_page(
                    page, page_num, search_filters, use_cache=use_cache
                )
                page_listing_count = len(listings_data)

                if not listings_data:
                    if not quiet:
                        console.print(" [yellow]no listings found, stopping.[/yellow]")
                    break

                pages_scraped += 1
                if not quiet:
                    console.print(f" [green]{page_listing_count} listings[/green]")

                # Process each listing
                with get_session() as session:
                    repo = ListingRepository(session)

                    for idx, listing_data in enumerate(listings_data, 1):
                        url = listing_data.get("url")
                        title = listing_data.get("title", "")
                        price = listing_data.get("price")

                        # Check if we can skip the detail fetch
                        if url and repo.listing_exists_with_price(url, price):
                            skipped_count += 1
                            total_found += 1
                            if not quiet:
                                console.print(
                                    f"  [{idx}/{page_listing_count}] {title[:50]}... [dim]SKIP[/dim] (unchanged)"
                                )
                            # Update last_seen_at for the existing listing
                            existing = repo.get_listing_by_url(url)
                            if existing:
                                repo.update_listing(existing.id)
                            continue

                        if not quiet:
                            console.print(
                                f"  [{idx}/{page_listing_count}] Processing: {title[:50]}...",
                                end="",
                            )

                        # Get detail page for options and description
                        options_list = []
                        description = None
                        if url:
                            try:
                                detail = await scraper.scrape_listing_detail(
                                    page, url, use_cache=use_cache
                                )
                                options_list = detail.options_list
                                description = detail.description
                                fetched_count += 1
                            except Exception:
                                pass

                        # Combine title and description for text search
                        # Title often contains abbreviated option codes (ACC, KZU, HUD, etc.)
                        searchable_text = title
                        if description:
                            searchable_text = f"{title}\n{description}"

                        # Match options (searches options list + title/description)
                        match_result = match_options(options_list, options_config, searchable_text)
                        scored_result = calculate_score(match_result, options_config)

                        # Create listing data
                        create_data = ListingCreate(
                            source=source,
                            external_id=listing_data.get("external_id"),
                            url=url or "",
                            title=listing_data.get("title", ""),
                            price=listing_data.get("price"),
                            mileage_km=listing_data.get("mileage_km"),
                            first_registration=listing_data.get("first_registration"),
                            description=description,
                            match_score=scored_result.score,
                            is_qualified=scored_result.is_qualified,
                        )

                        # Upsert to database
                        listing, created = repo.upsert_listing(create_data)
                        if created:
                            new_count += 1
                            status = "[green]NEW[/green]"
                        else:
                            updated_count += 1
                            status = "[blue]UPD[/blue]"
                            # Clear existing options for re-scraped listings
                            repo.clear_listing_options(listing.id)

                        # Store matched options
                        all_matched = (
                            match_result.matched_required + match_result.matched_nice_to_have
                        )
                        for option_name in all_matched:
                            option, _ = repo.get_or_create_option(option_name)
                            repo.add_option_to_listing(listing.id, option.id)

                        total_found += 1

                        if not quiet:
                            score_display = f"{scored_result.score:.0f}%"
                            qual = "[green]Q[/green]" if scored_result.is_qualified else "[dim]·[/dim]"
                            console.print(f" {status} {qual} {score_display}")

                if not quiet:
                    console.print(
                        f"  [dim]Running total: {total_found} found, {new_count} new, {updated_count} updated[/dim]"
                    )

                await scraper.random_delay()

            except Exception as e:
                if not quiet:
                    console.print(f" [red]error: {e}[/red]")
                continue

    return {
        "total_found": total_found,
        "new_listings": new_count,
        "updated_listings": updated_count,
        "skipped_unchanged": skipped_count,
        "fetched_details": fetched_count,
    }


@app.command()
def scrape(
    source: Source = typer.Argument(
        ...,
        help="Source to scrape (autoscout24_de, autoscout24_nl).",
    ),
    max_pages: int = typer.Option(
        50,
        "--max-pages",
        "-p",
        help="Maximum pages to scrape (stops early if no more results).",
    ),
    headless: bool = typer.Option(
        True,
        "--headless/--no-headless",
        help="Run browser in headless mode.",
    ),
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to options config YAML file.",
    ),
    price_max: int | None = typer.Option(
        None,
        "--price-max",
        "-P",
        help="Maximum price in EUR (overrides config).",
    ),
    mileage_max: int | None = typer.Option(
        None,
        "--mileage-max",
        "-M",
        help="Maximum mileage in km (overrides config).",
    ),
    year_min: int | None = typer.Option(
        None,
        "--year-min",
        "-Y",
        help="Minimum first registration year (overrides config).",
    ),
    country: list[str] | None = typer.Option(
        None,
        "--country",
        "-C",
        help="Country codes to include (can specify multiple, e.g., -C D -C NL).",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON (for LLM/programmatic consumption).",
    ),
    no_cache: bool = typer.Option(
        False,
        "--no-cache",
        help="Disable HTML caching (cache is enabled by default).",
    ),
) -> None:
    """Scrape listings from the specified source."""
    # Load search filters from config
    config_filters = load_search_filters(config)

    # Merge CLI overrides with config values (CLI takes precedence)
    search_filters = SearchFilters(
        price_max_eur=price_max if price_max is not None else config_filters.price_max_eur,
        mileage_max_km=mileage_max if mileage_max is not None else config_filters.mileage_max_km,
        year_min=year_min if year_min is not None else config_filters.year_min,
        year_max=config_filters.year_max,  # No CLI override for year_max
        countries=country if country else config_filters.countries,
    )

    use_cache = not no_cache

    if not json_output:
        console.print(f"[bold blue]Scraping {source.value}[/bold blue]")
        console.print(f"  Page limit: {max_pages} (stops early if no more results)")
        console.print(f"  Headless: {headless}")
        console.print(f"  Cache: {'enabled' if use_cache else 'disabled'}")
        # Show active filters
        if search_filters.price_max_eur:
            console.print(f"  Max price: {search_filters.price_max_eur:,} EUR")
        if search_filters.mileage_max_km:
            console.print(f"  Max mileage: {search_filters.mileage_max_km:,} km")
        if search_filters.year_min:
            console.print(f"  Min year: {search_filters.year_min}")
        if search_filters.countries:
            console.print(f"  Countries: {', '.join(search_filters.countries)}")

    # Ensure database exists
    init_db()

    try:
        results = asyncio.run(
            run_scrape(
                source, max_pages, headless, config, quiet=json_output,
                search_filters=search_filters, use_cache=use_cache
            )
        )

        if json_output:
            output_json({
                "status": "success",
                "source": source.value,
                "max_pages": max_pages,
                "cache_enabled": use_cache,
                "results": results,
            })
        else:
            console.print()
            console.print("[green]Scraping complete![/green]")
            console.print(f"  Total found: {results['total_found']}")
            console.print(f"  New listings: {results['new_listings']}")
            console.print(f"  Updated: {results['updated_listings']}")
            console.print(f"  Skipped (unchanged): {results['skipped_unchanged']}")
            console.print(f"  Detail pages fetched: {results['fetched_details']}")
    except Exception as e:
        if json_output:
            output_json({
                "status": "error",
                "source": source.value,
                "error": str(e),
            })
        else:
            console.print(f"[red]Error during scraping: {e}[/red]")
        raise typer.Exit(1) from e


@app.command(name="list")
def list_listings(
    qualified: bool = typer.Option(
        False,
        "--qualified",
        "-q",
        help="Show only qualified listings.",
    ),
    min_score: float = typer.Option(
        0.0,
        "--min-score",
        "-s",
        help="Minimum match score.",
    ),
    limit: int = typer.Option(
        20,
        "--limit",
        "-l",
        help="Maximum number of listings to show.",
    ),
    source: Source | None = typer.Option(
        None,
        "--source",
        help="Filter by source.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON (for LLM/programmatic consumption).",
    ),
) -> None:
    """List scraped listings."""
    # Ensure database exists
    init_db()

    with get_session() as session:
        repo = ListingRepository(session)
        listings = repo.get_listings(
            source=source,
            qualified_only=qualified,
            min_score=min_score if min_score > 0 else None,
            limit=limit,
        )
        total = repo.count_listings(source=source, qualified_only=qualified)

        # JSON output for LLM consumption
        if json_output:
            output_json({
                "listings": [listing_to_dict(listing) for listing in listings],
                "count": len(listings),
                "total": total,
                "filters": {
                    "qualified_only": qualified,
                    "min_score": min_score if min_score > 0 else None,
                    "source": source.value if source else None,
                    "limit": limit,
                },
            })
            return

        if not listings:
            console.print("[yellow]No listings found.[/yellow]")
            return

        table = Table(title=f"Car Listings ({len(listings)} shown)")
        table.add_column("ID", style="cyan", justify="right")
        table.add_column("Title", style="white", max_width=40)
        table.add_column("Price", style="green", justify="right")
        table.add_column("Mileage", style="blue", justify="right")
        table.add_column("Score", style="yellow", justify="right")
        table.add_column("Qual", style="magenta", justify="center")
        table.add_column("Source", style="dim")

        for listing in listings:
            price_str = f"{listing.price:,}" if listing.price else "-"
            mileage_str = f"{listing.mileage_km:,} km" if listing.mileage_km else "-"
            score_str = f"{listing.match_score:.0f}%" if listing.match_score else "-"
            qual_str = "[green]Y[/green]" if listing.is_qualified else "[red]N[/red]"
            source_str = listing.source.value.split("_")[-1].upper() if listing.source else "-"

            table.add_row(
                str(listing.id),
                listing.title[:40] if listing.title else "-",
                price_str,
                mileage_str,
                score_str,
                qual_str,
                source_str,
            )

        console.print(table)

        if total > limit:
            console.print(f"[dim]Showing {limit} of {total} total listings[/dim]")


@app.command()
def show(
    listing_id: int = typer.Argument(..., help="Listing ID to show."),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON (for LLM/programmatic consumption).",
    ),
) -> None:
    """Show detailed information for a specific listing."""
    # Ensure database exists
    init_db()

    with get_session() as session:
        repo = ListingRepository(session)
        listing = repo.get_listing_by_id(listing_id)

        if not listing:
            if json_output:
                output_json({"error": f"Listing #{listing_id} not found"})
            else:
                console.print(f"[red]Listing #{listing_id} not found.[/red]")
            raise typer.Exit(1)

        # JSON output for LLM consumption
        if json_output:
            output_json(listing_to_dict(listing))
            return

        # Build detail panel
        qual_status = "[green]QUALIFIED[/green]" if listing.is_qualified else "[red]NOT QUALIFIED[/red]"

        details = [
            f"[bold]Title:[/bold] {listing.title}",
            f"[bold]Source:[/bold] {listing.source.value if listing.source else 'Unknown'}",
            f"[bold]URL:[/bold] {listing.url}",
            "",
            f"[bold]Price:[/bold] {listing.price:,} EUR" if listing.price else "[bold]Price:[/bold] -",
            f"[bold]Mileage:[/bold] {listing.mileage_km:,} km" if listing.mileage_km else "[bold]Mileage:[/bold] -",
            f"[bold]Year:[/bold] {listing.year}" if listing.year else "[bold]Year:[/bold] -",
            f"[bold]First Registration:[/bold] {listing.first_registration or '-'}",
            f"[bold]VIN:[/bold] {listing.vin or '-'}",
            "",
            f"[bold]Location:[/bold] {listing.location_city or '-'}, {listing.location_country or '-'}",
            f"[bold]Dealer:[/bold] {listing.dealer_name or '-'} ({listing.dealer_type or '-'})",
            "",
            f"[bold]Match Score:[/bold] {listing.match_score:.1f}%" if listing.match_score else "[bold]Match Score:[/bold] -",
            f"[bold]Status:[/bold] {qual_status}",
            "",
            f"[bold]First Seen:[/bold] {listing.first_seen_at.strftime('%Y-%m-%d %H:%M') if listing.first_seen_at else '-'}",
            f"[bold]Last Seen:[/bold] {listing.last_seen_at.strftime('%Y-%m-%d %H:%M') if listing.last_seen_at else '-'}",
        ]

        if listing.matched_options:
            details.append("")
            details.append(f"[bold]Matched Options:[/bold] {', '.join(listing.matched_options)}")

        panel = Panel(
            "\n".join(details),
            title=f"[bold blue]Listing #{listing.id}[/bold blue]",
            expand=False,
        )
        console.print(panel)


@app.command()
def export(
    format: str = typer.Option(
        "csv",
        "--format",
        "-f",
        help="Export format (csv, json).",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path.",
    ),
    qualified: bool = typer.Option(
        False,
        "--qualified",
        "-q",
        help="Export only qualified listings.",
    ),
    source: Source | None = typer.Option(
        None,
        "--source",
        help="Filter by source.",
    ),
    min_score: float = typer.Option(
        0.0,
        "--min-score",
        "-s",
        help="Minimum match score.",
    ),
) -> None:
    """Export listings to a file."""
    if format not in ("csv", "json"):
        console.print(f"[red]Unknown format: {format}. Use 'csv' or 'json'.[/red]")
        raise typer.Exit(1)

    # Ensure database exists
    init_db()

    with get_session() as session:
        repo = ListingRepository(session)
        listings = repo.get_listings(
            source=source,
            qualified_only=qualified,
            min_score=min_score if min_score > 0 else None,
        )

        if not listings:
            console.print("[yellow]No listings to export.[/yellow]")
            return

        # Determine output path
        if output is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output = Path(f"listings_{timestamp}.{format}")

        console.print(f"[bold blue]Exporting {len(listings)} listings to {output}...[/bold blue]")

        if format == "csv":
            export_to_csv(listings, output)
        else:
            export_to_json(listings, output)

        console.print(f"[green]Export complete: {output}[/green]")


if __name__ == "__main__":
    app()
