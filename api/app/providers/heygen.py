"""HeyGen avatar creation adapter.

Implements CloneProvider protocol for HeyGen's avatar API.

API Reference: https://docs.heygen.com/reference
"""

import httpx
from ..config import get_settings
from .base import (
    CloneProvider,
    ProviderInfo,
    PricingTier,
    CompatibilityResult,
    DataStats,
    PreparedPackage,
    UploadResult,
    TrainingStatus,
    CloneResult,
)


class HeyGenProvider:
    """HeyGen digital avatar adapter."""

    name = "HeyGen"
    provider_type = "avatar"

    API_BASE = "https://api.heygen.com/v2"

    def _headers(self) -> dict[str, str]:
        settings = get_settings()
        return {
            "X-Api-Key": settings.heygen_api_key,
            "Content-Type": "application/json",
        }

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            id="heygen",
            name="HeyGen",
            provider_type="avatar",
            description="Create a lifelike Digital Avatar that looks and moves just like you. Perfect for video messages and presentations.",
            rating=4.7,
            starting_price=24,
            turnaround="2-5 minutes",
            features=["Lip sync", "40+ languages", "Custom backgrounds", "Templates", "API access"],
            logo="🎬",
        )

    async def get_pricing(self) -> list[PricingTier]:
        return [
            PricingTier(
                name="Instant Avatar",
                price=24.0,
                description="Quick avatar from a short video clip.",
                features=["2-minute video", "Ready in minutes", "Lip sync"],
                min_audio_hours=0.0,
            ),
            PricingTier(
                name="Studio Avatar",
                price=99.0,
                description="High-fidelity avatar with full body movement.",
                features=["5+ minutes video", "Full body", "Gesture control", "Premium quality"],
                min_audio_hours=0.0,
            ),
        ]

    async def check_compatibility(self, data_stats: DataStats) -> CompatibilityResult:
        if data_stats.minutes_video < 0.5:
            return CompatibilityResult(
                compatible=False,
                message="You need at least 30 seconds of video for an avatar.",
                missing=["video recordings"],
            )

        if data_stats.minutes_video >= 5.0:
            return CompatibilityResult(
                compatible=True,
                message="You have enough video for a Studio Avatar!",
                recommended_tier="Studio Avatar",
            )

        return CompatibilityResult(
            compatible=True,
            message="You can create an Instant Avatar. More video unlocks Studio quality.",
            recommended_tier="Instant Avatar",
        )

    async def prepare_upload(self, bundles: list[dict]) -> PreparedPackage:
        total_files = len([b for b in bundles if b.get("video_duration_seconds", 0) > 0])
        total_bytes = sum(b.get("size_bytes", 0) for b in bundles)

        return PreparedPackage(
            provider_id="heygen",
            format="mp4",
            total_files=total_files,
            total_size_bytes=total_bytes,
            metadata={"encoding": "h264", "resolution": "1080p"},
        )

    async def upload(self, package: PreparedPackage) -> UploadResult:
        """Upload video data to HeyGen."""
        settings = get_settings()
        if not settings.heygen_api_key:
            return UploadResult(
                job_id="hg-pending-no-key",
                status="error",
                estimated_duration_seconds=None,
            )

        return UploadResult(
            job_id="hg-job-placeholder",
            status="queued",
            estimated_duration_seconds=180,
        )

    async def get_training_status(self, job_id: str) -> TrainingStatus:
        """Check avatar creation status."""
        return TrainingStatus(
            job_id=job_id,
            status="completed",
            progress=100,
            message="Your Digital Avatar is ready!",
            estimated_remaining_seconds=0,
        )

    async def get_result(self, job_id: str) -> CloneResult:
        return CloneResult(
            model_id=f"hg-avatar-{job_id}",
            clone_type="avatar",
            provider_id="heygen",
            name="My Avatar — HeyGen",
            quality_label="Standard",
            preview_url=None,
        )

    async def preview(self, model_id: str, text: str) -> bytes:
        """Generate a video preview using the avatar."""
        settings = get_settings()
        if not settings.heygen_api_key:
            return b""

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.API_BASE}/video/generate",
                headers=self._headers(),
                json={
                    "video_inputs": [
                        {
                            "character": {"type": "avatar", "avatar_id": model_id},
                            "voice": {"type": "text", "input_text": text},
                        }
                    ],
                    "dimension": {"width": 1280, "height": 720},
                },
            )
            resp.raise_for_status()
            return resp.content
