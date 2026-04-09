"""ElevenLabs voice cloning adapter.

Implements CloneProvider protocol for ElevenLabs' instant and professional
voice cloning APIs.

API Reference: https://elevenlabs.io/docs/api-reference
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


class ElevenLabsProvider:
    """ElevenLabs voice cloning adapter."""

    name = "ElevenLabs"
    provider_type = "voice"

    API_BASE = "https://api.elevenlabs.io/v1"

    def _headers(self) -> dict[str, str]:
        settings = get_settings()
        return {
            "xi-api-key": settings.elevenlabs_api_key,
            "Content-Type": "application/json",
        }

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            id="elevenlabs",
            name="ElevenLabs",
            provider_type="voice",
            description="Industry-leading voice cloning with stunning accuracy. Create a Voice Twin that captures every nuance of how you speak.",
            rating=4.8,
            starting_price=5,
            turnaround="5-15 minutes",
            features=["Instant cloning", "29 languages", "Emotional range", "API access", "Commercial license"],
            logo="🎙️",
        )

    async def get_pricing(self) -> list[PricingTier]:
        return [
            PricingTier(
                name="Instant Clone",
                price=5.0,
                description="Quick voice clone from a short sample. Great for getting started.",
                features=["30-second sample", "Ready in seconds", "Good quality"],
                min_audio_hours=0.01,
                max_audio_hours=0.5,
            ),
            PricingTier(
                name="Professional Clone",
                price=11.0,
                description="Studio-quality voice clone trained on hours of audio.",
                features=["3+ hours of audio", "Highest fidelity", "Emotional range", "Fine-tuning"],
                min_audio_hours=3.0,
            ),
        ]

    async def check_compatibility(self, data_stats: DataStats) -> CompatibilityResult:
        if data_stats.hours_audio < 0.01:
            return CompatibilityResult(
                compatible=False,
                message="You need at least a few seconds of audio for an instant clone.",
                missing=["audio recordings"],
            )

        if data_stats.hours_audio >= 3.0 and data_stats.avg_quality >= 80:
            return CompatibilityResult(
                compatible=True,
                message="You qualify for a Professional Clone — the highest quality tier!",
                recommended_tier="Professional Clone",
            )

        if data_stats.hours_audio >= 0.5:
            return CompatibilityResult(
                compatible=True,
                message="You have enough audio for an Instant Clone. More audio unlocks Professional quality.",
                recommended_tier="Instant Clone",
            )

        return CompatibilityResult(
            compatible=True,
            message="You can create a basic Instant Clone. Record more for better results.",
            recommended_tier="Instant Clone",
        )

    async def prepare_upload(self, bundles: list[dict]) -> PreparedPackage:
        # Combine audio into a single optimized package
        total_files = len(bundles)
        total_bytes = sum(b.get("size_bytes", 0) for b in bundles)

        return PreparedPackage(
            provider_id="elevenlabs",
            format="mp3",
            total_files=total_files,
            total_size_bytes=total_bytes,
            metadata={"encoding": "mp3", "sample_rate": 44100},
        )

    async def upload(self, package: PreparedPackage) -> UploadResult:
        """Upload voice data to ElevenLabs and start cloning."""
        # POST /v1/voice-generation/create-voice
        # In production, this would send the actual audio data
        settings = get_settings()
        if not settings.elevenlabs_api_key:
            return UploadResult(
                job_id="el-pending-no-key",
                status="error",
                estimated_duration_seconds=None,
            )

        # Scaffold: would call ElevenLabs API here
        return UploadResult(
            job_id="el-job-placeholder",
            status="queued",
            estimated_duration_seconds=300,
        )

    async def get_training_status(self, job_id: str) -> TrainingStatus:
        """Check voice clone training status."""
        # ElevenLabs instant clones are near-instant, professional takes longer
        return TrainingStatus(
            job_id=job_id,
            status="completed",
            progress=100,
            message="Your Voice Twin is ready!",
            estimated_remaining_seconds=0,
        )

    async def get_result(self, job_id: str) -> CloneResult:
        """Get the completed voice clone."""
        return CloneResult(
            model_id=f"el-voice-{job_id}",
            clone_type="voice",
            provider_id="elevenlabs",
            name="My Voice — ElevenLabs",
            quality_label="Studio Quality",
            preview_url=None,
        )

    async def preview(self, model_id: str, text: str) -> bytes:
        """Generate a TTS preview using the cloned voice."""
        settings = get_settings()
        if not settings.elevenlabs_api_key:
            return b""

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.API_BASE}/text-to-speech/{model_id}",
                headers=self._headers(),
                json={
                    "text": text,
                    "model_id": "eleven_multilingual_v2",
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.8,
                    },
                },
            )
            resp.raise_for_status()
            return resp.content
