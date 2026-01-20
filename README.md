# i4-scout

CLI tool to scrape BMW i4 eDrive40 listings from AutoScout24 DE/NL, match against user-defined options, and store results in SQLite.

## Features

- Scrape listings from AutoScout24 Germany and Netherlands
- Match listings against configurable required/nice-to-have options
- Score and qualify listings based on option matches
- Export to CSV/JSON
- SQLite storage with price history tracking
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
# Initialize database
i4-scout init-database

# Configure options (copy and edit)
cp config/options.example.yaml config/options.yaml

# Scrape listings
i4-scout scrape autoscout24_de --max-pages 5

# List qualified listings
i4-scout list --qualified

# Show listing details
i4-scout show 1

# Export to CSV
i4-scout export --format csv --qualified
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `init-database` | Initialize SQLite database |
| `scrape <source>` | Scrape listings from source (autoscout24_de, autoscout24_nl) |
| `list` | List scraped listings with filters |
| `show <id>` | Show detailed listing information |
| `export` | Export listings to CSV/JSON |

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

# Run tests (146 tests)
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
│   ├── scrapers/           # Site scrapers (AutoScout24 DE/NL)
│   ├── matching/           # Option matching engine
│   ├── database/           # SQLAlchemy models & repository
│   └── export/             # CSV/JSON exporters
├── tests/
│   ├── unit/               # Unit tests
│   ├── integration/        # Integration tests
│   └── fixtures/           # HTML test fixtures
├── config/
│   └── options.yaml        # Options configuration
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
└── docs/
```

## License

MIT
