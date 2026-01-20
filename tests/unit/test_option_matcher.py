"""Unit tests for option matcher - TDD approach."""

import pytest

from car_scraper.models.pydantic_models import MatchResult, OptionConfig, OptionsConfig


@pytest.fixture
def sample_config() -> OptionsConfig:
    """Create a sample configuration for testing."""
    return OptionsConfig(
        required=[
            OptionConfig(
                name="Head-Up Display",
                aliases=["HUD", "Windschutzscheiben-HUD", "Head Up Display"],
            ),
            OptionConfig(
                name="Harman Kardon",
                aliases=["Harman/Kardon", "HK Sound"],
            ),
        ],
        nice_to_have=[
            OptionConfig(
                name="Seat Heating",
                aliases=["Sitzheizung", "Heated seats", "Stoelverwarming"],
            ),
            OptionConfig(
                name="Laser Light",
                aliases=["Laserlicht", "BMW Laserlight"],
            ),
        ],
        dealbreakers=["Unfallwagen", "Accident damage", "Salvage"],
    )


class TestOptionMatcher:
    """Tests for the option matching function."""

    def test_match_required_options(self, sample_config: OptionsConfig) -> None:
        """Should match required options by alias."""
        from car_scraper.matching.option_matcher import match_options

        listing_options = ["HUD", "Harman/Kardon", "Other option"]

        result = match_options(listing_options, sample_config)

        assert "Head-Up Display" in result.matched_required
        assert "Harman Kardon" in result.matched_required
        assert len(result.missing_required) == 0

    def test_match_nice_to_have_options(self, sample_config: OptionsConfig) -> None:
        """Should match nice-to-have options by alias."""
        from car_scraper.matching.option_matcher import match_options

        listing_options = ["Sitzheizung", "Laserlicht"]

        result = match_options(listing_options, sample_config)

        assert "Seat Heating" in result.matched_nice_to_have
        assert "Laser Light" in result.matched_nice_to_have

    def test_identify_missing_required(self, sample_config: OptionsConfig) -> None:
        """Should identify missing required options."""
        from car_scraper.matching.option_matcher import match_options

        listing_options = ["Sitzheizung"]  # No required options

        result = match_options(listing_options, sample_config)

        assert "Head-Up Display" in result.missing_required
        assert "Harman Kardon" in result.missing_required
        assert len(result.matched_required) == 0

    def test_detect_dealbreaker(self, sample_config: OptionsConfig) -> None:
        """Should detect dealbreaker options."""
        from car_scraper.matching.option_matcher import match_options

        listing_options = ["HUD", "Harman Kardon", "Unfallwagen"]

        result = match_options(listing_options, sample_config)

        assert result.has_dealbreaker is True
        assert result.dealbreaker_found == "Unfallwagen"

    def test_no_dealbreaker(self, sample_config: OptionsConfig) -> None:
        """Should not flag dealbreaker when not present."""
        from car_scraper.matching.option_matcher import match_options

        listing_options = ["HUD", "Harman Kardon"]

        result = match_options(listing_options, sample_config)

        assert result.has_dealbreaker is False
        assert result.dealbreaker_found is None

    def test_match_with_normalization(self, sample_config: OptionsConfig) -> None:
        """Should match options with different casing/diacritics."""
        from car_scraper.matching.option_matcher import match_options

        listing_options = [
            "head-up display",  # lowercase with dash
            "HARMAN KARDON",  # uppercase
            "sitzheizung",  # lowercase German
        ]

        result = match_options(listing_options, sample_config)

        assert "Head-Up Display" in result.matched_required
        assert "Harman Kardon" in result.matched_required
        assert "Seat Heating" in result.matched_nice_to_have

    def test_match_returns_match_result(self, sample_config: OptionsConfig) -> None:
        """Should return a MatchResult instance."""
        from car_scraper.matching.option_matcher import match_options

        result = match_options([], sample_config)

        assert isinstance(result, MatchResult)

    def test_match_empty_listing_options(self, sample_config: OptionsConfig) -> None:
        """Should handle empty listing options."""
        from car_scraper.matching.option_matcher import match_options

        result = match_options([], sample_config)

        assert len(result.matched_required) == 0
        assert len(result.matched_nice_to_have) == 0
        assert len(result.missing_required) == 2

    def test_match_empty_config(self) -> None:
        """Should handle empty config."""
        from car_scraper.matching.option_matcher import match_options

        empty_config = OptionsConfig(required=[], nice_to_have=[], dealbreakers=[])

        result = match_options(["Option 1", "Option 2"], empty_config)

        assert len(result.matched_required) == 0
        assert len(result.matched_nice_to_have) == 0
        assert len(result.missing_required) == 0
        assert result.has_dealbreaker is False

    def test_match_partial_alias_no_match(self, sample_config: OptionsConfig) -> None:
        """Partial alias matches should not count."""
        from car_scraper.matching.option_matcher import match_options

        listing_options = ["HUD Pro"]  # Contains HUD but isn't HUD

        result = match_options(listing_options, sample_config)

        # Depending on implementation - exact match vs contains
        # For safety, we want exact normalized match
        assert "Head-Up Display" not in result.matched_required

    def test_match_canonical_name_directly(self, sample_config: OptionsConfig) -> None:
        """Should match canonical name (not just aliases)."""
        from car_scraper.matching.option_matcher import match_options

        listing_options = ["Head-Up Display", "Seat Heating"]

        result = match_options(listing_options, sample_config)

        assert "Head-Up Display" in result.matched_required
        assert "Seat Heating" in result.matched_nice_to_have

    def test_dealbreaker_case_insensitive(self, sample_config: OptionsConfig) -> None:
        """Dealbreaker matching should be case insensitive."""
        from car_scraper.matching.option_matcher import match_options

        listing_options = ["accident DAMAGE"]  # Mixed case

        result = match_options(listing_options, sample_config)

        assert result.has_dealbreaker is True

    def test_no_duplicate_matches(self, sample_config: OptionsConfig) -> None:
        """Same option matched multiple times should appear once."""
        from car_scraper.matching.option_matcher import match_options

        # Multiple aliases for same option
        listing_options = ["HUD", "Head Up Display", "Windschutzscheiben-HUD"]

        result = match_options(listing_options, sample_config)

        assert result.matched_required.count("Head-Up Display") == 1
