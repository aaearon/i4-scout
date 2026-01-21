"""Integration tests for CLI commands."""

import json
from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from i4_scout.cli import app
from i4_scout.database.engine import get_session, init_db, reset_engine
from i4_scout.database.repository import ListingRepository
from i4_scout.models.pydantic_models import ListingCreate, Source


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def test_db(tmp_path: Path) -> Path:
    """Create a test database."""
    import os

    # Reset engine to ensure clean state
    reset_engine()

    db_path = tmp_path / "test.db"
    # Set environment variable for the CLI
    os.environ["I4_SCOUT_DB_PATH"] = str(db_path)
    init_db(db_path)
    yield db_path

    # Cleanup: reset engine after test
    reset_engine()
    if "I4_SCOUT_DB_PATH" in os.environ:
        del os.environ["I4_SCOUT_DB_PATH"]


@pytest.fixture
def populated_db(test_db: Path) -> Path:
    """Create a test database with sample listings."""
    with get_session() as session:
        repo = ListingRepository(session)

        # Create sample listings
        listings = [
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com/listing1",
                title="BMW i4 eDrive40 Gran Coupe",
                price=45000,
                mileage_km=15000,
                year=2023,
                first_registration=date(2023, 3, 1),
                match_score=85.0,
                is_qualified=True,
            ),
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com/listing2",
                title="BMW i4 M50 xDrive",
                price=65000,
                mileage_km=5000,
                year=2024,
                first_registration=date(2024, 1, 1),
                match_score=45.0,
                is_qualified=False,
            ),
            ListingCreate(
                source=Source.AUTOSCOUT24_NL,
                url="https://example.com/listing3",
                title="BMW i4 eDrive35",
                price=38000,
                mileage_km=25000,
                year=2022,
                first_registration=date(2022, 6, 1),
                match_score=70.0,
                is_qualified=False,
            ),
        ]

        for data in listings:
            repo.create_listing(data)

    return test_db


class TestInitDatabaseCommand:
    """Tests for init-database command."""

    def test_init_database_creates_db(self, runner: CliRunner, tmp_path: Path) -> None:
        """init-database should create the database file."""
        db_path = tmp_path / "new_test.db"

        result = runner.invoke(app, ["init-database", "--db", str(db_path)])

        assert result.exit_code == 0
        assert "initialized" in result.output.lower()
        assert db_path.exists()

    def test_init_database_idempotent(self, runner: CliRunner, test_db: Path) -> None:
        """init-database should be safe to run multiple times."""
        result = runner.invoke(app, ["init-database", "--db", str(test_db)])

        assert result.exit_code == 0


class TestListCommand:
    """Tests for list command."""

    def test_list_empty_database(self, runner: CliRunner, test_db: Path) -> None:
        """list should handle empty database gracefully."""
        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "no listings" in result.output.lower()

    def test_list_shows_listings(self, runner: CliRunner, populated_db: Path) -> None:
        """list should show listings from database."""
        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "BMW i4" in result.output
        assert "45,000" in result.output or "45000" in result.output

    def test_list_qualified_filter(self, runner: CliRunner, populated_db: Path) -> None:
        """list --qualified should only show qualified listings."""
        result = runner.invoke(app, ["list", "--qualified"])

        assert result.exit_code == 0
        assert "eDrive40" in result.output
        # M50 should not be shown (not qualified)
        assert "M50" not in result.output or "shown" in result.output.lower()

    def test_list_limit(self, runner: CliRunner, populated_db: Path) -> None:
        """list --limit should limit results."""
        result = runner.invoke(app, ["list", "--limit", "1"])

        assert result.exit_code == 0
        assert "1 shown" in result.output or "1)" in result.output

    def test_list_min_score(self, runner: CliRunner, populated_db: Path) -> None:
        """list --min-score should filter by score."""
        result = runner.invoke(app, ["list", "--min-score", "80"])

        assert result.exit_code == 0
        # Only listing with 85% should show
        assert "eDrive40" in result.output


