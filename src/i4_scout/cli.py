"""CLI interface for i4-scout."""

import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from i4_scout import __version__
from i4_scout.config import load_options_config, load_search_filters, merge_search_filters
from i4_scout.database.engine import get_session
from i4_scout.models.pydantic_models import ScrapeProgress, ScrapeStatus, Source
from i4_scout.services import JobService, ListingService, ScrapeService

app = typer.Typer(
    name="i4-scout",
    help="BMW i4 listing scraper for AutoScout24 DE/NL",
    add_completion=False,
)
console = Console()


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


    job_id: int | None = None
    was_cancelled = False

    try:
        # Create job record and run scrape
        with get_session() as session:
            job_service = JobService(session)

            # Create job before starting
            search_filters_dict = search_filters.model_dump() if search_filters else None
            job = job_service.create_job(
                source=source,
                max_pages=max_pages,
                search_filters=search_filters_dict,
            )
            job_id = job.id
            job_service.update_status(job_id, ScrapeStatus.RUNNING)

            if not json_output:
                console.print(f"  Job ID: {job_id}")

            # Create cancellation check function (uses separate session)
            def check_cancelled() -> bool:
                with get_session() as check_session:
                    check_job = JobService(check_session).get_job(job_id)
                    return check_job is not None and check_job.status == ScrapeStatus.CANCELLED

            # Create combined progress callback
            cli_callback = _create_progress_callback(quiet=json_output)

            def combined_progress(progress: ScrapeProgress) -> None:
                # Update job progress
                job_service.update_progress(
                    job_id,
                    current_page=progress.page,
                    total_found=progress.listings_found,
                    new_listings=progress.new_count,
                    updated_listings=progress.updated_count,
                )
                # Also call CLI callback if present
                if cli_callback:
                    cli_callback(progress)

            # Run scrape
            service = ScrapeService(session, options_config)
            result = asyncio.run(
                service.run_scrape(
                    source=source,
                    max_pages=max_pages,
                    search_filters=search_filters,
                    headless=headless,
                    use_cache=use_cache,
                    force_refresh=force_refresh,
                    progress_callback=combined_progress,
                    is_cancelled=check_cancelled,
                    job_id=job_id,
                )
            )

            # Check if job was cancelled from web UI
            if check_cancelled():
                was_cancelled = True
                if not json_output:
                    console.print()
                    console.print("[yellow]Scrape was cancelled from web interface[/yellow]")
            else:
                # Mark job as completed
                job_service.complete_job(
                    job_id,
                    total_found=result.total_found,
                    new_listings=result.new_listings,
                    updated_listings=result.updated_listings,
                )

        if was_cancelled:
            if json_output:
                output_json({
                    "status": "cancelled",
                    "source": source.value,
                    "job_id": job_id,
                    "results": result.model_dump(),
                })
            raise typer.Exit(0)

        if json_output:
            output_json({
                "status": "success",
                "source": source.value,
                "job_id": job_id,
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

    except KeyboardInterrupt:
        # Handle Ctrl+C as cancellation
        if job_id is not None:
            with get_session() as session:
                JobService(session).cancel_job(job_id)
        if not json_output:
            console.print()
            console.print("[yellow]Scrape cancelled by user (Ctrl+C)[/yellow]")
        raise typer.Exit(130) from None

    except Exception as e:
        # Mark job as failed
        if job_id is not None:
            try:
                with get_session() as session:
                    JobService(session).fail_job(job_id, str(e))
            except Exception:
                pass  # Best effort

        if json_output:
            output_json({
                "status": "error",
                "source": source.value,
                "job_id": job_id,
                "error": str(e),
            })
        else:
            console.print(f"[red]Error during scraping: {e}[/red]")
        raise typer.Exit(1) from e


@app.command(name="recalculate-scores")
def recalculate_scores(
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
    """Recalculate scores for all listings using current weights.

    This command recalculates match_score and is_qualified for all listings
    based on the current scoring weights and options configuration. Useful
    after changing scoring weights to update existing listings without
    re-scraping.
    """
    # Load config
    options_config = load_options_config(config)


    if not json_output:
        console.print("[bold blue]Recalculating scores for all listings...[/bold blue]")

    with get_session() as session:
        service = ListingService(session)
        result = service.recalculate_scores(options_config)

        if json_output:
            output_json({
                "status": "success",
                "total_processed": result.total_processed,
                "score_changed": result.score_changed,
                "qualification_changed": result.qualification_changed,
                "changes": result.changes,
            })
        else:
            console.print()
            console.print("[green]Recalculation complete![/green]")
            console.print(f"  Total listings processed: {result.total_processed}")
            console.print(f"  Scores changed: {result.score_changed}")
            console.print(f"  Qualification changed: {result.qualification_changed}")

            if result.changes:
                console.print()
                console.print("[bold]Changes:[/bold]")
                for change in result.changes[:20]:  # Show first 20
                    qual_change = ""
                    if change["old_qualified"] != change["new_qualified"]:
                        qual_change = " [yellow](qualification changed)[/yellow]"
                    console.print(
                        f"  #{change['id']}: {change['old_score']}% -> "
                        f"{change['new_score']}%{qual_change}"
                    )
                if len(result.changes) > 20:
                    console.print(f"  ... and {len(result.changes) - 20} more")


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
