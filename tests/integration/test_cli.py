"""Integration tests for CLI commands."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from i4_scout.cli import app
from i4_scout.database.engine import init_db, reset_engine


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


class TestVersionOption:
    """Tests for --version option."""

    def test_version_flag(self, runner: CliRunner) -> None:
        """--version should show version and exit."""
        result = runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        assert "i4-scout version" in result.output


class TestHelpOption:
    """Tests for --help option."""

    def test_help_shows_available_commands(self, runner: CliRunner) -> None:
        """--help should show only the available commands."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        # Should show the kept commands
        assert "scrape" in result.output
        assert "recalculate-scores" in result.output
        assert "serve" in result.output

        # Should NOT show the removed commands
        assert "list " not in result.output  # Space to avoid matching "listings"
        assert "show " not in result.output  # Space to avoid matching "shows"
        assert "export " not in result.output
        assert "enrich" not in result.output


class TestRemovedCommands:
    """Tests that removed commands are no longer available."""

    def test_list_command_not_found(self, runner: CliRunner) -> None:
        """list command should not exist."""
        result = runner.invoke(app, ["list"])
        assert result.exit_code != 0
        assert "No such command" in result.output or "Error" in result.output

    def test_show_command_not_found(self, runner: CliRunner) -> None:
        """show command should not exist."""
        result = runner.invoke(app, ["show", "1"])
        assert result.exit_code != 0
        assert "No such command" in result.output or "Error" in result.output

    def test_export_command_not_found(self, runner: CliRunner) -> None:
        """export command should not exist."""
        result = runner.invoke(app, ["export"])
        assert result.exit_code != 0
        assert "No such command" in result.output or "Error" in result.output

    def test_enrich_command_not_found(self, runner: CliRunner) -> None:
        """enrich command should not exist."""
        result = runner.invoke(app, ["enrich", "1", "test.pdf"])
        assert result.exit_code != 0
        assert "No such command" in result.output or "Error" in result.output
