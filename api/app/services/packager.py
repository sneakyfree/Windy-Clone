"""Data packager — prepare recording bundles for provider upload.

Each provider expects data in a specific format (MP3, WAV, MP4, ZIP).
This service handles format conversion and packaging.
"""

import io
import zipfile
from pydantic import BaseModel

from .data_fetcher import TrainingBundle


class PackageResult(BaseModel):
    """Result of packaging bundles for a provider."""
    provider_id: str
    format: str
    total_files: int
    total_size_bytes: int
    bundle_ids: list[str]


# ── Format requirements per provider ──

PROVIDER_FORMATS: dict[str, dict] = {
    "elevenlabs": {
        "audio_format": "mp3",
        "sample_rate": 44100,
        "max_file_size_mb": 50,
    },
    "heygen": {
        "video_format": "mp4",
        "resolution": "1080p",
        "max_file_size_mb": 100,
    },
    "playht": {
        "audio_format": "wav",
        "sample_rate": 44100,
        "max_file_size_mb": 50,
    },
    "resembleai": {
        "audio_format": "wav",
        "sample_rate": 22050,
        "max_file_size_mb": 50,
    },
}


def get_format_requirements(provider_id: str) -> dict:
    """Get format requirements for a provider."""
    return PROVIDER_FORMATS.get(provider_id, {"audio_format": "wav", "sample_rate": 44100})


async def package_bundles(
    provider_id: str,
    bundles: list[TrainingBundle],
) -> PackageResult:
    """
    Package training bundles for a specific provider.

    In production, this would:
    1. Download raw audio/video from Windy Cloud
    2. Convert to provider-required format
    3. Apply quality filters (remove low-quality segments)
    4. Create a ZIP or multi-part upload package
    5. Return the packaged result

    For now, returns metadata about what would be packaged.
    """
    reqs = get_format_requirements(provider_id)

    # Filter bundles based on provider type
    if reqs.get("video_format"):
        # Avatar providers need video bundles
        valid_bundles = [b for b in bundles if b.video_duration_seconds > 0]
    else:
        # Voice providers need audio bundles
        valid_bundles = [b for b in bundles if b.audio_duration_seconds > 0]

    # Sort by quality (highest first)
    valid_bundles.sort(key=lambda b: b.quality_score, reverse=True)

    # Estimate packed size (rough: 1 min audio ≈ 1MB MP3, 5MB WAV)
    size_per_min = 5_000_000 if reqs.get("audio_format") == "wav" else 1_000_000
    total_duration = sum(b.audio_duration_seconds for b in valid_bundles)
    estimated_size = int((total_duration / 60) * size_per_min)

    return PackageResult(
        provider_id=provider_id,
        format=reqs.get("audio_format", reqs.get("video_format", "zip")),
        total_files=len(valid_bundles),
        total_size_bytes=estimated_size,
        bundle_ids=[b.bundle_id for b in valid_bundles],
    )
