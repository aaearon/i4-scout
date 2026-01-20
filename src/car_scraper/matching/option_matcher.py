"""Option matching against configuration aliases."""

from car_scraper.matching.bundle_expander import expand_bundles
from car_scraper.matching.normalizer import normalize_text
from car_scraper.models.pydantic_models import MatchResult, OptionsConfig


def match_options(raw_options: list[str], config: OptionsConfig) -> MatchResult:
    """Match listing options against config aliases.

    Algorithm:
    1. Expand bundles in raw options
    2. Normalize all listing options
    3. Build flattened alias map from config (normalized)
    4. Match each normalized listing option against alias map
    5. Check for dealbreakers
    6. Return MatchResult with categorized matches

    Args:
        raw_options: List of raw option strings from listing.
        config: Options configuration with required/nice-to-have/dealbreakers.

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

    # Step 4: Match options
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

    # Step 5: Calculate missing required
    all_required_names = {opt.name for opt in config.required}
    missing_required = list(all_required_names - matched_required)

    return MatchResult(
        matched_required=list(matched_required),
        matched_nice_to_have=list(matched_nice_to_have),
        missing_required=missing_required,
        has_dealbreaker=dealbreaker_found is not None,
        dealbreaker_found=dealbreaker_found,
    )
