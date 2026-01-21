"""Unit tests for text normalizer - TDD approach."""



class TestTextNormalizer:
    """Tests for the text normalization function."""

    def test_normalize_lowercase(self) -> None:
        """Should convert text to lowercase."""
        from i4_scout.matching.normalizer import normalize_text

        assert normalize_text("Sitzheizung") == "sitzheizung"
        assert normalize_text("HEATED SEATS") == "heated seats"

    def test_normalize_german_eszett(self) -> None:
        """Should convert German ß to ss."""
        from i4_scout.matching.normalizer import normalize_text

        assert normalize_text("Größe") == "grosse"
        assert normalize_text("Fußraum") == "fussraum"

    def test_normalize_umlaut_a(self) -> None:
        """Should strip umlaut from ä."""
        from i4_scout.matching.normalizer import normalize_text

        assert normalize_text("Wärmepumpe") == "warmepumpe"
        assert normalize_text("Rückfahrkamera") == "ruckfahrkamera"

    def test_normalize_umlaut_o(self) -> None:
        """Should strip umlaut from ö."""
        from i4_scout.matching.normalizer import normalize_text

        assert normalize_text("Größe") == "grosse"
        assert normalize_text("Höhenverstellung") == "hohenverstellung"

    def test_normalize_umlaut_u(self) -> None:
        """Should strip umlaut from ü."""
        from i4_scout.matching.normalizer import normalize_text

        assert normalize_text("Rückfahrkamera") == "ruckfahrkamera"
        assert normalize_text("Türen") == "turen"

    def test_normalize_punctuation(self) -> None:
        """Should remove punctuation."""
        from i4_scout.matching.normalizer import normalize_text

        assert normalize_text("Head-Up Display") == "head up display"
        assert normalize_text("360° Kamera") == "360 kamera"
        assert normalize_text("Harman/Kardon") == "harman kardon"

    def test_normalize_whitespace(self) -> None:
        """Should collapse multiple spaces to single space."""
        from i4_scout.matching.normalizer import normalize_text

        assert normalize_text("  multiple   spaces  ") == "multiple spaces"
        assert normalize_text("tabs\tand\nnewlines") == "tabs and newlines"

    def test_normalize_preserves_numbers(self) -> None:
        """Should preserve numeric characters."""
        from i4_scout.matching.normalizer import normalize_text

        assert normalize_text("360° Camera") == "360 camera"
        assert normalize_text("M50 xDrive") == "m50 xdrive"

    def test_normalize_empty_string(self) -> None:
        """Should handle empty strings."""
        from i4_scout.matching.normalizer import normalize_text

        assert normalize_text("") == ""
        assert normalize_text("   ") == ""

    def test_normalize_special_characters(self) -> None:
        """Should handle various special characters."""
        from i4_scout.matching.normalizer import normalize_text

        # Common characters in car options
        assert normalize_text("AC/Klima") == "ac klima"
        assert normalize_text("LED (inkl. Blinker)") == "led inkl blinker"
        assert normalize_text("Hi-Fi System") == "hi fi system"

    def test_normalize_dutch_text(self) -> None:
        """Should handle Dutch special characters."""
        from i4_scout.matching.normalizer import normalize_text

        # Dutch has ë and ï
        assert normalize_text("Verwarmd stuur") == "verwarmd stuur"
        assert normalize_text("Stoelverwarming") == "stoelverwarming"

    def test_normalize_consistent_output(self) -> None:
        """Same input should always produce same output."""
        from i4_scout.matching.normalizer import normalize_text

        input_text = "Größe-Test / Example"
        result1 = normalize_text(input_text)
        result2 = normalize_text(input_text)

        assert result1 == result2 == "grosse test example"
