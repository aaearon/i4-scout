"""YAML configuration loader for options config."""

from pathlib import Path
from typing import Any

import yaml

from i4_scout.models.pydantic_models import OptionConfig, OptionsConfig, SearchFilters


def load_options_config(path: Path | None = None) -> OptionsConfig:
    """Load and validate options configuration from YAML.

    Args:
        path: Path to YAML config file. If None, uses default config/options.yaml.

    Returns:
        Validated OptionsConfig instance.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        yaml.YAMLError: If YAML parsing fails.
        ValidationError: If config doesn't match expected schema.
    """
    if path is None:
        # Default path relative to project root
        path = Path(__file__).parent.parent.parent / "config" / "options.yaml"

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "r") as f:
        raw_config: dict[str, Any] | None = yaml.safe_load(f)

    # Handle empty config file
    if raw_config is None:
        raw_config = {}

    # Parse required options
    required = _parse_option_list(raw_config.get("required", []))

    # Parse nice-to-have options
    nice_to_have = _parse_option_list(raw_config.get("nice_to_have", []))

    # Dealbreakers are simple strings
    dealbreakers = raw_config.get("dealbreakers", [])

    return OptionsConfig(
        required=required,
        nice_to_have=nice_to_have,
        dealbreakers=dealbreakers,
    )


def _parse_option_list(options_data: list[dict[str, Any]]) -> list[OptionConfig]:
    """Parse a list of option configurations.

    Args:
        options_data: List of option dictionaries from YAML.

    Returns:
        List of validated OptionConfig instances.
    """
    options = []
    for opt_dict in options_data:
        option = OptionConfig(
            name=opt_dict["name"],
            aliases=opt_dict.get("aliases", []),
            category=opt_dict.get("category"),
            is_bundle=opt_dict.get("is_bundle", False),
            bundle_contents=opt_dict.get("bundle_contents", []),
        )
        options.append(option)
    return options


def _get_default_config_path() -> Path:
    """Get the default config path relative to project root."""
    return Path(__file__).parent.parent.parent / "config" / "options.yaml"


def _load_raw_config(path: Path | None = None) -> dict[str, Any]:
    """Load raw YAML config from path.

    Args:
        path: Path to YAML config file. If None, uses default config/options.yaml.

    Returns:
        Raw config dictionary.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        yaml.YAMLError: If YAML parsing fails.
    """
    if path is None:
        path = _get_default_config_path()

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "r") as f:
        raw_config: dict[str, Any] | None = yaml.safe_load(f)

    return raw_config if raw_config is not None else {}


def load_search_filters(path: Path | None = None) -> SearchFilters:
    """Load search filters from YAML configuration.

    Args:
        path: Path to YAML config file. If None, uses default config/options.yaml.

    Returns:
        SearchFilters instance with values from config (or defaults if not specified).
    """
    raw_config = _load_raw_config(path)
    filters_dict = raw_config.get("search_filters", {})

    return SearchFilters(
        price_max_eur=filters_dict.get("price_max_eur"),
        mileage_max_km=filters_dict.get("mileage_max_km"),
        year_min=filters_dict.get("year_min"),
        year_max=filters_dict.get("year_max"),
        countries=filters_dict.get("countries"),
    )


def load_full_config(path: Path | None = None) -> tuple[OptionsConfig, SearchFilters]:
    """Load both OptionsConfig and SearchFilters from YAML configuration.

    Args:
        path: Path to YAML config file. If None, uses default config/options.yaml.

    Returns:
        Tuple of (OptionsConfig, SearchFilters).
    """
    return load_options_config(path), load_search_filters(path)


def merge_search_filters(
    config_filters: SearchFilters,
    overrides: dict[str, Any],
) -> SearchFilters:
    """Merge CLI/API overrides with config filters.

    Overrides take precedence over config values.

    Args:
        config_filters: Base search filters from config.
        overrides: Dict with override values. Keys:
            - price_max: Override price_max_eur
            - mileage_max: Override mileage_max_km
            - year_min: Override year_min
            - countries: Override countries list

    Returns:
        New SearchFilters with merged values.
    """
    return SearchFilters(
        price_max_eur=overrides.get("price_max") or config_filters.price_max_eur,
        mileage_max_km=overrides.get("mileage_max") or config_filters.mileage_max_km,
        year_min=overrides.get("year_min") or config_filters.year_min,
        year_max=config_filters.year_max,
        countries=overrides.get("countries") or config_filters.countries,
    )
