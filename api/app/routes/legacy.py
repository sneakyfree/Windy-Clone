"""Legacy endpoints — /api/v1/legacy/*

Provides the user's recording stats and readiness scores
for the Legacy Dashboard (home page).

Data is fetched from Windy Pro's account-server and processed locally.
"""

from fastapi import APIRouter, Depends

from ..auth.dependencies import CurrentUser, get_current_user
from ..services.data_fetcher import fetch_recording_stats, fetch_training_bundles
from ..services.readiness import calculate_readiness

router = APIRouter()


@router.get("/stats")
async def get_legacy_stats(user: CurrentUser = Depends(get_current_user)):
    """
    User's recording statistics.

    Returns total words, audio hours, video minutes, session count,
    and quality information — fetched from Windy Pro.
    """
    stats = await fetch_recording_stats(user.identity_id, jwt_token=user.raw_token)

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
    }


@router.get("/readiness")
async def get_readiness(user: CurrentUser = Depends(get_current_user)):
    """
    Voice twin, digital avatar, and soul file readiness scores.

    Each score is 0-100 with a friendly progress message.
    """
    stats = await fetch_recording_stats(user.identity_id, jwt_token=user.raw_token)
    readiness = calculate_readiness(stats)

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
    }


@router.get("/timeline")
async def get_timeline(user: CurrentUser = Depends(get_current_user)):
    """
    Recording history timeline — list of training-ready bundles.

    Used for the Legacy page's timeline visualization.
    """
    bundles = await fetch_training_bundles(user.identity_id, jwt_token=user.raw_token)

    return {
        "identity_id": user.identity_id,
        "bundles": [b.model_dump() for b in bundles],
        "total": len(bundles),
    }
