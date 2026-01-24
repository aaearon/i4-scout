# i4-scout

CLI tool to scrape BMW i4 listings from AutoScout24 DE/NL, match against user-defined options, and store results in SQLite.

## Features

- Scrape listings from AutoScout24 Germany and Netherlands
- Match listings against configurable required/nice-to-have options
- Score and qualify listings based on option matches
- Export to CSV/JSON
- SQLite storage with price history tracking and **price change visibility**
- **Web Interface** with dashboard, filtering, comparison, and favorites
- **REST API** for programmatic access
- PDF enrichment to extract options from dealer spec sheets
- Issue tracking and notes for dealer communication
- Vehicle color extraction (exterior, interior, material)
- Listing lifecycle tracking (active/delisted status, days on market)
- Photo gallery with lightbox viewer
- Docker support

## Installation

```bash
# Clone and setup
git clone <repository>
cd i4-scout
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Install Playwright browsers
playwright install chromium
```

## Quick Start

```bash
# Configure options (copy and edit)
cp config/options.example.yaml config/options.yaml

# Scrape listings (database auto-initializes on first use)
i4-scout scrape autoscout24_de --max-pages 5

# List qualified listings
i4-scout list --qualified

# Show listing details
i4-scout show 1

# Export to CSV
i4-scout export --format csv --qualified

# Start web interface
i4-scout serve
```

## Web Interface

Start the server with `i4-scout serve` and navigate to http://localhost:8000.

- **Dashboard**: Market pulse (7-day velocity), price drops, near-miss listings, feature rarity, favorites
- **Listings**: Filterable table with sorting, pagination, hover popovers, and status indicators
- **Photo Gallery**: Image viewer with thumbnails and lightbox
- **Price Changes**: Visual indicators for price drops (green) and increases (red)
- **Comparison**: Select up to 4 listings for side-by-side comparison (includes colors)
- **Copy to Clipboard**: Export selected listings as LLM-friendly markdown
- **Favorites**: Star listings (persisted in browser localStorage)
- **Issue Tracking**: Mark listings with issues (e.g., DEKRA findings)
- **Notes**: Add work log style notes to track dealer communication
- **PDF Enrichment**: Upload dealer spec PDFs to extract additional options
- **Scrape Control**: Start/stop scrapes with live progress tracking, job history

See [CLAUDE.md](CLAUDE.md) for full documentation.

## CLI Commands

| Command | Description |
|---------|-------------|
| `scrape <source>` | Scrape listings from source (autoscout24_de, autoscout24_nl) |
| `list` | List scraped listings with filters |
| `show <id>` | Show detailed listing information |
| `export` | Export listings to CSV/JSON |
| `recalculate-scores` | Recalculate match scores for all listings |
| `enrich <id> <pdf>` | Enrich listing with options from dealer PDF |
| `serve` | Start web interface and API server |

## Configuration

See `config/options.example.yaml` for configuration format. Copy to `config/options.yaml` and customize.

Documentation: [docs/options-config.md](docs/options-config.md)

## Docker

```bash
cd docker
docker-compose build
docker-compose run scrape-de  # Scrape German listings
docker-compose run scrape-nl  # Scrape Dutch listings
docker-compose run list       # List qualified listings
docker-compose run export     # Export to JSON
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run specific test file
pytest tests/unit/test_normalizer.py -v
```

## Project Structure

```
i4-scout/
├── src/i4_scout/
│   ├── cli.py              # CLI interface (Typer)
│   ├── config.py           # YAML config loader
│   ├── api/                # FastAPI routes and templates
│   ├── scrapers/           # Site scrapers (AutoScout24 DE/NL)
│   ├── matching/           # Option matching engine
│   ├── services/           # Business logic layer
│   ├── database/           # SQLAlchemy models & repository
│   ├── models/             # Pydantic & ORM models
│   └── export/             # CSV/JSON exporters
├── tests/
│   ├── unit/               # Unit tests
│   ├── integration/        # Integration tests
│   └── fixtures/           # HTML test fixtures
├── config/
│   └── options.yaml        # Options configuration
├── data/                   # Database & uploaded documents
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
└── docs/                   # Documentation (see ARCHITECTURE.md)
```

## License

MIT
