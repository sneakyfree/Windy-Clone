"""Tests for the data_fetcher write-through cache race fix (P2 #8)."""

import asyncio
import json
import uuid

import httpx
import pytest

from app.config import get_settings
from app.db.engine import get_session_factory, init_db
from app.db.models import CachedRecordingStats
from app.services import data_fetcher
from app.services.data_fetcher import fetch_recording_stats
from sqlalchemy import select


def _patch_httpx(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    real = data_fetcher.httpx.AsyncClient

    def factory(*a, **kw):
        kw["transport"] = transport
        return real(*a, **kw)

    monkeypatch.setattr(data_fetcher.httpx, "AsyncClient", factory)


@pytest.fixture
def live_mode(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "dev_mode", False)
    return s


def _ok_handler(request):
    return httpx.Response(
        200,
        json={
            "total_words": 42,
            "hours_audio": 1.0,
            "minutes_video": 0.0,
            "session_count": 5,
            "avg_quality_score": 88.0,
            "quality_label": "Good",
            "quality_distribution": {"good": 5},
        },
    )


@pytest.mark.anyio
async def test_concurrent_first_fetch_does_not_raise(monkeypatch, live_mode):
    """Two parallel cache-miss fetches for the same identity must both succeed."""
    await init_db()
    _patch_httpx(monkeypatch, _ok_handler)
    factory = get_session_factory()
    identity_id = f"race-{uuid.uuid4().hex[:8]}"

    async def one_call():
        async with factory() as db:
            return await fetch_recording_stats(identity_id, jwt_token="t", db=db)

    # Two concurrent calls — pre-fix this used to raise IntegrityError on one.
    r1, r2 = await asyncio.gather(one_call(), one_call())
    assert not r1.unavailable and not r2.unavailable
    assert r1.stats.total_words == 42 and r2.stats.total_words == 42

    # Exactly one cache row persisted.
    async with factory() as db:
        rows = (
            await db.execute(
                select(CachedRecordingStats).where(CachedRecordingStats.identity_id == identity_id)
            )
        ).scalars().all()
        assert len(rows) == 1
        assert json.loads(rows[0].stats_json)["total_words"] == 42


@pytest.mark.anyio
async def test_second_fetch_updates_not_duplicates(monkeypatch, live_mode):
    """A later fetch UPDATEs the existing row rather than exploding on UNIQUE."""
    await init_db()
    _patch_httpx(monkeypatch, _ok_handler)
    factory = get_session_factory()
    identity_id = f"update-{uuid.uuid4().hex[:8]}"

    async with factory() as db:
        r1 = await fetch_recording_stats(identity_id, jwt_token="t", db=db)
        assert r1.stats.total_words == 42

    async with factory() as db:
        r2 = await fetch_recording_stats(identity_id, jwt_token="t", db=db)
        assert r2.stats.total_words == 42

        rows = (
            await db.execute(
                select(CachedRecordingStats).where(CachedRecordingStats.identity_id == identity_id)
            )
        ).scalars().all()
        assert len(rows) == 1
