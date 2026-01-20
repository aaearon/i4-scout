"""Option matching against configuration aliases."""

import re

from i4_scout.matching.bundle_expander import expand_bundles
from i4_scout.matching.normalizer import normalize_text
from i4_scout.models.pydantic_models import MatchResult, OptionsConfig


def match_options(
    raw_options: list[str],
    config: OptionsConfig,
    description: str | None = None,
) -> MatchResult:
    """Match listing options against config aliases.

    Algorithm:
    1. Expand bundles in raw options
    2. Normalize all listing options
    3. Build flattened alias map from config (normalized)
    4. Match each normalized listing option against alias map
    5. Search description text for option codes and aliases
    6. Check for dealbreakers
    7. Return MatchResult with categorized matches

    Args:
        raw_options: List of raw option strings from listing.
        config: Options configuration with required/nice-to-have/dealbreakers.
        description: Optional vehicle description text to search for codes.

    Returns:
        MatchResult with matched/missing options and dealbreaker status.
    """
    # Step 1: Expand bundles
    expanded_options = expand_bundles(raw_options, config)

    # Step 2: Normalize all listing options
    normalized_listing_options = {normalize_text(opt) for opt in expanded_options}

    # Step 3: Build alias maps for required and nice-to-have
    # Maps normalized alias -> canonical name
    required_alias_map: dict[str, str] = {}
    nice_to_have_alias_map: dict[str, str] = {}

    for option in config.required:
        # Add canonical name
        required_alias_map[normalize_text(option.name)] = option.name
        # Add all aliases
        for alias in option.aliases:
            required_alias_map[normalize_text(alias)] = option.name

    for option in config.nice_to_have:
        # Add canonical name
        nice_to_have_alias_map[normalize_text(option.name)] = option.name
        # Add all aliases
        for alias in option.aliases:
            nice_to_have_alias_map[normalize_text(alias)] = option.name

    # Normalize dealbreakers
    normalized_dealbreakers = {normalize_text(d): d for d in config.dealbreakers}

    # Step 4: Match options from options list
    matched_required: set[str] = set()
    matched_nice_to_have: set[str] = set()
    dealbreaker_found: str | None = None

    for normalized_opt in normalized_listing_options:
        # Check for required match
        if normalized_opt in required_alias_map:
            matched_required.add(required_alias_map[normalized_opt])

        # Check for nice-to-have match
        if normalized_opt in nice_to_have_alias_map:
            matched_nice_to_have.add(nice_to_have_alias_map[normalized_opt])

        # Check for dealbreaker
        if normalized_opt in normalized_dealbreakers and dealbreaker_found is None:
            dealbreaker_found = normalized_dealbreakers[normalized_opt]

    # Step 5: Search description text for option codes and aliases
    if description:
        description_lower = description.lower()

        # Search for required options in description
        for option in config.required:
            if option.name in matched_required:
                continue  # Already matched
            # Check canonical name and all aliases (including codes)
            all_names = [option.name] + list(option.aliases)
            for name in all_names:
                # Use word boundary matching for short codes (like "337", "7A2")
                if len(name) <= 4 and name.isalnum():
                    # Short codes need word boundaries to avoid false positives
                    pattern = rf"\b{re.escape(name)}\b"
                    if re.search(pattern, description, re.IGNORECASE):
                        matched_required.add(option.name)
                        break
                elif name.lower() in description_lower:
                    matched_required.add(option.name)
                    break

        # Search for nice-to-have options in description
        for option in config.nice_to_have:
            if option.name in matched_nice_to_have:
                continue  # Already matched
            all_names = [option.name] + list(option.aliases)
            for name in all_names:
                if len(name) <= 4 and name.isalnum():
                    pattern = rf"\b{re.escape(name)}\b"
                    if re.search(pattern, description, re.IGNORECASE):
                        matched_nice_to_have.add(option.name)
                        break
                elif name.lower() in description_lower:
                    matched_nice_to_have.add(option.name)
                    break

        # Check dealbreakers in description
        if dealbreaker_found is None:
            for dealbreaker in config.dealbreakers:
                if dealbreaker.lower() in description_lower:
                    dealbreaker_found = dealbreaker
                    break

    # Step 6: Calculate missing required
    all_required_names = {opt.name for opt in config.required}
    missing_required = list(all_required_names - matched_required)

    return MatchResult(
        matched_required=list(matched_required),
        matched_nice_to_have=list(matched_nice_to_have),
        missing_required=missing_required,
        has_dealbreaker=dealbreaker_found is not None,
        dealbreaker_found=dealbreaker_found,
    )
