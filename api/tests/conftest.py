"""Pytest fixtures for Windy Clone API tests."""

# ── Critical ordering: set DATABASE_URL before any `app.*` module is
# imported, so Settings picks up the test override instead of the
# default `sqlite+aiosqlite:///<repo>/data/windy_clone.db`. On CI the
# `data/` directory is .gitignore'd and absent, which is why the
# default used to die with
# `sqlite3.OperationalError: unable to open database file`.
#
# We use a per-session tmp file rather than `:memory:` because this
# repo's engine module (`api/app/db/engine.py`) caches a single engine
# globally and hands out pooled connections. With `:memory:` each
# pooled aiosqlite connection would see an empty private DB; a real
# file path keeps every connection pointed at the same tables and
# matches the dev runtime exactly. The tmp dir is never cleaned up —
# pytest-xdist-safe and negligible on CI.

import os
import tempfile

_TEST_DB_DIR = tempfile.mkdtemp(prefix="windy-clone-test-")
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_TEST_DB_DIR}/test.db")

import pytest  # noqa: E402
from httpx import AsyncClient, ASGITransport  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402
from app.db.engine import init_db  # noqa: E402
from app.middleware.rate_limit import RateLimitMiddleware  # noqa: E402


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
    await init_db()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
