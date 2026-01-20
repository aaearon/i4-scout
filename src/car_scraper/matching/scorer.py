"""Score calculation for matched options."""

from car_scraper.models.pydantic_models import MatchResult, OptionsConfig


# Scoring weights
REQUIRED_WEIGHT = 100
NICE_TO_HAVE_WEIGHT = 10


def calculate_score(match_result: MatchResult, config: OptionsConfig) -> MatchResult:
    """Calculate match score based on matched options.

    Formula:
        score = (required_matched * 100) + (nice_to_have_matched * 10)
        max_score = (len(required) * 100) + (len(nice_to_have) * 10)
        normalized_score = (score / max_score) * 100

    Qualification:
        is_qualified = all required matched AND no dealbreaker

    Args:
        match_result: MatchResult from option matcher.
        config: Options configuration for max score calculation.

    Returns:
        New MatchResult with score and is_qualified fields set.
    """
    # Calculate raw score
    required_score = len(match_result.matched_required) * REQUIRED_WEIGHT
    nice_to_have_score = len(match_result.matched_nice_to_have) * NICE_TO_HAVE_WEIGHT
    raw_score = required_score + nice_to_have_score

    # Calculate max possible score
    max_required = len(config.required) * REQUIRED_WEIGHT
    max_nice_to_have = len(config.nice_to_have) * NICE_TO_HAVE_WEIGHT
    max_score = max_required + max_nice_to_have

    # Normalize score to 0-100%
    if max_score > 0:
        normalized_score = (raw_score / max_score) * 100
    else:
        # No requirements = perfect score
        normalized_score = 100.0

    # Determine qualification
    all_required_matched = len(match_result.missing_required) == 0
    is_qualified = all_required_matched and not match_result.has_dealbreaker

    # Return new MatchResult with score
    return MatchResult(
        matched_required=match_result.matched_required,
        matched_nice_to_have=match_result.matched_nice_to_have,
        missing_required=match_result.missing_required,
        has_dealbreaker=match_result.has_dealbreaker,
        dealbreaker_found=match_result.dealbreaker_found,
        score=normalized_score,
        is_qualified=is_qualified,
    )
