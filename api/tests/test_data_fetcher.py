"""Tests for data_fetcher live + graceful-degradation paths.

The existing suite runs in dev_mode=True (returns mocks). These exercise the
live HTTP path and the fallback-to-cache-with-stale-banner path so we have
coverage for both branches.
"""

import json
import uuid
from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy import select

from app.config import get_settings
from app.db.engine import get_session_factory, init_db
from app.db.models import CachedRecordingStats
from app.services import data_fetcher
from app.services.data_fetcher import (
    RecordingStats,
    fetch_recording_stats,
    fetch_training_bundles,
)


def _new_id(tag: str) -> str:
    """Unique identity per test run — the test DB file persists across runs."""
    return f"{tag}-{uuid.uuid4().hex[:8]}"


def _patch_httpx(monkeypatch, handler):
    """Swap httpx.AsyncClient for a MockTransport-backed client."""
    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(data_fetcher.httpx, "AsyncClient", factory)


@pytest.fixture
async def db_session():
    await init_db()
    factory = get_session_factory()
    async with factory() as session:
        yield session


@pytest.fixture
def live_mode(monkeypatch):
    """Force settings.dev_mode=False without touching env."""
    settings = get_settings()
    monkeypatch.setattr(settings, "dev_mode", False)
    return settings


@pytest.mark.anyio
async def test_live_stats_success_writes_cache(monkeypatch, live_mode, db_session):
    identity_id = _new_id("stats-ok")
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/api/v1/recordings/stats")
        return httpx.Response(
            200,
            json={
                "total_words": 12345,
                "hours_audio": 3.5,
                "minutes_video": 1.2,
                "session_count": 42,
                "avg_quality_score": 88.0,
                "quality_label": "Good",
                "quality_distribution": {"good": 42},
            },
        )

    _patch_httpx(monkeypatch, handler)
    result = await fetch_recording_stats(identity_id, jwt_token="t", db=db_session)

    assert result.stale is False and result.unavailable is False
    assert result.stats.total_words == 12345
    assert result.stats.hours_audio == 3.5

    row = (
        await db_session.execute(
            select(CachedRecordingStats).where(CachedRecordingStats.identity_id == identity_id)
        )
    ).scalar_one()
    assert json.loads(row.stats_json)["total_words"] == 12345


@pytest.mark.anyio
async def test_live_stats_failure_falls_back_to_cache(monkeypatch, live_mode, db_session):
    identity_id = _new_id("stats-stale")
    cached = RecordingStats(total_words=999, hours_audio=1.1, avg_quality_score=50)
    db_session.add(
        CachedRecordingStats(
            identity_id=identity_id,
            stats_json=json.dumps(cached.model_dump()),
            fetched_at=datetime.now(timezone.utc),
        )
    )
    await db_session.commit()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    _patch_httpx(monkeypatch, handler)
    result = await fetch_recording_stats(identity_id, jwt_token="t", db=db_session)

    assert result.stale is True and result.unavailable is False
    assert result.stats.total_words == 999
    assert result.fetched_at is not None


@pytest.mark.anyio
async def test_live_stats_failure_no_cache_is_unavailable(monkeypatch, live_mode, db_session):
    identity_id = _new_id("stats-unavail")
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    _patch_httpx(monkeypatch, handler)
    result = await fetch_recording_stats(identity_id, jwt_token="t", db=db_session)

    assert result.unavailable is True
    assert result.stale is False
    assert result.stats.total_words == 0


@pytest.mark.anyio
async def test_live_bundles_success_writes_cache(monkeypatch, live_mode, db_session):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/api/v1/clone/training-data")
        return httpx.Response(
            200,
            json={
                "bundles": [
                    {
                        "bundle_id": "b-1",
                        "audio_duration_seconds": 60.0,
                        "video_duration_seconds": 0.0,
                        "word_count": 150,
                        "quality_score": 92.0,
                        "quality_tier": "excellent",
                        "created_at": "2026-04-16T10:00:00Z",
                    }
                ]
            },
        )

    _patch_httpx(monkeypatch, handler)
    result = await fetch_training_bundles(_new_id("bundles-ok"), jwt_token="t", db=db_session)

    assert result.unavailable is False and result.stale is False
    assert len(result.bundles) == 1
    assert result.bundles[0].bundle_id == "b-1"


@pytest.mark.anyio
async def test_legacy_routes_expose_banner_fields(client):
    """Dev-mode smoke: routes include banner/stale keys (null when fresh)."""
    resp = await client.get("/api/v1/legacy/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "stale" in data and "unavailable" in data and "banner" in data
    assert data["banner"] is None
