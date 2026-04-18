"""Tests for RateLimitMiddleware (P1 #1)."""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.middleware.rate_limit import RateLimitMiddleware


async def _find_limiter() -> RateLimitMiddleware:
    """Starlette wraps middlewares; reach in to reset state between tests."""
    # FastAPI/Starlette compose middlewares at build_middleware_stack time,
    # but we added RateLimitMiddleware via app.add_middleware before the
    # stack is materialised. The simpler route for tests: clear the bucket
    # map via a fresh instance. The wrapped app already has one instance;
    # we need to reach it. `user_middleware` holds the un-built middleware
    # specs with args; we find ours by class name.
    for mw in app.user_middleware:
        if mw.cls is RateLimitMiddleware:
            # Pull the live instance from the built stack.
            stack = app.middleware_stack
            while stack is not None:
                if isinstance(stack, RateLimitMiddleware):
                    stack._reset()
                    return stack
                stack = getattr(stack, "app", None)
    raise AssertionError("RateLimitMiddleware not found")


@pytest.fixture(autouse=True)
async def _reset_limiter():
    app.middleware_stack = app.build_middleware_stack()
    await _find_limiter()
    yield


@pytest.mark.anyio
async def test_health_is_unlimited():
    """Liveness probe must never get 429'd."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        for _ in range(50):
            resp = await c.get("/health")
            assert resp.status_code == 200


@pytest.mark.anyio
async def test_orders_capped_at_10_per_minute():
    """11th POST /api/v1/orders inside 60s → 429 with Retry-After."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        for i in range(10):
            r = await c.post(
                "/api/v1/orders",
                json={"provider_id": "elevenlabs", "clone_type": "voice"},
            )
            assert r.status_code == 200, f"req {i+1}: {r.status_code} {r.text}"

        r = await c.post(
            "/api/v1/orders",
            json={"provider_id": "elevenlabs", "clone_type": "voice"},
        )
        assert r.status_code == 429
        assert int(r.headers["retry-after"]) >= 1
        assert "Too many requests" in r.json()["detail"]


@pytest.mark.anyio
async def test_webhooks_capped_at_30_per_minute():
    """31st webhook hit → 429 even with bad sig (still cheaper than HMAC DoS)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # 30 allowed within window (they 403 on bad sig, but that's still a 'hit').
        for i in range(30):
            r = await c.post("/api/v1/webhooks/identity/created", content=b"{}")
            assert r.status_code in (400, 403), f"req {i+1}: unexpected {r.status_code}"

        r = await c.post("/api/v1/webhooks/identity/created", content=b"{}")
        assert r.status_code == 429


@pytest.mark.anyio
async def test_x_forwarded_for_distinguishes_clients():
    """Two clients behind a proxy should each get their own bucket."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # Client A hits 10× (caps out).
        for _ in range(10):
            await c.post(
                "/api/v1/orders",
                json={"provider_id": "elevenlabs", "clone_type": "voice"},
                headers={"X-Forwarded-For": "10.0.0.1"},
            )
        r = await c.post(
            "/api/v1/orders",
            json={"provider_id": "elevenlabs", "clone_type": "voice"},
            headers={"X-Forwarded-For": "10.0.0.1"},
        )
        assert r.status_code == 429, "client A should be limited"

        # Client B (different IP) still has a fresh bucket.
        r = await c.post(
            "/api/v1/orders",
            json={"provider_id": "elevenlabs", "clone_type": "voice"},
            headers={"X-Forwarded-For": "10.0.0.2"},
        )
        assert r.status_code == 200, f"client B should not be rate-limited, got {r.status_code}"
