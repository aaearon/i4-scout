"""Configuration API endpoints."""

from fastapi import APIRouter

from i4_scout.api.dependencies import OptionsConfigDep, SearchFiltersDep
from i4_scout.api.schemas import (
    OptionConfigResponse,
    OptionsConfigResponse,
    SearchFiltersResponse,
)
from i4_scout.models.pydantic_models import OptionConfig

router = APIRouter()


@router.get("/options", response_model=OptionsConfigResponse)
async def get_options_config(
    config: OptionsConfigDep,
) -> OptionsConfigResponse:
    """Get the options matching configuration.

    Returns the configured required options, nice-to-have options,
    and dealbreakers used for scoring listings.
    """

    def to_option_response(opt: OptionConfig) -> OptionConfigResponse:
        return OptionConfigResponse(
            name=opt.name,
            aliases=opt.aliases,
            category=opt.category,
            is_bundle=opt.is_bundle,
            bundle_contents=opt.bundle_contents,
        )

    return OptionsConfigResponse(
        required=[to_option_response(opt) for opt in config.required],
        nice_to_have=[to_option_response(opt) for opt in config.nice_to_have],
        dealbreakers=config.dealbreakers,
    )


@router.get("/filters", response_model=SearchFiltersResponse)
async def get_search_filters_endpoint(
    filters: SearchFiltersDep,
) -> SearchFiltersResponse:
    """Get the search filters configuration.

    Returns the configured search filters used when scraping
    (price max, mileage max, year range, countries).
    """
    return SearchFiltersResponse(
        price_max_eur=filters.price_max_eur,
        mileage_max_km=filters.mileage_max_km,
        year_min=filters.year_min,
        year_max=filters.year_max,
        countries=filters.countries or [],
    )
