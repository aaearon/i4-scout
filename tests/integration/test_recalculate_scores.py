"""Integration tests for recalculate-scores command."""

import json
import os
from datetime import date
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from i4_scout.cli import app
from i4_scout.database.engine import get_session, init_db, reset_engine
from i4_scout.database.repository import ListingRepository
from i4_scout.models.pydantic_models import ListingCreate, OptionConfig, OptionsConfig, Source


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def test_db(tmp_path: Path) -> Path:
    """Create a test database."""
    reset_engine()

    db_path = tmp_path / "test.db"
    os.environ["I4_SCOUT_DB_PATH"] = str(db_path)
    init_db(db_path)
    yield db_path

    reset_engine()
    if "I4_SCOUT_DB_PATH" in os.environ:
        del os.environ["I4_SCOUT_DB_PATH"]


@pytest.fixture
def sample_config() -> OptionsConfig:
    """Create a sample options config for testing."""
    return OptionsConfig(
        required=[
            OptionConfig(name="Head-Up Display", aliases=["HUD"]),
            OptionConfig(name="Harman Kardon", aliases=["HK"]),
        ],
        nice_to_have=[
            OptionConfig(name="Seat Heating", aliases=["Sitzheizung"]),
            OptionConfig(name="Laser Light", aliases=["Laserlicht"]),
        ],
        dealbreakers=["Unfallwagen"],
    )


@pytest.fixture
def test_config_file(tmp_path: Path, sample_config: OptionsConfig) -> Path:
    """Create a test config file."""
    config_dict = {
        "required": [
            {"name": opt.name, "aliases": opt.aliases}
            for opt in sample_config.required
        ],
        "nice_to_have": [
            {"name": opt.name, "aliases": opt.aliases}
            for opt in sample_config.nice_to_have
        ],
        "dealbreakers": sample_config.dealbreakers,
    }
    config_path = tmp_path / "test_options.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config_dict, f)
    return config_path


@pytest.fixture
def populated_db_with_options(test_db: Path, sample_config: OptionsConfig) -> Path:
    """Create a test database with listings that have matched options."""
    with get_session() as session:
        repo = ListingRepository(session)

        # Create listing with all required and some nice-to-have
        listing1 = repo.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com/listing1",
                title="BMW i4 with HUD and HK",
                price=45000,
                mileage_km=15000,
                first_registration=date(2023, 3, 1),
                match_score=93.2,  # Old score with 10:1 ratio
                is_qualified=True,
            )
        )

        # Add matched options for listing1
        hud, _ = repo.get_or_create_option("Head-Up Display")
        hk, _ = repo.get_or_create_option("Harman Kardon")
        seat, _ = repo.get_or_create_option("Seat Heating")
        repo.add_option_to_listing(listing1.id, hud.id)
        repo.add_option_to_listing(listing1.id, hk.id)
        repo.add_option_to_listing(listing1.id, seat.id)

        # Create listing with only some required
        listing2 = repo.create_listing(
            ListingCreate(
                source=Source.AUTOSCOUT24_DE,
                url="https://example.com/listing2",
                title="BMW i4 with HUD only",
                price=40000,
                mileage_km=20000,
                first_registration=date(2023, 1, 1),
                match_score=43.5,  # Old score
                is_qualified=False,
            )
        )

        # Add matched options for listing2 (only HUD)
        repo.add_option_to_listing(listing2.id, hud.id)

    return test_db