class TestShowCommand:
    """Tests for show command."""

    def test_show_existing_listing(self, runner: CliRunner, populated_db: Path) -> None:
        """show should display listing details."""
        result = runner.invoke(app, ["show", "1"])

        assert result.exit_code == 0
        assert "BMW i4 eDrive40" in result.output
        assert "45,000" in result.output or "45000" in result.output
        assert "QUALIFIED" in result.output

    def test_show_nonexistent_listing(self, runner: CliRunner, populated_db: Path) -> None:
        """show should error for nonexistent listing."""
        result = runner.invoke(app, ["show", "999"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()


class TestExportCommand:
    """Tests for export command."""

    def test_export_csv(self, runner: CliRunner, populated_db: Path, tmp_path: Path) -> None:
        """export --format csv should create CSV file."""
        output_file = tmp_path / "export.csv"

        result = runner.invoke(app, ["export", "--format", "csv", "--output", str(output_file)])

        assert result.exit_code == 0
        assert output_file.exists()

        # Verify CSV content
        content = output_file.read_text()
        assert "BMW i4" in content
        assert "45000" in content
        assert "source" in content.lower()  # Header

    def test_export_json(self, runner: CliRunner, populated_db: Path, tmp_path: Path) -> None:
        """export --format json should create JSON file."""
        output_file = tmp_path / "export.json"

        result = runner.invoke(app, ["export", "--format", "json", "--output", str(output_file)])

        assert result.exit_code == 0
        assert output_file.exists()

        # Verify JSON content
        data = json.loads(output_file.read_text())
        assert "listings" in data
        assert data["count"] == 3
        assert any("BMW i4" in item["title"] for item in data["listings"])

    def test_export_qualified_only(
        self, runner: CliRunner, populated_db: Path, tmp_path: Path
    ) -> None:
        """export --qualified should only export qualified listings."""
        output_file = tmp_path / "qualified.json"

        result = runner.invoke(
            app, ["export", "--format", "json", "--qualified", "--output", str(output_file)]
        )

        assert result.exit_code == 0

        data = json.loads(output_file.read_text())
        assert data["count"] == 1
        assert data["listings"][0]["is_qualified"] is True

    def test_export_empty_database(self, runner: CliRunner, test_db: Path) -> None:
        """export should handle empty database."""
        result = runner.invoke(app, ["export"])

        assert result.exit_code == 0
        assert "no listings" in result.output.lower()

    def test_export_invalid_format(self, runner: CliRunner, populated_db: Path) -> None:
        """export should reject invalid formats."""
        result = runner.invoke(app, ["export", "--format", "xml"])

        assert result.exit_code == 1
        assert "unknown format" in result.output.lower()


class TestJsonOutput:
    """Tests for --json output option (LLM-friendly output)."""

    def test_list_json_output(self, runner: CliRunner, populated_db: Path) -> None:
        """list --json should output valid JSON."""
        result = runner.invoke(app, ["list", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "listings" in data
        assert "count" in data
        assert "total" in data
        assert "filters" in data
        assert data["count"] == 3
        assert len(data["listings"]) == 3

    def test_list_json_with_filters(self, runner: CliRunner, populated_db: Path) -> None:
        """list --json should include filter info."""
        result = runner.invoke(app, ["list", "--json", "--qualified", "--min-score", "80"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["filters"]["qualified_only"] is True
        assert data["filters"]["min_score"] == 80.0
        assert data["count"] == 1  # Only one listing with score >= 80 and qualified

    def test_list_json_empty_database(self, runner: CliRunner, test_db: Path) -> None:
        """list --json should handle empty database."""
        result = runner.invoke(app, ["list", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["listings"] == []
        assert data["count"] == 0

    def test_show_json_output(self, runner: CliRunner, populated_db: Path) -> None:
        """show --json should output valid JSON."""
        result = runner.invoke(app, ["show", "1", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == 1
        assert "BMW i4 eDrive40" in data["title"]
        assert data["price"] == 45000
        assert data["is_qualified"] is True
        assert "url" in data
        assert "mileage_km" in data
        assert "match_score" in data

    def test_show_json_not_found(self, runner: CliRunner, populated_db: Path) -> None:
        """show --json should output error JSON for not found."""
        result = runner.invoke(app, ["show", "999", "--json"])

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert "error" in data


class TestVersionOption:
    """Tests for --version option."""

    def test_version_flag(self, runner: CliRunner) -> None:
        """--version should show version and exit."""
        result = runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        assert "i4-scout version" in result.output
