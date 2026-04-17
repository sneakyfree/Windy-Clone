"""Tests for the P0 #5 concurrency fixes.

Covers:
  * FastAPI exception handler converts transient DB OperationalError into 503.
  * Pipeline's _load_order_with_retry survives a brief read-after-write race.
"""

import asyncio
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.db.engine import get_session_factory, init_db
from app.db.models import Order, OrderStatus
from app.main import app
from app.services import clone_pipeline
from app.services.clone_pipeline import _load_order_with_retry, run_elevenlabs_pipeline


# ───────────────────── 503 exception handler ──────────────────────────────


@pytest.mark.anyio
async def test_transient_db_error_returns_503(monkeypatch):
    """When a route raises OperationalError with a lock marker, 503 + Retry-After."""

    # Inject a one-off route that raises the transient error. Using a real
    # custom route keeps the exception-handler integration honest.
    from fastapi import APIRouter
    router = APIRouter()

    @router.get("/__test_transient")
    async def boom():
        raise OperationalError("stmt", {}, Exception("database is locked"))

    app.include_router(router)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/__test_transient")

    assert resp.status_code == 503
    assert resp.headers.get("retry-after") == "1"
    assert "busy" in resp.json()["detail"].lower()


@pytest.mark.anyio
async def test_non_transient_db_error_still_500(monkeypatch):
    """A non-lock OperationalError should NOT be remapped to 503."""
    from fastapi import APIRouter
    router = APIRouter()

    @router.get("/__test_nontransient")
    async def boom():
        raise OperationalError("stmt", {}, Exception("table 'x' does not exist"))

    app.include_router(router)

    # raise_app_exceptions=False so the transport returns the 500 response
    # instead of re-raising — we want to observe the response, not the exception.
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/__test_nontransient")
    assert resp.status_code == 500


# ───────────────────── pipeline race tolerance ────────────────────────────


@pytest.mark.anyio
async def test_load_order_with_retry_waits_for_late_commit():
    """The lookup should succeed when the row appears between attempts."""
    await init_db()
    factory = get_session_factory()
    order_id = f"late-{uuid.uuid4().hex[:8]}"

    async def insert_after_delay():
        await asyncio.sleep(0.12)  # lands between attempt 2 and 3
        async with factory() as db2:
            o = Order(
                id=order_id,
                identity_id="race",
                provider_id="elevenlabs",
                provider_type="voice",
                status=OrderStatus.PENDING.value,
                progress=0,
            )
            db2.add(o)
            await db2.commit()

    async with factory() as db:
        insert_task = asyncio.create_task(insert_after_delay())
        row = await _load_order_with_retry(db, order_id, attempts=6, initial_delay=0.05)
        await insert_task
        assert row is not None
        assert row.id == order_id


@pytest.mark.anyio
async def test_load_order_with_retry_returns_none_when_truly_missing():
    """After all attempts, a genuinely absent order returns None (not raise)."""
    await init_db()
    factory = get_session_factory()
    async with factory() as db:
        row = await _load_order_with_retry(
            db, "never-existed", attempts=2, initial_delay=0.01
        )
        assert row is None


@pytest.mark.anyio
async def test_pipeline_uses_retry_helper(monkeypatch):
    """Pipeline flows through _load_order_with_retry (integration sanity)."""
    calls = {"n": 0}
    real = clone_pipeline._load_order_with_retry

    async def counting(*a, **kw):
        calls["n"] += 1
        return await real(*a, **kw)

    monkeypatch.setattr(clone_pipeline, "_load_order_with_retry", counting)

    await run_elevenlabs_pipeline(
        order_id="does-not-exist",
        identity_id="x",
        display_name=None,
        jwt_token=None,
    )
    assert calls["n"] == 1
