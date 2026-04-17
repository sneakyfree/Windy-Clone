"""Pytest fixtures for Windy Clone API tests."""

import pytest
from httpx import AsyncClient, ASGITransport

from app.config import get_settings
from app.main import app
from app.db.engine import init_db
from app.middleware.rate_limit import RateLimitMiddleware


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Tests share the default 127.0.0.1 client IP; without a reset the
    /api/v1/orders 10-rpm cap gets exhausted across test_orders.py runs and
    unrelated tests 429. Walk the built middleware stack once and clear."""
    stack = getattr(app, "middleware_stack", None) or app.build_middleware_stack()
    app.middleware_stack = stack
    cur = stack
    while cur is not None:
        if isinstance(cur, RateLimitMiddleware):
            cur._reset()
            break
        cur = getattr(cur, "app", None)
    yield


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
