"""Test configuration and fixtures."""
import pytest


@pytest.fixture
def app():
    """Fixture for FastAPI test client."""
    from app.main import app
    return app


@pytest.fixture
def config():
    """Fixture for app configuration."""
    from app.core.config import settings
    return settings
