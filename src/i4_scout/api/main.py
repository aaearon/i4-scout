"""FastAPI application factory and configuration."""

from fastapi import FastAPI

from i4_scout.api.routes import config, listings, scrape, stats


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(
        title="i4-scout API",
        description="BMW i4 eDrive40 listing scraper API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Include routers
    app.include_router(listings.router, prefix="/api/listings", tags=["listings"])
    app.include_router(config.router, prefix="/api/config", tags=["config"])
    app.include_router(stats.router, prefix="/api/stats", tags=["stats"])
    app.include_router(scrape.router, prefix="/api/scrape/jobs", tags=["scrape"])

    @app.get("/health", tags=["health"])
    async def health_check() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "healthy"}

    return app


# Create app instance for uvicorn
app = create_app()
