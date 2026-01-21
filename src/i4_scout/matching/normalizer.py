"""Text normalization for option matching."""

import re
import unicodedata

# Pre-compiled regex patterns for performance
_PUNCTUATION_RE = re.compile(r"[/\-°]")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Normalize text for consistent option matching.

    Algorithm:
    1. Convert to lowercase
    2. Replace German ß with ss
    3. Normalize Unicode (NFKD form)
    4. Strip diacritics (combining characters)
    5. Remove punctuation (keep alphanumeric + spaces)
    6. Collapse whitespace to single spaces
    7. Strip leading/trailing whitespace

    Args:
        text: Input text to normalize.

    Returns:
        Normalized text suitable for matching.

    Examples:
        >>> normalize_text("Sitzheizung")
        'sitzheizung'
        >>> normalize_text("Wärmepumpe")
        'warmepumpe'
        >>> normalize_text("Größe")
        'grosse'
        >>> normalize_text("Head-Up Display")
        'head up display'
        >>> normalize_text("360° Kamera")
        '360 kamera'
    """
    if not text:
        return ""

    # Step 1: Lowercase
    result = text.lower()

    # Step 2: German ß handling (must be before Unicode normalization)
    result = result.replace("ß", "ss")

    # Step 3: Unicode normalization (NFKD decomposes characters)
    # e.g., ä becomes a + combining diaeresis
    result = unicodedata.normalize("NFKD", result)

    # Step 4: Strip diacritics (combining characters)
    result = "".join(c for c in result if not unicodedata.combining(c))

    # Step 5: Remove punctuation - keep alphanumeric and spaces
    # Replace common punctuation with spaces first
    result = _PUNCTUATION_RE.sub(" ", result)
    # Remove remaining non-alphanumeric (except spaces)
    result = _NON_ALNUM_RE.sub("", result)

    # Step 6: Collapse whitespace to single spaces
    result = _WHITESPACE_RE.sub(" ", result)

    # Step 7: Strip leading/trailing whitespace
    result = result.strip()

    return result
