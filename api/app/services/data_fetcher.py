"""Fetch recording data from Windy Pro's account-server.

Windy Clone never stores audio/video — it reads stats from Pro.
In dev mode, returns mock data matching the frontend.

Production path: live HTTP → write-through to cache. If Pro is unreachable,
fall back to the last-known-good cached snapshot with `stale=True`. If nothing
has ever been cached, `unavailable=True`.
"""

import json
import logging
from datetime import datetime, timezone

import httpx
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db.models import CachedRecordingStats

logger = logging.getLogger(__name__)


class RecordingStats(BaseModel):
    """Summary statistics from Windy Pro."""
    total_words: int = 0
    hours_audio: float = 0.0
    minutes_video: float = 0.0
    session_count: int = 0
    avg_quality_score: float = 0.0  # 0-100
    quality_label: str = "Unknown"  # "Excellent", "Good", "Fair", "Needs Improvement"
    quality_distribution: dict[str, int] = {}  # {"excellent": 800, "good": 300, ...}


class TrainingBundle(BaseModel):
    """A single training-ready bundle from Windy Pro."""
    bundle_id: str
    audio_duration_seconds: float
    video_duration_seconds: float
    word_count: int
    quality_score: float
    quality_tier: str
    created_at: str


class StatsResult(BaseModel):
    """Envelope so callers can render a 'data may be stale' banner."""
    stats: RecordingStats
    stale: bool = False
    unavailable: bool = False
    fetched_at: str | None = None  # ISO8601 of the cached snapshot, if stale


class BundlesResult(BaseModel):
    """Bundles envelope mirroring StatsResult."""
    bundles: list[TrainingBundle]
    stale: bool = False
    unavailable: bool = False
    fetched_at: str | None = None


# ── Mock data for dev mode ──
_MOCK_STATS = RecordingStats(
    total_words=847293,
    hours_audio=42.7,
    minutes_video=18.3,
    session_count=1247,
    avg_quality_score=91.5,
    quality_label="Excellent",
    quality_distribution={"excellent": 823, "good": 312, "fair": 87, "needs_improvement": 25},
)

_MOCK_BUNDLES = [
    TrainingBundle(
        bundle_id=f"bundle-{i:04d}",
        audio_duration_seconds=120 + (i * 7.3),
        video_duration_seconds=max(0, 30 + (i * 2.1) if i % 3 == 0 else 0),
        word_count=450 + (i * 12),
        quality_score=85 + (i % 15),
        quality_tier="excellent" if (85 + i % 15) >= 90 else "good",
        created_at=f"2026-03-{min(28, 1 + i):02d}T10:00:00Z",
    )
    for i in range(20)
]


def _parse_stats(data: dict) -> RecordingStats:
    return RecordingStats(
        total_words=data.get("total_words", 0),
        hours_audio=data.get("hours_audio", 0),
        minutes_video=data.get("minutes_video", 0),
        session_count=data.get("session_count", 0),
        avg_quality_score=data.get("avg_quality_score", 0),
        quality_label=data.get("quality_label", "Unknown"),
        quality_distribution=data.get("quality_distribution", {}),
    )


def _parse_bundles(data: dict) -> list[TrainingBundle]:
    return [
        TrainingBundle(
            bundle_id=b["bundle_id"],
            audio_duration_seconds=b.get("audio_duration_seconds", 0),
            video_duration_seconds=b.get("video_duration_seconds", 0),
            word_count=b.get("word_count", 0),
            quality_score=b.get("quality_score", 0),
            quality_tier=b.get("quality_tier", "unknown"),
            created_at=b.get("created_at", ""),
        )
        for b in data.get("bundles", [])
    ]


async def _load_cache_row(
    db: AsyncSession | None, identity_id: str
) -> CachedRecordingStats | None:
    if db is None:
        return None
    result = await db.execute(
        select(CachedRecordingStats).where(CachedRecordingStats.identity_id == identity_id)
    )
    return result.scalar_one_or_none()


