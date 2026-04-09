"""Provider marketplace endpoints — /api/v1/providers/*

Lists providers, details, and compatibility checks.
Provider data comes from the registry (config-driven, not hardcoded in UI).
"""

from fastapi import APIRouter, Depends, HTTPException

from ..auth.dependencies import CurrentUser, get_current_user
from ..providers.registry import get_all_providers, get_provider_by_id, get_providers_by_type
from ..providers.base import DataStats
from ..services.data_fetcher import fetch_recording_stats

router = APIRouter()


@router.get("")
async def list_providers(
    type: str = "all",
    user: CurrentUser = Depends(get_current_user),
):
    """
    List all providers with pricing and features.

    Query params:
        type: "all" | "voice" | "avatar" | "both"
    """
    providers = get_providers_by_type(type)
    return {
        "providers": [p.model_dump() for p in providers],
        "total": len(providers),
    }


@router.get("/{provider_id}")
async def get_provider_detail(
    provider_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """
    Full provider detail — features, pricing tiers, demos.
    """
    provider = get_provider_by_id(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")

    return {
        "provider": provider.model_dump(),
    }


@router.get("/{provider_id}/compat")
async def check_compatibility(
    provider_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """
    Check if the user's data is compatible with a provider.

    Returns whether they have enough audio/video for the provider's requirements.
    """
    provider = get_provider_by_id(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")

    stats = await fetch_recording_stats(user.identity_id)

    # Basic compatibility check based on provider type
    issues = []
    compatible = True

    if provider.provider_type in ("voice", "both"):
        if stats.hours_audio < 0.5:
            issues.append("Need at least 30 minutes of audio for a basic voice clone")
            compatible = False
        elif stats.hours_audio < 2.0:
            issues.append("More audio will improve voice quality — aim for 2+ hours")

    if provider.provider_type in ("avatar", "both"):
        if stats.minutes_video < 0.5:
            issues.append("Need at least 30 seconds of video for an avatar")
            compatible = False
        elif stats.minutes_video < 2.0:
            issues.append("More video will improve avatar quality — aim for 2+ minutes")

    quality_note = ""
    if stats.avg_quality_score >= 85:
        quality_note = "Your recordings are excellent quality — perfect for this provider"
    elif stats.avg_quality_score >= 70:
        quality_note = "Your recording quality is good — results will be solid"
    else:
        quality_note = "Try recording in a quieter environment for better results"
        issues.append(quality_note)

    return {
        "provider_id": provider_id,
        "compatible": compatible,
        "quality_note": quality_note,
        "issues": issues,
        "data_summary": {
            "hours_audio": stats.hours_audio,
            "minutes_video": stats.minutes_video,
            "total_words": stats.total_words,
            "quality_score": stats.avg_quality_score,
        },
    }