class TestRecalculateScoresCommand:
    """Tests for recalculate-scores command."""

    def test_recalculate_empty_db(
        self, runner: CliRunner, test_db: Path, test_config_file: Path
    ) -> None:
        """recalculate-scores should work on empty database."""
        result = runner.invoke(app, ["recalculate-scores", "-c", str(test_config_file)])

        assert result.exit_code == 0
        assert "Recalculation complete" in result.output
        assert "Total listings processed: 0" in result.output

    def test_recalculate_updates_scores(
        self, runner: CliRunner, populated_db_with_options: Path, test_config_file: Path
    ) -> None:
        """recalculate-scores should update scores with new weights."""
        result = runner.invoke(app, ["recalculate-scores", "-c", str(test_config_file)])

        assert result.exit_code == 0
        assert "Recalculation complete" in result.output
        assert "Total listings processed: 2" in result.output
        assert "Scores changed: 2" in result.output

    def test_recalculate_json_output(
        self, runner: CliRunner, populated_db_with_options: Path, test_config_file: Path
    ) -> None:
        """recalculate-scores --json should output valid JSON."""
        result = runner.invoke(
            app, ["recalculate-scores", "--json", "-c", str(test_config_file)]
        )

        assert result.exit_code == 0

        # Parse JSON output
        output = json.loads(result.output)
        assert output["status"] == "success"
        assert output["total_processed"] == 2
        assert output["score_changed"] == 2
        assert "changes" in output
        assert len(output["changes"]) == 2

        # Verify change details
        changes_by_id = {c["id"]: c for c in output["changes"]}

        # Listing 1: 2 required + 1 nice-to-have matched
        # New score: (2*75 + 1*25) / (2*75 + 2*25) * 100 = 175/200 * 100 = 87.5%
        listing1_change = changes_by_id[1]
        assert listing1_change["old_score"] == 93.2
        assert listing1_change["new_score"] == 87.5
        assert listing1_change["old_qualified"] is True
        assert listing1_change["new_qualified"] is True

        # Listing 2: 1 required, 0 nice-to-have matched
        # New score: (1*75 + 0*25) / (2*75 + 2*25) * 100 = 75/200 * 100 = 37.5%
        listing2_change = changes_by_id[2]
        assert listing2_change["old_score"] == 43.5
        assert listing2_change["new_score"] == 37.5
        assert listing2_change["old_qualified"] is False
        assert listing2_change["new_qualified"] is False


class TestRecalculateScoresService:
    """Unit tests for recalculate_scores service method."""

    def test_score_recalculation_math(
        self, test_db: Path, sample_config: OptionsConfig
    ) -> None:
        """Verify score recalculation uses correct weights."""
        from i4_scout.services.listing_service import ListingService

        with get_session() as session:
            repo = ListingRepository(session)

            # Create listing with known options
            listing = repo.create_listing(
                ListingCreate(
                    source=Source.AUTOSCOUT24_DE,
                    url="https://example.com/test",
                    title="Test listing",
                    price=50000,
                    mileage_km=10000,
                    match_score=0.0,  # Will be recalculated
                    is_qualified=False,
                )
            )

            # Add 2 required + 1 nice-to-have options
            hud, _ = repo.get_or_create_option("Head-Up Display")
            hk, _ = repo.get_or_create_option("Harman Kardon")
            seat, _ = repo.get_or_create_option("Seat Heating")
            repo.add_option_to_listing(listing.id, hud.id)
            repo.add_option_to_listing(listing.id, hk.id)
            repo.add_option_to_listing(listing.id, seat.id)

        # Recalculate
        with get_session() as session:
            service = ListingService(session)
            result = service.recalculate_scores(sample_config)

            assert result.total_processed == 1
            assert result.score_changed == 1

            # Verify new score: (2*75 + 1*25) / (2*75 + 2*25) * 100 = 87.5
            change = result.changes[0]
            assert change["new_score"] == 87.5
            assert change["new_qualified"] is True

    def test_qualification_changes(
        self, test_db: Path, sample_config: OptionsConfig
    ) -> None:
        """Verify qualification status is recalculated correctly."""
        from i4_scout.services.listing_service import ListingService

        with get_session() as session:
            repo = ListingRepository(session)

            # Create listing missing one required option
            listing = repo.create_listing(
                ListingCreate(
                    source=Source.AUTOSCOUT24_DE,
                    url="https://example.com/test",
                    title="Test listing",
                    price=50000,
                    mileage_km=10000,
                    match_score=50.0,
                    is_qualified=True,  # Incorrectly marked as qualified
                )
            )

            # Add only 1 of 2 required options
            hud, _ = repo.get_or_create_option("Head-Up Display")
            repo.add_option_to_listing(listing.id, hud.id)

        # Recalculate
        with get_session() as session:
            service = ListingService(session)
            result = service.recalculate_scores(sample_config)

            assert result.qualification_changed == 1
            assert result.changes[0]["old_qualified"] is True
            assert result.changes[0]["new_qualified"] is False
