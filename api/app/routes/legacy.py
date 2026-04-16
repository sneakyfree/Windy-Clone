"""Legacy endpoints — /api/v1/legacy/*

Provides the user's recording stats and readiness scores
for the Legacy Dashboard (home page).

Data is fetched from Windy Pro's account-server and processed locally,
with graceful degradation to a cached snapshot when Pro is unreachable.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import CurrentUser, get_current_user
from ..db.engine import get_db
from ..services.data_fetcher import fetch_recording_stats, fetch_training_bundles
from ..services.readiness import calculate_readiness

router = APIRouter()


def _data_source_banner(stale: bool, unavailable: bool, fetched_at: str | None) -> dict | None:
    """Build the 'data may be stale' banner payload for the frontend."""
    if unavailable:
        return {
            "severity": "warning",
            "message": "We can't reach Windy Pro right now — check back in a minute.",
        }
    if stale:
        return {
            "severity": "info",
            "message": "Windy Pro is slow to respond. Showing your last synced data — it may be stale.",
            "last_synced": fetched_at,
        }
    return None


@router.get("/stats")
async def get_legacy_stats(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    User's recording statistics.

    Returns total words, audio hours, video minutes, session count,
    and quality information — fetched from Windy Pro (cached fallback).
    """
    result = await fetch_recording_stats(user.identity_id, jwt_token=user.raw_token, db=db)
    stats = result.stats

    return {
        "identity_id": user.identity_id,
        "display_name": user.display_name,
        "stats": {
            "total_words": stats.total_words,
            "hours_audio": stats.hours_audio,
            "minutes_video": stats.minutes_video,
            "session_count": stats.session_count,
        },
        "quality": {
            "average_score": stats.avg_quality_score,
            "label": stats.quality_label,
            "distribution": stats.quality_distribution,
        },
        "stale": result.stale,
        "unavailable": result.unavailable,
        "banner": _data_source_banner(result.stale, result.unavailable, result.fetched_at),
    }


@router.get("/readiness")
async def get_readiness(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Voice twin, digital avatar, and soul file readiness scores."""
    result = await fetch_recording_stats(user.identity_id, jwt_token=user.raw_token, db=db)
    readiness = calculate_readiness(result.stats)

    return {
        "identity_id": user.identity_id,
        "readiness": {
            "voice_twin": {
                "percentage": readiness.voice_twin,
                "message": readiness.voice_twin_message,
            },
            "digital_avatar": {
                "percentage": readiness.digital_avatar,
                "message": readiness.digital_avatar_message,
            },
            "soul_file": {
                "percentage": readiness.soul_file,
                "message": readiness.soul_file_message,
            },
            "overall": readiness.overall,
        },
        "stale": result.stale,
        "unavailable": result.unavailable,
        "banner": _data_source_banner(result.stale, result.unavailable, result.fetched_at),
    }


@router.get("/timeline")
async def get_timeline(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Recording history timeline — list of training-ready bundles."""
    result = await fetch_training_bundles(user.identity_id, jwt_token=user.raw_token, db=db)

    return {
        "identity_id": user.identity_id,
        "bundles": [b.model_dump() for b in result.bundles],
        "total": len(result.bundles),
        "stale": result.stale,
        "unavailable": result.unavailable,
        "banner": _data_source_banner(result.stale, result.unavailable, result.fetched_at),
    }
