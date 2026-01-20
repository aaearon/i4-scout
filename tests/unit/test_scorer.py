"""Unit tests for scorer - TDD approach."""

import pytest

from i4_scout.models.pydantic_models import MatchResult, OptionConfig, OptionsConfig


@pytest.fixture
def sample_config() -> OptionsConfig:
    """Create a sample configuration for scoring tests."""
    return OptionsConfig(
        required=[
            OptionConfig(name="Head-Up Display", aliases=["HUD"]),
            OptionConfig(name="Harman Kardon", aliases=["HK"]),
        ],
        nice_to_have=[
            OptionConfig(name="Seat Heating", aliases=["Sitzheizung"]),
            OptionConfig(name="Laser Light", aliases=["Laserlicht"]),
            OptionConfig(name="Panoramic Roof", aliases=["Panoramadach"]),
        ],
        dealbreakers=["Unfallwagen"],
    )


class TestScorer:
    """Tests for the scoring function."""

    def test_perfect_score_all_options(self, sample_config: OptionsConfig) -> None:
        """All options matched should give 100% score."""
        from i4_scout.matching.scorer import calculate_score

        match_result = MatchResult(
            matched_required=["Head-Up Display", "Harman Kardon"],
            matched_nice_to_have=["Seat Heating", "Laser Light", "Panoramic Roof"],
            missing_required=[],
            has_dealbreaker=False,
        )

        result = calculate_score(match_result, sample_config)

        assert result.score == 100.0
        assert result.is_qualified is True

    def test_zero_score_no_matches(self, sample_config: OptionsConfig) -> None:
        """No matches should give 0% score."""
        from i4_scout.matching.scorer import calculate_score

        match_result = MatchResult(
            matched_required=[],
            matched_nice_to_have=[],
            missing_required=["Head-Up Display", "Harman Kardon"],
            has_dealbreaker=False,
        )

        result = calculate_score(match_result, sample_config)

        assert result.score == 0.0
        assert result.is_qualified is False

    def test_required_weighted_more_than_nice_to_have(
        self, sample_config: OptionsConfig
    ) -> None:
        """Required options should have more weight than nice-to-have."""
        from i4_scout.matching.scorer import calculate_score

        # Only required
        required_only = MatchResult(
            matched_required=["Head-Up Display", "Harman Kardon"],
            matched_nice_to_have=[],
            missing_required=[],
            has_dealbreaker=False,
        )

        # Only nice-to-have
        nice_only = MatchResult(
            matched_required=[],
            matched_nice_to_have=["Seat Heating", "Laser Light", "Panoramic Roof"],
            missing_required=["Head-Up Display", "Harman Kardon"],
            has_dealbreaker=False,
        )

        required_score = calculate_score(required_only, sample_config)
        nice_score = calculate_score(nice_only, sample_config)

        assert required_score.score > nice_score.score

    def test_qualified_requires_all_required(
        self, sample_config: OptionsConfig
    ) -> None:
        """is_qualified should be True only when ALL required are matched."""
        from i4_scout.matching.scorer import calculate_score

        # Missing one required
        partial = MatchResult(
            matched_required=["Head-Up Display"],
            matched_nice_to_have=["Seat Heating", "Laser Light", "Panoramic Roof"],
            missing_required=["Harman Kardon"],
            has_dealbreaker=False,
        )

        result = calculate_score(partial, sample_config)

        assert result.is_qualified is False

    def test_dealbreaker_disqualifies(self, sample_config: OptionsConfig) -> None:
        """Dealbreaker should disqualify even with all required matched."""
        from i4_scout.matching.scorer import calculate_score

        with_dealbreaker = MatchResult(
            matched_required=["Head-Up Display", "Harman Kardon"],
            matched_nice_to_have=["Seat Heating"],
            missing_required=[],
            has_dealbreaker=True,
            dealbreaker_found="Unfallwagen",
        )

        result = calculate_score(with_dealbreaker, sample_config)

        assert result.is_qualified is False
        # Score might still be calculated but qualification is False

    def test_score_formula_required_100_nice_10(
        self, sample_config: OptionsConfig
    ) -> None:
        """Score formula: required=100, nice_to_have=10."""
        from i4_scout.matching.scorer import calculate_score

        # 1 required (100) + 2 nice (20) = 120
        # max = 2*100 + 3*10 = 230
        # normalized = 120/230 * 100 ≈ 52.17
        match_result = MatchResult(
            matched_required=["Head-Up Display"],
            matched_nice_to_have=["Seat Heating", "Laser Light"],
            missing_required=["Harman Kardon"],
            has_dealbreaker=False,
        )

        result = calculate_score(match_result, sample_config)

        expected_score = (1 * 100 + 2 * 10) / (2 * 100 + 3 * 10) * 100
        assert abs(result.score - expected_score) < 0.01

    def test_score_bounds_0_to_100(self, sample_config: OptionsConfig) -> None:
        """Score should always be between 0 and 100."""
        from i4_scout.matching.scorer import calculate_score

        # Test various scenarios
        scenarios = [
            MatchResult(matched_required=[], matched_nice_to_have=[], missing_required=["a", "b"]),
            MatchResult(matched_required=["Head-Up Display", "Harman Kardon"], matched_nice_to_have=["Seat Heating", "Laser Light", "Panoramic Roof"], missing_required=[]),
        ]

        for match_result in scenarios:
            result = calculate_score(match_result, sample_config)
            assert 0.0 <= result.score <= 100.0

    def test_empty_config_gives_100(self) -> None:
        """Empty config (no requirements) should give 100%."""
        from i4_scout.matching.scorer import calculate_score

        empty_config = OptionsConfig(required=[], nice_to_have=[], dealbreakers=[])
        match_result = MatchResult()

        result = calculate_score(match_result, empty_config)

        assert result.score == 100.0
        assert result.is_qualified is True

    def test_score_copied_to_match_result(self, sample_config: OptionsConfig) -> None:
        """calculate_score should return a MatchResult with score set."""
        from i4_scout.matching.scorer import calculate_score

        match_result = MatchResult(
            matched_required=["Head-Up Display"],
            missing_required=["Harman Kardon"],
        )

        result = calculate_score(match_result, sample_config)

        assert isinstance(result, MatchResult)
        assert result.score > 0
        assert result.matched_required == match_result.matched_required

    def test_only_required_in_config(self) -> None:
        """Config with only required options should work."""
        from i4_scout.matching.scorer import calculate_score

        config = OptionsConfig(
            required=[OptionConfig(name="HUD", aliases=[])],
            nice_to_have=[],
            dealbreakers=[],
        )
        match_result = MatchResult(matched_required=["HUD"], missing_required=[])

        result = calculate_score(match_result, config)

        assert result.score == 100.0
        assert result.is_qualified is True

    def test_only_nice_to_have_in_config(self) -> None:
        """Config with only nice-to-have options should work."""
        from i4_scout.matching.scorer import calculate_score

        config = OptionsConfig(
            required=[],
            nice_to_have=[
                OptionConfig(name="Seat Heating", aliases=[]),
                OptionConfig(name="Laser", aliases=[]),
            ],
            dealbreakers=[],
        )
        match_result = MatchResult(
            matched_nice_to_have=["Seat Heating"],
        )

        result = calculate_score(match_result, config)

        # 1 nice matched out of 2 = 10/20 = 50%
        assert result.score == 50.0
        # No required, so is_qualified should be True
        assert result.is_qualified is True
