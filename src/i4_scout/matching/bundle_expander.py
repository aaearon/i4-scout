"""Bundle expansion for option matching."""

from i4_scout.matching.normalizer import normalize_text
from i4_scout.models.pydantic_models import OptionsConfig


def expand_bundles(raw_options: list[str], config: OptionsConfig) -> list[str]:
    """Expand detected bundles to their constituent options.

    Two-pass approach:
    1. Normalize all raw options and bundle aliases
    2. Check if any normalized option matches a bundle alias
    3. If found, inject bundle_contents into effective options list
    4. Remove duplicates while preserving order

    Args:
        raw_options: List of raw option strings from listing.
        config: Options configuration with bundle definitions.

    Returns:
        Expanded list of options (original + bundle contents).

    Example:
        >>> config = OptionsConfig(nice_to_have=[
        ...     OptionConfig(name="M Sport Package", aliases=["M Sportpaket"],
        ...                  is_bundle=True, bundle_contents=["M Sport suspension"])
        ... ])
        >>> expand_bundles(["M Sportpaket", "Sitzheizung"], config)
        ['M Sportpaket', 'Sitzheizung', 'M Sport suspension']
    """
    if not raw_options:
        return []

    # Build bundle alias map: normalized_alias -> bundle contents
    bundle_map: dict[str, list[str]] = {}

    # Check both required and nice_to_have for bundles
    all_options = list(config.required) + list(config.nice_to_have)

    for opt_config in all_options:
        if opt_config.is_bundle and opt_config.bundle_contents:
            # Add canonical name
            bundle_map[normalize_text(opt_config.name)] = list(opt_config.bundle_contents)
            # Add all aliases
            for alias in opt_config.aliases:
                bundle_map[normalize_text(alias)] = list(opt_config.bundle_contents)

    # If no bundles defined, return original
    if not bundle_map:
        return list(raw_options)

    # Expand bundles
    expanded: list[str] = []
    seen_normalized: set[str] = set()

    for option in raw_options:
        normalized = normalize_text(option)

        # Add original option if not duplicate
        if normalized not in seen_normalized:
            expanded.append(option)
            seen_normalized.add(normalized)

        # Check if this option is a bundle
        if normalized in bundle_map:
            # Add bundle contents
            for content in bundle_map[normalized]:
                content_normalized = normalize_text(content)
                if content_normalized not in seen_normalized:
                    expanded.append(content)
                    seen_normalized.add(content_normalized)

    return expanded
