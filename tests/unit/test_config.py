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
        from i4_scout.config import load_options_config

        config = load_options_config(temp_config_file)

        assert config is not None

    def test_load_config_returns_options_config(self, temp_config_file: Path) -> None:
        """Should return an OptionsConfig instance."""
        from i4_scout.config import load_options_config
        from i4_scout.models.pydantic_models import OptionsConfig

        config = load_options_config(temp_config_file)

        assert isinstance(config, OptionsConfig)

    def test_load_config_parses_required_options(self, temp_config_file: Path) -> None:
        """Should correctly parse required options."""
        from i4_scout.config import load_options_config

        config = load_options_config(temp_config_file)

        assert len(config.required) == 1
        assert config.required[0].name == "Head-Up Display"
        assert "HUD" in config.required[0].aliases

    def test_load_config_parses_nice_to_have_options(self, temp_config_file: Path) -> None:
        """Should correctly parse nice-to-have options."""
        from i4_scout.config import load_options_config

        config = load_options_config(temp_config_file)

        assert len(config.nice_to_have) == 2
        assert config.nice_to_have[0].name == "Laser Light"

    def test_load_config_parses_bundles(self, temp_config_file: Path) -> None:
        """Should correctly parse bundle configurations."""
        from i4_scout.config import load_options_config

        config = load_options_config(temp_config_file)

        m_sport = next(opt for opt in config.nice_to_have if opt.name == "M Sport Package")
        assert m_sport.is_bundle is True
        assert len(m_sport.bundle_contents) == 2
        assert "M Sport suspension" in m_sport.bundle_contents

    def test_load_config_parses_dealbreakers(self, temp_config_file: Path) -> None:
        """Should correctly parse dealbreakers list."""
        from i4_scout.config import load_options_config

        config = load_options_config(temp_config_file)

        assert len(config.dealbreakers) == 2
        assert "Unfallwagen" in config.dealbreakers

    def test_load_config_default_path(self) -> None:
        """Should load from default path when no path specified."""
        from i4_scout.config import load_options_config

        # This assumes config/options.yaml exists (created in setup)
        config = load_options_config()

        assert config is not None
        assert len(config.required) > 0

    def test_load_config_file_not_found(self, tmp_path: Path) -> None:
        """Should raise FileNotFoundError for missing config."""
        from i4_scout.config import load_options_config

        with pytest.raises(FileNotFoundError):
            load_options_config(tmp_path / "nonexistent.yaml")

    def test_load_config_invalid_yaml(self, tmp_path: Path) -> None:
        """Should raise error for invalid YAML."""
        from i4_scout.config import load_options_config

        invalid_path = tmp_path / "invalid.yaml"
        invalid_path.write_text("invalid: yaml: content: [")

        with pytest.raises(Exception):  # Could be yaml.YAMLError or ValidationError
            load_options_config(invalid_path)

    def test_load_config_empty_file(self, tmp_path: Path) -> None:
        """Should handle empty config file."""
        from i4_scout.config import load_options_config

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
        from i4_scout.config import load_options_config

        partial_path = tmp_path / "partial.yaml"
        partial_path.write_text(yaml.dump({"dealbreakers": ["Unfallwagen"]}))

        config = load_options_config(partial_path)

        assert config.required == []
        assert config.nice_to_have == []
        assert len(config.dealbreakers) == 1

    def test_config_is_frozen(self, temp_config_file: Path) -> None:
        """OptionsConfig should be immutable (attribute reassignment)."""
        from pydantic import ValidationError
        from i4_scout.config import load_options_config

        config = load_options_config(temp_config_file)

        # Attempting to reassign attributes should raise error
        with pytest.raises(ValidationError):
            config.dealbreakers = ["New Dealbreaker"]  # type: ignore


