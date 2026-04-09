"""Resemble AI voice cloning adapter.

Implements CloneProvider protocol for Resemble AI's voice API.

API Reference: https://docs.app.resemble.ai/
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


class ResembleAIProvider:
    """Resemble AI voice cloning adapter."""

    name = "Resemble AI"
    provider_type = "voice"

    API_BASE = "https://app.resemble.ai/api/v2"

    def _headers(self) -> dict[str, str]:
        settings = get_settings()
        return {
            "Authorization": f"Token token={settings.resembleai_api_key}",
            "Content-Type": "application/json",
        }

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            id="resembleai",
            name="Resemble AI",
            provider_type="voice",
            description="Professional-grade voice cloning with real-time synthesis. Built for enterprise quality at personal scale.",
            rating=4.5,
            starting_price=10,
            turnaround="15-30 minutes",
            features=["Real-time synthesis", "Voice editing", "Watermarking", "Localization", "Neural TTS"],
            logo="🔊",
        )

    async def get_pricing(self) -> list[PricingTier]:
        return [
            PricingTier(
                name="Basic Clone",
                price=10.0,
                description="Quick voice clone for personal use.",
                features=["Short audio", "Good quality", "Watermark-free"],
                min_audio_hours=0.1,
            ),
            PricingTier(
                name="Pro Clone",
                price=25.0,
                description="Enterprise-grade voice with real-time streaming.",
                features=["3+ hours audio", "Real-time", "Voice editing", "Enterprise SLA"],
                min_audio_hours=3.0,
            ),
        ]

    async def check_compatibility(self, data_stats: DataStats) -> CompatibilityResult:
        if data_stats.hours_audio < 0.1:
            return CompatibilityResult(
                compatible=False,
                message="You need at least a few minutes of audio.",
                missing=["audio recordings"],
            )

        if data_stats.hours_audio >= 3.0:
            return CompatibilityResult(
                compatible=True,
                message="You qualify for a Pro Clone with real-time synthesis!",
                recommended_tier="Pro Clone",
            )

        return CompatibilityResult(
            compatible=True,
            message="You can create a Basic Clone. More audio unlocks Pro quality.",
            recommended_tier="Basic Clone",
        )

    async def prepare_upload(self, bundles: list[dict]) -> PreparedPackage:
        total_files = len(bundles)
        total_bytes = sum(b.get("size_bytes", 0) for b in bundles)

        return PreparedPackage(
            provider_id="resembleai",
            format="wav",
            total_files=total_files,
            total_size_bytes=total_bytes,
            metadata={"encoding": "wav", "sample_rate": 22050},
        )

    async def upload(self, package: PreparedPackage) -> UploadResult:
        settings = get_settings()
        if not settings.resembleai_api_key:
            return UploadResult(
                job_id="ra-pending-no-key",
                status="error",
                estimated_duration_seconds=None,
            )

        return UploadResult(
            job_id="ra-job-placeholder",
            status="queued",
            estimated_duration_seconds=900,
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
            model_id=f"ra-voice-{job_id}",
            clone_type="voice",
            provider_id="resembleai",
            name="My Voice — Resemble AI",
            quality_label="Standard",
            preview_url=None,
        )

    async def preview(self, model_id: str, text: str) -> bytes:
        settings = get_settings()
        if not settings.resembleai_api_key:
            return b""

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.API_BASE}/clips",
                headers=self._headers(),
                json={
                    "voice_uuid": model_id,
                    "body": text,
                    "is_archived": False,
                },
            )
            resp.raise_for_status()
            return resp.content
