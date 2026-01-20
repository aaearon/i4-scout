"""CLI interface for car-scraper."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from car_scraper import __version__
from car_scraper.database.engine import init_db
from car_scraper.models.pydantic_models import Source

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
        engine = init_db(db_path, echo=verbose)
        db_location = db_path or "data/car_scraper.db"
        console.print(f"[green]Database initialized at: {db_location}[/green]")
    except Exception as e:
        console.print(f"[red]Error initializing database: {e}[/red]")
        raise typer.Exit(1)


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
) -> None:
    """Scrape listings from the specified source."""
    console.print(f"[bold blue]Scraping {source.value}...[/bold blue]")
    console.print(f"  Max pages: {max_pages}")
    console.print(f"  Headless: {headless}")

    # TODO: Implement scraping
    console.print("[yellow]Scraping not yet implemented.[/yellow]")


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
    console.print("[bold blue]Listings[/bold blue]")

    # TODO: Implement listing display
    table = Table(title="Car Listings")
    table.add_column("ID", style="cyan")
    table.add_column("Title", style="white")
    table.add_column("Price", style="green")
    table.add_column("Score", style="yellow")
    table.add_column("Source", style="blue")

    console.print(table)
    console.print("[yellow]Listing display not yet implemented.[/yellow]")


@app.command()
def show(
    listing_id: int = typer.Argument(..., help="Listing ID to show."),
) -> None:
    """Show detailed information for a specific listing."""
    console.print(f"[bold blue]Listing #{listing_id}[/bold blue]")

    # TODO: Implement listing detail display
    console.print("[yellow]Listing detail not yet implemented.[/yellow]")


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
) -> None:
    """Export listings to a file."""
    console.print(f"[bold blue]Exporting listings ({format})...[/bold blue]")

    # TODO: Implement export
    console.print("[yellow]Export not yet implemented.[/yellow]")


if __name__ == "__main__":
    app()
