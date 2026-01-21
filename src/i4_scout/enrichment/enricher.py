"""Listing enrichment with options from PDF documents."""

from i4_scout.matching.option_matcher import match_options
from i4_scout.matching.scorer import calculate_score
from i4_scout.models.pydantic_models import EnrichmentResult, MatchResult, OptionsConfig


class ListingEnricher:
    """Enriches listings with options found in PDF documents."""

    def __init__(self, options_config: OptionsConfig) -> None:
        """Initialize with options configuration.

        Args:
            options_config: Configuration with required/nice_to_have options.
        """
        self._config = options_config

    def match_from_text(self, pdf_text: str) -> MatchResult:
        """Match options from PDF text.

        Uses the same matching logic as the scraper: searches for option
        names, aliases, and BMW option codes in the text.

        Args:
            pdf_text: Extracted text from PDF document.

        Returns:
            MatchResult with matched options.
        """
        # Use existing option matcher with PDF text as description
        # Pass empty raw_options list since we're searching text only
        match_result = match_options(
            raw_options=[],
            config=self._config,
            description=pdf_text,
        )
        return match_result

    def find_new_options(
        self,
        pdf_text: str,
        existing_options: list[str],
    ) -> list[str]:
        """Find options in PDF that aren't already matched.

        Args:
            pdf_text: Extracted text from PDF document.
            existing_options: Options already matched on the listing.

        Returns:
            List of new option names found in PDF.
        """
        match_result = self.match_from_text(pdf_text)
        all_matched = match_result.matched_required + match_result.matched_nice_to_have

        existing_set = set(existing_options)
        new_options = [opt for opt in all_matched if opt not in existing_set]

        return new_options

    def calculate_enriched_score(
        self,
        existing_options: list[str],
        new_options: list[str],
    ) -> MatchResult:
        """Calculate score with existing + new options combined.

        Args:
            existing_options: Options already on the listing.
            new_options: New options found from PDF.

        Returns:
            MatchResult with recalculated score.
        """
        # Build combined set of all options
        all_options = set(existing_options) | set(new_options)

        # Categorize into required vs nice-to-have
        required_names = {opt.name for opt in self._config.required}
        nice_to_have_names = {opt.name for opt in self._config.nice_to_have}

        matched_required = [opt for opt in all_options if opt in required_names]
        matched_nice_to_have = [opt for opt in all_options if opt in nice_to_have_names]
        missing_required = list(required_names - all_options)

        # Create combined match result
        combined = MatchResult(
            matched_required=matched_required,
            matched_nice_to_have=matched_nice_to_have,
            missing_required=missing_required,
            has_dealbreaker=False,  # PDF enrichment doesn't check dealbreakers
            dealbreaker_found=None,
        )

        # Calculate score
        return calculate_score(combined, self._config)

    def enrich(
        self,
        listing_id: int,
        document_id: int,
        pdf_text: str,
        existing_options: list[str],
        current_score: float,
        is_currently_qualified: bool,
    ) -> EnrichmentResult:
        """Perform full enrichment of a listing from PDF text.

        Args:
            listing_id: ID of the listing being enriched.
            document_id: ID of the uploaded document.
            pdf_text: Extracted text from PDF.
            existing_options: Options already matched on the listing.
            current_score: Current match score before enrichment.
            is_currently_qualified: Current qualification status.

        Returns:
            EnrichmentResult with before/after scores and new options.
        """
        # Find all options in PDF
        match_result = self.match_from_text(pdf_text)
        options_found = match_result.matched_required + match_result.matched_nice_to_have

        # Identify which are new
        existing_set = set(existing_options)
        new_options = [opt for opt in options_found if opt not in existing_set]

        # Calculate new score with combined options
        if new_options:
            scored_result = self.calculate_enriched_score(existing_options, new_options)
            score_after = scored_result.score
            is_qualified_after = scored_result.is_qualified
        else:
            # No new options, scores stay the same
            score_after = current_score
            is_qualified_after = is_currently_qualified

        return EnrichmentResult(
            listing_id=listing_id,
            document_id=document_id,
            options_found=options_found,
            new_options_added=new_options,
            score_before=current_score,
            score_after=score_after,
            is_qualified_before=is_currently_qualified,
            is_qualified_after=is_qualified_after,
        )
