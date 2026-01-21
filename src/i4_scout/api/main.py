"""FastAPI application factory and configuration."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from i4_scout.api.routes import config, documents, listings, partials, scrape, stats, web

# Static files directory
STATIC_DIR = Path(__file__).parent.parent / "static"


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

    # Mount static files
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Include API routers
    app.include_router(listings.router, prefix="/api/listings", tags=["listings"])
    app.include_router(documents.router, prefix="/api/listings", tags=["documents"])
    app.include_router(config.router, prefix="/api/config", tags=["config"])
    app.include_router(stats.router, prefix="/api/stats", tags=["stats"])
    app.include_router(scrape.router, prefix="/api/scrape/jobs", tags=["scrape"])

    # Include web routers (HTML pages)
    app.include_router(web.router, tags=["web"])
    app.include_router(partials.router, tags=["partials"])

    @app.get("/health", tags=["health"])
    async def health_check() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "healthy"}

    return app


# Create app instance for uvicorn
app = create_app()
