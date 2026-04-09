"""Fetch recording data from Windy Pro's account-server.

Windy Clone never stores audio/video — it reads stats from Pro.
In dev mode, returns mock data matching the frontend.
"""

import httpx
from pydantic import BaseModel

from ..config import get_settings


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


async def fetch_recording_stats(identity_id: str, jwt_token: str | None = None) -> RecordingStats:
    """
    Fetch recording statistics from Windy Pro's account-server.

    GET /api/v1/recordings/stats

    In dev mode, returns mock data.
    """
    settings = get_settings()

    if settings.dev_mode:
        return _MOCK_STATS

    headers = {}
    if jwt_token:
        headers["Authorization"] = f"Bearer {jwt_token}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.windy_pro_api_url}/api/v1/recordings/stats",
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()

    return RecordingStats(
        total_words=data.get("total_words", 0),
        hours_audio=data.get("hours_audio", 0),
        minutes_video=data.get("minutes_video", 0),
        session_count=data.get("session_count", 0),
        avg_quality_score=data.get("avg_quality_score", 0),
        quality_label=data.get("quality_label", "Unknown"),
        quality_distribution=data.get("quality_distribution", {}),
    )


async def fetch_training_bundles(identity_id: str, jwt_token: str | None = None) -> list[TrainingBundle]:
    """
    Fetch training-ready bundles from Windy Pro's account-server.

    GET /api/v1/clone/training-data

    In dev mode, returns mock bundles.
    """
    settings = get_settings()

    if settings.dev_mode:
        return _MOCK_BUNDLES

    headers = {}
    if jwt_token:
        headers["Authorization"] = f"Bearer {jwt_token}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{settings.windy_pro_api_url}/api/v1/clone/training-data",
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()

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