def _apply_cache_fields(
    row: CachedRecordingStats,
    *,
    stats: RecordingStats | None,
    bundles: list[TrainingBundle] | None,
    now: datetime,
) -> None:
    if stats is not None:
        row.stats_json = json.dumps(stats.model_dump())
    if bundles is not None:
        row.bundles_json = json.dumps([b.model_dump() for b in bundles])
    row.fetched_at = now


async def _write_cache(
    db: AsyncSession | None,
    identity_id: str,
    *,
    stats: RecordingStats | None = None,
    bundles: list[TrainingBundle] | None = None,
) -> None:
    """Upsert the cache row.

    Two concurrent fetches for a new identity_id used to race on SELECT →
    INSERT and hit UNIQUE(identity_id). We now catch IntegrityError on the
    insert path, rollback, re-read the row the other coroutine just wrote,
    and update in place. UPDATE-path requests are unaffected.
    """
    if db is None:
        return
    now = datetime.now(timezone.utc)

    row = await _load_cache_row(db, identity_id)
    inserting = row is None
    if inserting:
        row = CachedRecordingStats(identity_id=identity_id, fetched_at=now)
        db.add(row)
    _apply_cache_fields(row, stats=stats, bundles=bundles, now=now)

    try:
        await db.commit()
    except IntegrityError:
        if not inserting:
            # We were on the UPDATE path — a genuine integrity error, not a race.
            raise
        await db.rollback()
        existing = await _load_cache_row(db, identity_id)
        if existing is None:
            # Nothing to update — shouldn't happen, but don't deadlock.
            return
        _apply_cache_fields(existing, stats=stats, bundles=bundles, now=now)
        await db.commit()


async def fetch_recording_stats(
    identity_id: str,
    jwt_token: str | None = None,
    db: AsyncSession | None = None,
) -> StatsResult:
    """GET /api/v1/recordings/stats with cache fallback.

    In dev mode, returns mock data. In production, a live-fetch failure
    returns the last cached snapshot with `stale=True`.
    """
    settings = get_settings()

    if settings.dev_mode:
        return StatsResult(stats=_MOCK_STATS)

    headers = {}
    if jwt_token:
        headers["Authorization"] = f"Bearer {jwt_token}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.windy_pro_api_url}/api/v1/recordings/stats",
                headers=headers,
            )
            resp.raise_for_status()
            stats = _parse_stats(resp.json())
        await _write_cache(db, identity_id, stats=stats)
        return StatsResult(stats=stats)
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        logger.warning("windy-pro stats fetch failed for %s: %s", identity_id, exc)

    row = await _load_cache_row(db, identity_id)
    if row is not None and row.stats_json:
        cached = RecordingStats(**json.loads(row.stats_json))
        fetched = row.fetched_at.isoformat() if row.fetched_at else None
        return StatsResult(stats=cached, stale=True, fetched_at=fetched)

    return StatsResult(stats=RecordingStats(), unavailable=True)


async def fetch_training_bundles(
    identity_id: str,
    jwt_token: str | None = None,
    db: AsyncSession | None = None,
) -> BundlesResult:
    """GET /api/v1/clone/training-data with cache fallback."""
    settings = get_settings()

    if settings.dev_mode:
        return BundlesResult(bundles=list(_MOCK_BUNDLES))

    headers = {}
    if jwt_token:
        headers["Authorization"] = f"Bearer {jwt_token}"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{settings.windy_pro_api_url}/api/v1/clone/training-data",
                headers=headers,
            )
            resp.raise_for_status()
            bundles = _parse_bundles(resp.json())
        await _write_cache(db, identity_id, bundles=bundles)
        return BundlesResult(bundles=bundles)
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        logger.warning("windy-pro bundles fetch failed for %s: %s", identity_id, exc)

    row = await _load_cache_row(db, identity_id)
    if row is not None and row.bundles_json:
        cached = [TrainingBundle(**b) for b in json.loads(row.bundles_json)]
        fetched = row.fetched_at.isoformat() if row.fetched_at else None
        return BundlesResult(bundles=cached, stale=True, fetched_at=fetched)

    return BundlesResult(bundles=[], unavailable=True)