class TestSearchFiltersConfig:
    """Tests for loading search_filters from YAML config."""

    @pytest.fixture
    def config_with_filters_dict(self) -> dict[str, Any]:
        """Return a config dictionary with search_filters."""
        return {
            "required": [
                {"name": "HUD", "aliases": ["Head-Up Display"]},
            ],
            "dealbreakers": [],
            "search_filters": {
                "price_max_eur": 55000,
                "mileage_max_km": 50000,
                "year_min": 2023,
                "year_max": 2025,
                "countries": ["D", "NL"],
            },
        }

    @pytest.fixture
    def config_file_with_filters(
        self, tmp_path: Path, config_with_filters_dict: dict[str, Any]
    ) -> Path:
        """Create a temp config file with search_filters."""
        import yaml

        config_path = tmp_path / "options_with_filters.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config_with_filters_dict, f)
        return config_path

    def test_load_search_filters(self, config_file_with_filters: Path) -> None:
        """Should load search_filters from YAML config."""
        from i4_scout.config import load_search_filters

        filters = load_search_filters(config_file_with_filters)

        assert filters.price_max_eur == 55000
        assert filters.mileage_max_km == 50000
        assert filters.year_min == 2023
        assert filters.year_max == 2025
        assert filters.countries == ["D", "NL"]

    def test_load_search_filters_returns_search_filters_type(
        self, config_file_with_filters: Path
    ) -> None:
        """Should return a SearchFilters instance."""
        from i4_scout.config import load_search_filters
        from i4_scout.models.pydantic_models import SearchFilters

        filters = load_search_filters(config_file_with_filters)

        assert isinstance(filters, SearchFilters)

    def test_load_search_filters_missing_section(self, temp_config_file: Path) -> None:
        """Should return empty SearchFilters when section is missing."""
        from i4_scout.config import load_search_filters
        from i4_scout.models.pydantic_models import SearchFilters

        # temp_config_file doesn't have search_filters section
        filters = load_search_filters(temp_config_file)

        assert isinstance(filters, SearchFilters)
        assert filters.price_max_eur is None
        assert filters.countries is None

    def test_load_search_filters_partial(self, tmp_path: Path) -> None:
        """Should handle partial search_filters section."""
        import yaml
        from i4_scout.config import load_search_filters

        partial_path = tmp_path / "partial_filters.yaml"
        partial_path.write_text(yaml.dump({
            "search_filters": {
                "price_max_eur": 45000,
                "year_min": 2024,
            }
        }))

        filters = load_search_filters(partial_path)

        assert filters.price_max_eur == 45000
        assert filters.year_min == 2024
        assert filters.mileage_max_km is None
        assert filters.countries is None

    def test_load_full_config(self, config_file_with_filters: Path) -> None:
        """Should load both OptionsConfig and SearchFilters."""
        from i4_scout.config import load_full_config
        from i4_scout.models.pydantic_models import OptionsConfig, SearchFilters

        options_config, search_filters = load_full_config(config_file_with_filters)

        assert isinstance(options_config, OptionsConfig)
        assert isinstance(search_filters, SearchFilters)
        assert len(options_config.required) == 1
        assert search_filters.price_max_eur == 55000


class TestMergeSearchFilters:
    """Tests for merge_search_filters helper."""

    def test_merge_with_no_overrides(self) -> None:
        """Should return config filters when no overrides provided."""
        from i4_scout.config import merge_search_filters
        from i4_scout.models.pydantic_models import SearchFilters

        config_filters = SearchFilters(
            price_max_eur=55000,
            mileage_max_km=50000,
            year_min=2023,
            countries=["D", "NL"],
        )

        result = merge_search_filters(config_filters, {})

        assert result.price_max_eur == 55000
        assert result.mileage_max_km == 50000
        assert result.year_min == 2023
        assert result.countries == ["D", "NL"]

    def test_merge_overrides_take_precedence(self) -> None:
        """Overrides should take precedence over config values."""
        from i4_scout.config import merge_search_filters
        from i4_scout.models.pydantic_models import SearchFilters

        config_filters = SearchFilters(
            price_max_eur=55000,
            mileage_max_km=50000,
            year_min=2023,
        )
        overrides = {
            "price_max": 45000,
            "year_min": 2024,
        }

        result = merge_search_filters(config_filters, overrides)

        assert result.price_max_eur == 45000  # Overridden
        assert result.mileage_max_km == 50000  # From config
        assert result.year_min == 2024  # Overridden

    def test_merge_countries_override(self) -> None:
        """Should allow overriding countries list."""
        from i4_scout.config import merge_search_filters
        from i4_scout.models.pydantic_models import SearchFilters

        config_filters = SearchFilters(countries=["D", "NL"])
        overrides = {"countries": ["B", "A"]}

        result = merge_search_filters(config_filters, overrides)

        assert result.countries == ["B", "A"]

    def test_merge_preserves_year_max_from_config(self) -> None:
        """Should preserve year_max from config (no override support)."""
        from i4_scout.config import merge_search_filters
        from i4_scout.models.pydantic_models import SearchFilters

        config_filters = SearchFilters(year_max=2025)
        overrides = {}

        result = merge_search_filters(config_filters, overrides)

        assert result.year_max == 2025

    def test_merge_with_empty_config(self) -> None:
        """Should work with empty config filters."""
        from i4_scout.config import merge_search_filters
        from i4_scout.models.pydantic_models import SearchFilters

        config_filters = SearchFilters()
        overrides = {"price_max": 40000}

        result = merge_search_filters(config_filters, overrides)

        assert result.price_max_eur == 40000
        assert result.mileage_max_km is None

    def test_merge_returns_search_filters_type(self) -> None:
        """Should return a SearchFilters instance."""
        from i4_scout.config import merge_search_filters
        from i4_scout.models.pydantic_models import SearchFilters

        config_filters = SearchFilters()
        result = merge_search_filters(config_filters, {})

        assert isinstance(result, SearchFilters)
