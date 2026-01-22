"""CLI interface for i4-scout."""

import asyncio
import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from i4_scout import __version__
from i4_scout.config import load_options_config, load_search_filters, merge_search_filters
from i4_scout.database.engine import get_session, init_db
from i4_scout.database.repository import ListingRepository
from i4_scout.export.csv_exporter import export_to_csv
from i4_scout.export.json_exporter import export_to_json
from i4_scout.models.pydantic_models import ScrapeProgress, Source
from i4_scout.services import DocumentService, ListingService, ScrapeService
from i4_scout.services.document_service import (
    InvalidFileError,
    ListingNotFoundError,
)

app = typer.Typer(
    name="i4-scout",
    help="BMW i4 listing scraper for AutoScout24 DE/NL",
    add_completion=False,
)
console = Console()


def _listing_read_to_dict(listing: Any) -> dict[str, Any]:
    """Convert a ListingRead to a JSON-serializable dict."""
    data: dict[str, Any] = listing.model_dump()
    # Convert source enum to string value
    if data.get("source"):
        data["source"] = data["source"].value
    # Convert datetime objects to ISO format strings
    if data.get("first_seen_at"):
        data["first_seen_at"] = data["first_seen_at"].isoformat()
    if data.get("last_seen_at"):
        data["last_seen_at"] = data["last_seen_at"].isoformat()
    # Convert date objects to MM/YYYY format
    if data.get("first_registration"):
        fr = data["first_registration"]
        data["first_registration"] = fr.strftime("%m/%Y") if hasattr(fr, "strftime") else str(fr)
    return data


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
    """BMW i4 listing scraper."""
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


