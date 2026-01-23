"""Score calculation for matched options."""

from i4_scout.models.pydantic_models import MatchResult, OptionsConfig

# Scoring weights (3:1 ratio - nice-to-have contributes ~20% to total score)
REQUIRED_WEIGHT = 75
NICE_TO_HAVE_WEIGHT = 25


def calculate_score(match_result: MatchResult, config: OptionsConfig) -> MatchResult:
    """Calculate match score based on matched options.

    Formula:
        score = (required_matched * 75) + (nice_to_have_matched * 25)
        max_score = (len(required) * 75) + (len(nice_to_have) * 25)
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
