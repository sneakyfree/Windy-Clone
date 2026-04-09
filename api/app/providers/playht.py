"""PlayHT voice cloning adapter.

Implements CloneProvider protocol for PlayHT's voice synthesis API.

API Reference: https://docs.play.ht/reference
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


class PlayHTProvider:
    """PlayHT voice cloning adapter."""

    name = "PlayHT"
    provider_type = "voice"

    API_BASE = "https://api.play.ht/api/v2"

    def _headers(self) -> dict[str, str]:
        settings = get_settings()
        return {
            "Authorization": f"Bearer {settings.playht_api_key}",
            "X-User-ID": settings.playht_user_id,
            "Content-Type": "application/json",
        }

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            id="playht",
            name="PlayHT",
            provider_type="voice",
            description="Ultra-realistic voice synthesis with fine-grained control. Your Voice Twin with adjustable emotion and pacing.",
            rating=4.6,
            starting_price=8,
            turnaround="10-30 minutes",
            features=["Emotion control", "SSML support", "API access", "Streaming", "Custom pronunciation"],
            logo="▶️",
        )

    async def get_pricing(self) -> list[PricingTier]:
        return [
            PricingTier(
                name="Standard Clone",
                price=8.0,
                description="Quality voice clone from audio samples.",
                features=["Short audio sample", "Good quality", "Fast processing"],
                min_audio_hours=0.1,
            ),
            PricingTier(
                name="Ultra Clone",
                price=20.0,
                description="Premium voice clone with emotion control.",
                features=["2+ hours audio", "Emotion control", "SSML", "Highest fidelity"],
                min_audio_hours=2.0,
            ),
        ]

    async def check_compatibility(self, data_stats: DataStats) -> CompatibilityResult:
        if data_stats.hours_audio < 0.1:
            return CompatibilityResult(
                compatible=False,
                message="You need at least a few minutes of audio.",
                missing=["audio recordings"],
            )

        if data_stats.hours_audio >= 2.0:
            return CompatibilityResult(
                compatible=True,
                message="You qualify for an Ultra Clone with emotion control!",
                recommended_tier="Ultra Clone",
            )

        return CompatibilityResult(
            compatible=True,
            message="You can create a Standard Clone. More audio unlocks Ultra quality.",
            recommended_tier="Standard Clone",
        )

    async def prepare_upload(self, bundles: list[dict]) -> PreparedPackage:
        total_files = len(bundles)
        total_bytes = sum(b.get("size_bytes", 0) for b in bundles)

        return PreparedPackage(
            provider_id="playht",
            format="wav",
            total_files=total_files,
            total_size_bytes=total_bytes,
            metadata={"encoding": "wav", "sample_rate": 44100},
        )

    async def upload(self, package: PreparedPackage) -> UploadResult:
        settings = get_settings()
        if not settings.playht_api_key:
            return UploadResult(
                job_id="ph-pending-no-key",
                status="error",
                estimated_duration_seconds=None,
            )

        return UploadResult(
            job_id="ph-job-placeholder",
            status="queued",
            estimated_duration_seconds=600,
        )

    async def get_training_status(self, job_id: str) -> TrainingStatus:
        return TrainingStatus(
            job_id=job_id,
            status="completed",
            progress=100,
            message="Your Voice Twin is ready!",
            estimated_remaining_seconds=0,
        )

    async def get_result(self, job_id: str) -> CloneResult:
        return CloneResult(
            model_id=f"ph-voice-{job_id}",
            clone_type="voice",
            provider_id="playht",
            name="My Voice — PlayHT",
            quality_label="Standard",
            preview_url=None,
        )

    async def preview(self, model_id: str, text: str) -> bytes:
        settings = get_settings()
        if not settings.playht_api_key:
            return b""

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.API_BASE}/tts",
                headers=self._headers(),
                json={
                    "text": text,
                    "voice": model_id,
                    "output_format": "mp3",
                    "speed": 1.0,
                },
            )
            resp.raise_for_status()
            return resp.content
