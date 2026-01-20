"""CLI interface for car-scraper."""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from car_scraper import __version__
from car_scraper.config import load_options_config
from car_scraper.database.engine import get_session, init_db
from car_scraper.database.repository import ListingRepository
from car_scraper.export.csv_exporter import export_to_csv
from car_scraper.export.json_exporter import export_to_json
from car_scraper.matching.option_matcher import match_options
from car_scraper.matching.scorer import calculate_score
from car_scraper.models.pydantic_models import ListingCreate, Source
from car_scraper.scrapers.autoscout24_de import AutoScout24DEScraper
from car_scraper.scrapers.autoscout24_nl import AutoScout24NLScraper
from car_scraper.scrapers.browser import BrowserConfig, BrowserManager

app = typer.Typer(
    name="car-scraper",
    help="BMW i4 eDrive40 listing scraper for AutoScout24 DE/NL",
    add_completion=False,
)
console = Console()


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"car-scraper version {__version__}")
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
    db_path: Optional[Path] = typer.Option(
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
        db_location = db_path or "data/car_scraper.db"
        console.print(f"[green]Database initialized at: {db_location}[/green]")
    except Exception as e:
        console.print(f"[red]Error initializing database: {e}[/red]")
        raise typer.Exit(1)


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
    config_path: Optional[Path],
) -> tuple[int, int, int]:
    """Run the scraping process.

    Returns:
        Tuple of (total_found, new_count, updated_count).
    """
    # Load options config
    options_config = load_options_config(config_path)

    # Setup browser
    browser_config = BrowserConfig(headless=headless)
    scraper_class = get_scraper_class(source)

    total_found = 0
    new_count = 0
    updated_count = 0

    async with BrowserManager(browser_config) as browser:
        scraper = scraper_class(browser)
        page = await browser.get_page()

        # Scrape search pages
        for page_num in range(1, max_pages + 1):
            console.print(f"  Scraping page {page_num}...", end="")

            try:
                listings_data = await scraper.scrape_search_page(page, page_num)
                console.print(f" found {len(listings_data)} listings")

                if not listings_data:
                    console.print("  No more listings found, stopping.")
                    break

                total_found += len(listings_data)

                # Process each listing
                with get_session() as session:
                    repo = ListingRepository(session)

                    for listing_data in listings_data:
                        # Get detail page for options and description
                        url = listing_data.get("url")
                        title = listing_data.get("title", "")
                        options_list = []
                        description = None
                        if url:
                            try:
                                detail = await scraper.scrape_listing_detail(page, url)
                                options_list = detail.options_list
                                description = detail.description
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
                        _, created = repo.upsert_listing(create_data)
                        if created:
                            new_count += 1
                        else:
                            updated_count += 1

                await scraper.random_delay()

            except Exception as e:
                console.print(f" [red]error: {e}[/red]")
                continue

    return total_found, new_count, updated_count


@app.command()
def scrape(
    source: Source = typer.Argument(
        ...,
        help="Source to scrape (autoscout24_de, autoscout24_nl).",
    ),
    max_pages: int = typer.Option(
        10,
        "--max-pages",
        "-p",
        help="Maximum number of pages to scrape.",
    ),
    headless: bool = typer.Option(
        True,
        "--headless/--no-headless",
        help="Run browser in headless mode.",
    ),
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to options config YAML file.",
    ),
) -> None:
    """Scrape listings from the specified source."""
    console.print(f"[bold blue]Scraping {source.value}...[/bold blue]")
    console.print(f"  Max pages: {max_pages}")
    console.print(f"  Headless: {headless}")

    # Ensure database exists
    init_db()

    try:
        total, new, updated = asyncio.run(run_scrape(source, max_pages, headless, config))
        console.print()
        console.print(f"[green]Scraping complete![/green]")
        console.print(f"  Total found: {total}")
        console.print(f"  New listings: {new}")
        console.print(f"  Updated: {updated}")
    except Exception as e:
        console.print(f"[red]Error during scraping: {e}[/red]")
        raise typer.Exit(1)


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
    source: Optional[Source] = typer.Option(
        None,
        "--source",
        help="Filter by source.",
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

        # Show total count
        total = repo.count_listings(source=source, qualified_only=qualified)
        if total > limit:
            console.print(f"[dim]Showing {limit} of {total} total listings[/dim]")


@app.command()
def show(
    listing_id: int = typer.Argument(..., help="Listing ID to show."),
) -> None:
    """Show detailed information for a specific listing."""
    # Ensure database exists
    init_db()

    with get_session() as session:
        repo = ListingRepository(session)
        listing = repo.get_listing_by_id(listing_id)

        if not listing:
            console.print(f"[red]Listing #{listing_id} not found.[/red]")
            raise typer.Exit(1)

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
    output: Optional[Path] = typer.Option(
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
    source: Optional[Source] = typer.Option(
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
