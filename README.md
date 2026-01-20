# BMW i4 Car Scraper

CLI tool to scrape BMW i4 eDrive40 listings from AutoScout24 DE/NL, match against user-defined options, and store results in SQLite.

## Features

- Scrape listings from AutoScout24 Germany and Netherlands
- Match listings against configurable option requirements
- Store results in SQLite with price history tracking
- Export to CSV/JSON

## Installation

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install package
pip install -e .

# Install Playwright browsers
playwright install chromium
```

## Usage

```bash
# Initialize database
car-scraper init-database

# Scrape listings
car-scraper scrape autoscout24_de --max-pages 10
car-scraper scrape autoscout24_nl --max-pages 10

# List qualified listings
car-scraper list --qualified --min-score 80

# Show listing details
car-scraper show <listing_id>

# Export results
car-scraper export --format csv --qualified
```

## Configuration

Copy `config/options.example.yaml` to `config/options.yaml` and customize your required/nice-to-have options.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy src/

# Linting
ruff check src/
```

## License

MIT