def _create_progress_callback(quiet: bool) -> Callable[[ScrapeProgress], None] | None:
    """Create a progress callback for CLI output.

    Args:
        quiet: If True, return None (no output).

    Returns:
        Progress callback function or None.
    """
    if quiet:
        return None

    last_page = [0]  # Use list for mutability in closure
    listing_idx = [0]  # Track current listing within page

    def callback(progress: ScrapeProgress) -> None:
        # New page started
        if progress.page != last_page[0]:
            if last_page[0] > 0:
                console.print(
                    f"  [dim]Running total: {progress.listings_found} found, "
                    f"{progress.new_count} new, {progress.updated_count} updated[/dim]"
                )
            last_page[0] = progress.page
            listing_idx[0] = 0
            console.print(f"\n[bold]Page {progress.page}[/bold] - Fetching search results...")

        # Individual listing update
        if progress.current_listing:
            listing_idx[0] += 1
            title = progress.current_listing[:50]
            console.print(f"  Processing: {title}...")

    return callback


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
    force_refresh: bool = typer.Option(
        False,
        "--force-refresh",
        help="Force re-fetch detail pages for all listings (ignores skip optimization).",
    ),
) -> None:
    """Scrape listings from the specified source."""
    # Load config
    options_config = load_options_config(config)
    config_filters = load_search_filters(config)

    # Build overrides dict
    overrides: dict[str, Any] = {}
    if price_max is not None:
        overrides["price_max"] = price_max
    if mileage_max is not None:
        overrides["mileage_max"] = mileage_max
    if year_min is not None:
        overrides["year_min"] = year_min
    if country:
        overrides["countries"] = country

    # Merge CLI overrides with config values
    search_filters = merge_search_filters(config_filters, overrides)
    use_cache = not no_cache

    if not json_output:
        console.print(f"[bold blue]Scraping {source.value}[/bold blue]")
        console.print(f"  Page limit: {max_pages} (stops early if no more results)")
        console.print(f"  Headless: {headless}")
        console.print(f"  Cache: {'enabled' if use_cache else 'disabled'}")
        if force_refresh:
            console.print("  Force refresh: [yellow]enabled[/yellow] (re-fetching all details)")
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
        # Use ScrapeService
        with get_session() as session:
            service = ScrapeService(session, options_config)
            progress_callback = _create_progress_callback(quiet=json_output)

            result = asyncio.run(
                service.run_scrape(
                    source=source,
                    max_pages=max_pages,
                    search_filters=search_filters,
                    headless=headless,
                    use_cache=use_cache,
                    force_refresh=force_refresh,
                    progress_callback=progress_callback,
                )
            )

        if json_output:
            output_json({
                "status": "success",
                "source": source.value,
                "max_pages": max_pages,
                "cache_enabled": use_cache,
                "results": result.model_dump(),
            })
        else:
            console.print()
            console.print("[green]Scraping complete![/green]")
            console.print(f"  Total found: {result.total_found}")
            console.print(f"  New listings: {result.new_listings}")
            console.print(f"  Updated: {result.updated_listings}")
            console.print(f"  Skipped (unchanged): {result.skipped_unchanged}")
            console.print(f"  Detail pages fetched: {result.fetched_details}")
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
        service = ListingService(session)
        listings, total = service.get_listings(
            source=source,
            qualified_only=qualified,
            min_score=min_score if min_score > 0 else None,
            limit=limit,
        )

        # JSON output for LLM consumption
        if json_output:
            output_json({
                "listings": [_listing_read_to_dict(listing) for listing in listings],
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
        service = ListingService(session)
        listing = service.get_listing(listing_id)

        if not listing:
            if json_output:
                output_json({"error": f"Listing #{listing_id} not found"})
            else:
                console.print(f"[red]Listing #{listing_id} not found.[/red]")
            raise typer.Exit(1)

        # JSON output for LLM consumption
        if json_output:
            output_json(_listing_read_to_dict(listing))
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


@app.command()
def enrich(
    listing_id: int = typer.Argument(..., help="Listing ID to enrich."),
    pdf_path: Path = typer.Argument(..., help="Path to dealer PDF file."),
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to options config YAML file.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON (for LLM/programmatic consumption).",
    ),
) -> None:
    """Enrich a listing with options from a dealer PDF file.

    Extracts text and option codes from the PDF, matches against options config,
    adds new options to the listing, and recalculates the match score.
    """
    # Load config
    options_config = load_options_config(config)

    # Validate PDF path
    if not pdf_path.exists():
        if json_output:
            output_json({"error": f"PDF file not found: {pdf_path}"})
        else:
            console.print(f"[red]PDF file not found: {pdf_path}[/red]")
        raise typer.Exit(1)

    if not pdf_path.suffix.lower() == ".pdf":
        if json_output:
            output_json({"error": "File must have .pdf extension"})
        else:
            console.print("[red]File must have .pdf extension[/red]")
        raise typer.Exit(1)

    # Ensure database exists
    init_db()

    if not json_output:
        console.print(f"[bold blue]Enriching listing #{listing_id} with {pdf_path.name}[/bold blue]")

    try:
        with get_session() as session:
            service = DocumentService(session, options_config)

            # Read PDF content
            pdf_content = pdf_path.read_bytes()

            # Upload document
            service.upload_document(
                listing_id=listing_id,
                file_content=pdf_content,
                original_filename=pdf_path.name,
            )

            # Process document
            result = service.process_document(listing_id)

            if json_output:
                output_json({
                    "listing_id": result.listing_id,
                    "document_id": result.document_id,
                    "options_found": result.options_found,
                    "new_options_added": result.new_options_added,
                    "score_before": result.score_before,
                    "score_after": result.score_after,
                    "is_qualified_before": result.is_qualified_before,
                    "is_qualified_after": result.is_qualified_after,
                })
            else:
                console.print()
                console.print("[green]Enrichment complete![/green]")
                console.print(f"  Options found in PDF: {len(result.options_found)}")
                if result.options_found:
                    console.print(f"    {', '.join(result.options_found)}")
                console.print(f"  New options added: {len(result.new_options_added)}")
                if result.new_options_added:
                    console.print(f"    {', '.join(result.new_options_added)}")
                console.print(f"  Score: {result.score_before:.1f}% -> {result.score_after:.1f}%")

                # Qualification status change
                if result.is_qualified_after and not result.is_qualified_before:
                    console.print("[bold green]  Listing is now QUALIFIED![/bold green]")
                elif result.is_qualified_after:
                    console.print("  Status: Qualified")
                else:
                    console.print("  Status: Not Qualified")

    except ListingNotFoundError as e:
        if json_output:
            output_json({"error": str(e)})
        else:
            console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e
    except InvalidFileError as e:
        if json_output:
            output_json({"error": str(e)})
        else:
            console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e
    except Exception as e:
        if json_output:
            output_json({"error": f"Unexpected error: {e}"})
        else:
            console.print(f"[red]Unexpected error: {e}[/red]")
        raise typer.Exit(1) from e


@app.command()
def serve(
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        "-h",
        help="Host to bind to.",
    ),
    port: int = typer.Option(
        8000,
        "--port",
        "-p",
        help="Port to bind to.",
    ),
    reload: bool = typer.Option(
        False,
        "--reload",
        "-r",
        help="Enable auto-reload (for development).",
    ),
) -> None:
    """Start the API server."""
    import uvicorn

    # Ensure database exists
    init_db()

    console.print("[bold blue]Starting API server...[/bold blue]")
    console.print(f"  Host: {host}")
    console.print(f"  Port: {port}")
    console.print(f"  Reload: {reload}")
    console.print(f"  Docs: http://{host}:{port}/docs")
    console.print()

    uvicorn.run(
        "i4_scout.api.main:app",
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    app()
