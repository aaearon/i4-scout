"""YAML configuration loader for options config."""

from pathlib import Path
from typing import Any

import yaml

from i4_scout.models.pydantic_models import OptionConfig, OptionsConfig


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
