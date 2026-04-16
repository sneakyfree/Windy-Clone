"""ElevenLabs voice cloning adapter.

Real HTTP against ElevenLabs' voice-cloning and TTS APIs:
  - POST /v1/voices/add              → submit training (multipart)
  - GET  /v1/voices/{voice_id}       → check status (fine_tuning.state)
  - POST /v1/text-to-speech/{voice_id} → preview synthesis

API reference: https://elevenlabs.io/docs/api-reference
"""

from __future__ import annotations

import logging

import httpx

from ..config import get_settings
from .base import (
    CloneResult,
    CompatibilityResult,
    DataStats,
    PreparedPackage,
    PricingTier,
    ProviderInfo,
    TrainingStatus,
    UploadResult,
)

logger = logging.getLogger(__name__)


class ElevenLabsProvider:
    """ElevenLabs voice cloning adapter."""

    name = "ElevenLabs"
    provider_type = "voice"

    API_BASE = "https://api.elevenlabs.io/v1"

    def _api_key(self) -> str:
        return get_settings().elevenlabs_api_key

    def _json_headers(self) -> dict[str, str]:
        return {"xi-api-key": self._api_key(), "Content-Type": "application/json"}

    def _auth_header(self) -> dict[str, str]:
        # Multipart requests must not force Content-Type — httpx sets boundary.
        return {"xi-api-key": self._api_key()}

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
        """Submit training — POST /v1/voices/add (multipart form).

        Expects the caller to have placed audio files at
        `package.metadata["audio_files"]` as a list of
        `(filename, bytes, content_type)` tuples, plus `voice_name`.
        Returns voice_id as job_id.
        """
        if not self._api_key():
            raise RuntimeError("ELEVENLABS_API_KEY is not configured")

        voice_name = package.metadata.get("voice_name", "Windy Voice Twin")
        audio_files = package.metadata.get("audio_files") or []
        if not audio_files:
            raise RuntimeError("no audio files provided for training submission")

        files = [("files", (fname, data, ctype)) for (fname, data, ctype) in audio_files]
        data = {
            "name": voice_name,
            "description": "Voice Twin generated by Windy Clone",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.API_BASE}/voices/add",
                headers=self._auth_header(),
                data=data,
                files=files,
            )
            resp.raise_for_status()
            body = resp.json()

        voice_id = body.get("voice_id")
        if not voice_id:
            raise RuntimeError(f"ElevenLabs did not return a voice_id: {body}")

        return UploadResult(job_id=voice_id, status="queued", estimated_duration_seconds=300)

    async def get_training_status(self, job_id: str) -> TrainingStatus:
        """Poll training status — GET /v1/voices/{voice_id}."""
        if not self._api_key():
            raise RuntimeError("ELEVENLABS_API_KEY is not configured")

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{self.API_BASE}/voices/{job_id}",
                headers=self._auth_header(),
            )
            resp.raise_for_status()
            body = resp.json()

        fine = body.get("fine_tuning") or {}
        state_map = fine.get("state") or {}
        # ElevenLabs returns {"eleven_multilingual_v2": "fine_tuned"} style per-model
        # state maps. Treat any "fine_tuned" or "finished" as completed.
        raw_state = next(iter(state_map.values()), "completed") if state_map else "completed"

        if raw_state in ("fine_tuned", "finished", "completed"):
            status = "completed"
            progress = 100
            message = "Your Voice Twin is ready!"
        elif raw_state in ("fine_tuning", "queued", "processing"):
            status = "training"
            progress = int(fine.get("finetuning_progress", 0) * 100)
            message = "Training your Voice Twin…"
        else:
            status = raw_state
            progress = 0
            message = f"ElevenLabs state: {raw_state}"

        return TrainingStatus(
            job_id=job_id,
            status=status,
            progress=progress,
            message=message,
            estimated_remaining_seconds=None,
        )

    async def get_result(self, job_id: str) -> CloneResult:
        """Fetch the trained voice model — GET /v1/voices/{voice_id}."""
        if not self._api_key():
            raise RuntimeError("ELEVENLABS_API_KEY is not configured")

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{self.API_BASE}/voices/{job_id}",
                headers=self._auth_header(),
            )
            resp.raise_for_status()
            body = resp.json()

        return CloneResult(
            model_id=body.get("voice_id", job_id),
            clone_type="voice",
            provider_id="elevenlabs",
            name=body.get("name", "My Voice — ElevenLabs"),
            quality_label="Studio Quality",
            preview_url=body.get("preview_url"),
        )

    async def preview(self, model_id: str, text: str) -> bytes:
        """Generate a TTS preview — POST /v1/text-to-speech/{voice_id}."""
        if not self._api_key():
            return b""

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.API_BASE}/text-to-speech/{model_id}",
                headers=self._json_headers(),
                json={
                    "text": text,
                    "model_id": "eleven_multilingual_v2",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.8},
                },
            )
            resp.raise_for_status()
            return resp.content
