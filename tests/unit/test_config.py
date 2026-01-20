"""Unit tests for YAML config loader - TDD approach."""

from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def sample_config_dict() -> dict[str, Any]:
    """Return a sample configuration dictionary."""
    return {
        "required": [
            {
                "name": "Head-Up Display",
                "aliases": ["HUD", "Head Up Display"],
                "category": "driver_assistance",
            }
        ],
        "nice_to_have": [
            {
                "name": "Laser Light",
                "aliases": ["Laserlicht"],
                "category": "exterior",
            },
            {
                "name": "M Sport Package",
                "aliases": ["M Sportpaket"],
                "is_bundle": True,
                "bundle_contents": ["M Sport suspension", "M Sport steering wheel"],
            },
        ],
        "dealbreakers": ["Unfallwagen", "Salvage"],
    }


@pytest.fixture
def temp_config_file(tmp_path: Path, sample_config_dict: dict[str, Any]) -> Path:
    """Create a temporary config file."""
    import yaml

    config_path = tmp_path / "options.yaml"
    with open(config_path, "w") as f:
        yaml.dump(sample_config_dict, f)
    return config_path


class TestConfigLoader:
    """Tests for the YAML config loader."""

    def test_load_config_from_path(self, temp_config_file: Path) -> None:
        """Should load config from a specified path."""
        from car_scraper.config import load_options_config

        config = load_options_config(temp_config_file)

        assert config is not None

    def test_load_config_returns_options_config(self, temp_config_file: Path) -> None:
        """Should return an OptionsConfig instance."""
        from car_scraper.config import load_options_config
        from car_scraper.models.pydantic_models import OptionsConfig

        config = load_options_config(temp_config_file)

        assert isinstance(config, OptionsConfig)

    def test_load_config_parses_required_options(self, temp_config_file: Path) -> None:
        """Should correctly parse required options."""
        from car_scraper.config import load_options_config

        config = load_options_config(temp_config_file)

        assert len(config.required) == 1
        assert config.required[0].name == "Head-Up Display"
        assert "HUD" in config.required[0].aliases

    def test_load_config_parses_nice_to_have_options(self, temp_config_file: Path) -> None:
        """Should correctly parse nice-to-have options."""
        from car_scraper.config import load_options_config

        config = load_options_config(temp_config_file)

        assert len(config.nice_to_have) == 2
        assert config.nice_to_have[0].name == "Laser Light"

    def test_load_config_parses_bundles(self, temp_config_file: Path) -> None:
        """Should correctly parse bundle configurations."""
        from car_scraper.config import load_options_config

        config = load_options_config(temp_config_file)

        m_sport = next(opt for opt in config.nice_to_have if opt.name == "M Sport Package")
        assert m_sport.is_bundle is True
        assert len(m_sport.bundle_contents) == 2
        assert "M Sport suspension" in m_sport.bundle_contents

    def test_load_config_parses_dealbreakers(self, temp_config_file: Path) -> None:
        """Should correctly parse dealbreakers list."""
        from car_scraper.config import load_options_config

        config = load_options_config(temp_config_file)

        assert len(config.dealbreakers) == 2
        assert "Unfallwagen" in config.dealbreakers

    def test_load_config_default_path(self) -> None:
        """Should load from default path when no path specified."""
        from car_scraper.config import load_options_config

        # This assumes config/options.yaml exists (created in setup)
        config = load_options_config()

        assert config is not None
        assert len(config.required) > 0

    def test_load_config_file_not_found(self, tmp_path: Path) -> None:
        """Should raise FileNotFoundError for missing config."""
        from car_scraper.config import load_options_config

        with pytest.raises(FileNotFoundError):
            load_options_config(tmp_path / "nonexistent.yaml")

    def test_load_config_invalid_yaml(self, tmp_path: Path) -> None:
        """Should raise error for invalid YAML."""
        from car_scraper.config import load_options_config

        invalid_path = tmp_path / "invalid.yaml"
        invalid_path.write_text("invalid: yaml: content: [")

        with pytest.raises(Exception):  # Could be yaml.YAMLError or ValidationError
            load_options_config(invalid_path)

    def test_load_config_empty_file(self, tmp_path: Path) -> None:
        """Should handle empty config file."""
        from car_scraper.config import load_options_config

        empty_path = tmp_path / "empty.yaml"
        empty_path.write_text("")

        config = load_options_config(empty_path)

        # Should return config with empty lists
        assert config.required == []
        assert config.nice_to_have == []
        assert config.dealbreakers == []

    def test_load_config_partial_config(self, tmp_path: Path) -> None:
        """Should handle config with only some sections."""
        import yaml
        from car_scraper.config import load_options_config

        partial_path = tmp_path / "partial.yaml"
        partial_path.write_text(yaml.dump({"dealbreakers": ["Unfallwagen"]}))

        config = load_options_config(partial_path)

        assert config.required == []
        assert config.nice_to_have == []
        assert len(config.dealbreakers) == 1

    def test_config_is_frozen(self, temp_config_file: Path) -> None:
        """OptionsConfig should be immutable (attribute reassignment)."""
        from pydantic import ValidationError
        from car_scraper.config import load_options_config

        config = load_options_config(temp_config_file)

        # Attempting to reassign attributes should raise error
        with pytest.raises(ValidationError):
            config.dealbreakers = ["New Dealbreaker"]  # type: ignore
