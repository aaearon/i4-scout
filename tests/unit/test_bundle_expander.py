"""Unit tests for bundle expander - TDD approach."""

import pytest

from car_scraper.models.pydantic_models import OptionConfig, OptionsConfig


@pytest.fixture
def config_with_bundles() -> OptionsConfig:
    """Create a config with bundle definitions."""
    return OptionsConfig(
        required=[
            OptionConfig(
                name="Head-Up Display",
                aliases=["HUD", "Windschutzscheiben-HUD"],
            )
        ],
        nice_to_have=[
            OptionConfig(
                name="M Sport Package",
                aliases=["M Sportpaket", "M Sport"],
                is_bundle=True,
                bundle_contents=[
                    "M Sport suspension",
                    "M Sport steering wheel",
                    "M Sport brakes",
                ],
            ),
            OptionConfig(
                name="Technology Package",
                aliases=["Technologie Paket"],
                is_bundle=True,
                bundle_contents=[
                    "Head-Up Display",
                    "Navigation Professional",
                ],
            ),
            OptionConfig(
                name="Laser Light",
                aliases=["Laserlicht"],
            ),
        ],
        dealbreakers=[],
    )


class TestBundleExpander:
    """Tests for the bundle expansion function."""

    def test_expand_no_bundles_returns_original(
        self, config_with_bundles: OptionsConfig
    ) -> None:
        """Options without bundles should be returned unchanged."""
        from car_scraper.matching.bundle_expander import expand_bundles

        raw_options = ["Sitzheizung", "Klimaanlage", "LED Scheinwerfer"]

        result = expand_bundles(raw_options, config_with_bundles)

        assert set(result) == set(raw_options)

    def test_expand_bundle_adds_contents(
        self, config_with_bundles: OptionsConfig
    ) -> None:
        """When bundle is detected, its contents should be added."""
        from car_scraper.matching.bundle_expander import expand_bundles

        raw_options = ["M Sportpaket", "Sitzheizung"]

        result = expand_bundles(raw_options, config_with_bundles)

        assert "M Sport suspension" in result
        assert "M Sport steering wheel" in result
        assert "M Sport brakes" in result
        # Original options preserved
        assert "Sitzheizung" in result

    def test_expand_bundle_preserves_original_bundle_name(
        self, config_with_bundles: OptionsConfig
    ) -> None:
        """Original bundle name should remain in the expanded list."""
        from car_scraper.matching.bundle_expander import expand_bundles

        raw_options = ["M Sport"]

        result = expand_bundles(raw_options, config_with_bundles)

        # Bundle name preserved
        assert "M Sport" in result
        # Contents added
        assert "M Sport suspension" in result

    def test_expand_multiple_bundles(
        self, config_with_bundles: OptionsConfig
    ) -> None:
        """Multiple bundles should all be expanded."""
        from car_scraper.matching.bundle_expander import expand_bundles

        raw_options = ["M Sportpaket", "Technologie Paket"]

        result = expand_bundles(raw_options, config_with_bundles)

        # M Sport contents
        assert "M Sport suspension" in result
        # Technology Package contents
        assert "Head-Up Display" in result
        assert "Navigation Professional" in result

    def test_expand_no_duplicates(
        self, config_with_bundles: OptionsConfig
    ) -> None:
        """Expanded options should not have duplicates."""
        from car_scraper.matching.bundle_expander import expand_bundles

        # Option already present + bundle containing same option
        raw_options = ["Head-Up Display", "Technologie Paket"]

        result = expand_bundles(raw_options, config_with_bundles)

        # Count occurrences - should be exactly 1
        assert result.count("Head-Up Display") == 1

    def test_expand_case_insensitive_bundle_match(
        self, config_with_bundles: OptionsConfig
    ) -> None:
        """Bundle matching should be case insensitive."""
        from car_scraper.matching.bundle_expander import expand_bundles

        raw_options = ["m sportpaket"]  # lowercase

        result = expand_bundles(raw_options, config_with_bundles)

        # Should still expand
        assert "M Sport suspension" in result

    def test_expand_empty_options(
        self, config_with_bundles: OptionsConfig
    ) -> None:
        """Empty options list should return empty list."""
        from car_scraper.matching.bundle_expander import expand_bundles

        result = expand_bundles([], config_with_bundles)

        assert result == []

    def test_expand_empty_config(self) -> None:
        """Config with no bundles should return original options."""
        from car_scraper.matching.bundle_expander import expand_bundles

        empty_config = OptionsConfig(required=[], nice_to_have=[], dealbreakers=[])
        raw_options = ["Option 1", "Option 2"]

        result = expand_bundles(raw_options, empty_config)

        assert set(result) == set(raw_options)

    def test_expand_partial_bundle_name_no_match(
        self, config_with_bundles: OptionsConfig
    ) -> None:
        """Partial bundle name should not trigger expansion."""
        from car_scraper.matching.bundle_expander import expand_bundles

        raw_options = ["M Sport wheels"]  # Not a bundle alias

        result = expand_bundles(raw_options, config_with_bundles)

        # No expansion - just original
        assert result == ["M Sport wheels"]
        assert "M Sport suspension" not in result
