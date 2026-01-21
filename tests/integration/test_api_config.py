"""Integration tests for config API endpoints."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from i4_scout.api.dependencies import get_db, get_options_config, get_search_filters
from i4_scout.api.main import create_app
from i4_scout.models.db_models import Base
from i4_scout.models.pydantic_models import OptionConfig, OptionsConfig, SearchFilters


@pytest.fixture
def test_engine(tmp_path: Path):
    """Create a test database engine."""
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session_factory(test_engine):
    """Create a session factory for the test database."""
    return sessionmaker(bind=test_engine)


@pytest.fixture
def mock_options_config() -> OptionsConfig:
    """Create a mock options configuration."""
    return OptionsConfig(
        required=[
            OptionConfig(
                name="Driving Assistant Professional",
                aliases=["Driving Assistant Pro", "DAP"],
                category="safety",
                is_bundle=True,
                bundle_contents=["Lane Keep Assist", "ACC"],
            ),
            OptionConfig(
                name="Harman Kardon",
                aliases=["HK Sound", "H/K"],
                category="audio",
            ),
        ],
        nice_to_have=[
            OptionConfig(
                name="Head-Up Display",
                aliases=["HUD"],
                category="comfort",
            ),
        ],
        dealbreakers=["Accident damage", "Salvage title"],
    )


@pytest.fixture
def mock_search_filters() -> SearchFilters:
    """Create mock search filters."""
    return SearchFilters(
        price_max_eur=55000,
        mileage_max_km=50000,
        year_min=2023,
        year_max=2025,
        countries=["D", "NL"],
    )


@pytest.fixture
def client(session_factory, mock_options_config, mock_search_filters):
    """Create a test client with overridden dependencies."""
    app = create_app()

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def override_get_options_config():
        return mock_options_config

    def override_get_search_filters():
        return mock_search_filters

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_options_config] = override_get_options_config
    app.dependency_overrides[get_search_filters] = override_get_search_filters
    return TestClient(app)


class TestGetOptionsConfig:
    """Tests for GET /api/config/options endpoint."""

    def test_get_options(self, client: TestClient) -> None:
        """Returns options configuration."""
        response = client.get("/api/config/options")
        assert response.status_code == 200
        data = response.json()

        assert len(data["required"]) == 2
        assert len(data["nice_to_have"]) == 1
        assert len(data["dealbreakers"]) == 2
        assert "Accident damage" in data["dealbreakers"]

    def test_options_contain_details(self, client: TestClient) -> None:
        """Options include name, aliases, category, and bundle contents."""
        response = client.get("/api/config/options")
        data = response.json()

        required = data["required"][0]
        assert required["name"] == "Driving Assistant Professional"
        assert "Driving Assistant Pro" in required["aliases"]
        assert required["category"] == "safety"
        assert required["is_bundle"] is True
        assert "Lane Keep Assist" in required["bundle_contents"]


class TestGetSearchFilters:
    """Tests for GET /api/config/filters endpoint."""

    def test_get_filters(self, client: TestClient) -> None:
        """Returns search filters configuration."""
        response = client.get("/api/config/filters")
        assert response.status_code == 200
        data = response.json()

        assert data["price_max_eur"] == 55000
        assert data["mileage_max_km"] == 50000
        assert data["year_min"] == 2023
        assert data["year_max"] == 2025
        assert data["countries"] == ["D", "NL"]
