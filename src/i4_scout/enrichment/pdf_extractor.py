"""PDF text extraction using pdfplumber."""

import re
from pathlib import Path

import pdfplumber


class PDFExtractor:
    """Extract text and BMW option codes from PDF documents."""

    # BMW option codes are typically 3 alphanumeric characters
    BMW_OPTION_CODE_PATTERN = re.compile(r"\b[0-9A-Z]{3}\b")

    def __init__(self, file_path: Path | str) -> None:
        """Initialize with PDF file path.

        Args:
            file_path: Path to the PDF file.
        """
        self._file_path = Path(file_path)

    def extract_text(self) -> str:
        """Extract all text from the PDF.

        Returns:
            Combined text from all pages.

        Raises:
            FileNotFoundError: If PDF file doesn't exist.
            ValueError: If file cannot be parsed as PDF.
        """
        if not self._file_path.exists():
            raise FileNotFoundError(f"PDF file not found: {self._file_path}")

        try:
            with pdfplumber.open(self._file_path) as pdf:
                pages_text = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        pages_text.append(text)

                    # Also extract table text (BMW options often in tables)
                    tables = page.extract_tables()
                    for table in tables:
                        for row in table:
                            if row:
                                # Filter None values and join cells
                                cells = [str(c).strip() for c in row if c]
                                if cells:
                                    pages_text.append(" ".join(cells))

                return "\n".join(pages_text)
        except Exception as e:
            raise ValueError(f"Failed to parse PDF: {e}") from e

    def extract_option_codes(self, text: str | None = None) -> list[str]:
        """Extract BMW option codes from text.

        BMW option codes are typically 3-character alphanumeric codes like:
        - 337 (M Sport Package)
        - 5A2 (Laser Light)
        - 7A2 (Harman Kardon)

        Args:
            text: Text to search. If None, extracts text from PDF first.

        Returns:
            List of unique option codes found.
        """
        if text is None:
            text = self.extract_text()

        # Find all potential option codes
        matches = self.BMW_OPTION_CODE_PATTERN.findall(text)

        # Return unique codes, preserving order of first appearance
        seen: set[str] = set()
        unique_codes: list[str] = []
        for code in matches:
            if code not in seen:
                seen.add(code)
                unique_codes.append(code)

        return unique_codes

    def extract_all(self) -> dict[str, str | list[str]]:
        """Extract text and option codes from PDF.

        Returns:
            Dict with 'text' (full text) and 'option_codes' (list of codes).
        """
        text = self.extract_text()
        codes = self.extract_option_codes(text)
        return {"text": text, "option_codes": codes}


def extract_text_from_pdf(file_path: Path | str) -> str:
    """Convenience function to extract text from a PDF file.

    Args:
        file_path: Path to the PDF file.

    Returns:
        Extracted text content.
    """
    extractor = PDFExtractor(file_path)
    return extractor.extract_text()
