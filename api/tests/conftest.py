"""Pytest fixtures for Windy Clone API tests."""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.db.engine import init_db


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
