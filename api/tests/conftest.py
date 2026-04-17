"""Pytest fixtures for Windy Clone API tests."""

import pytest
from httpx import AsyncClient, ASGITransport

from app.config import get_settings
from app.main import app
from app.db.engine import init_db


@pytest.fixture(autouse=True)
def _force_dev_mode():
    """Tests assume the dev-user fallback — pin dev_mode on regardless of env.

    The production default is dev_mode=False; without this fixture every test
    that expects the mock user would depend on the developer's local .env.
    """
    settings = get_settings()
    prior = settings.dev_mode
    settings.dev_mode = True
    yield
    settings.dev_mode = prior


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    """Async test client for the FastAPI app with fresh DB."""
    # Initialize in-memory DB for tests
    await init_db()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
