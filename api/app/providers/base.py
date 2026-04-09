"""Base provider protocol — all provider adapters implement this interface.

Adding a new provider = one new class that implements CloneProvider.
No route changes needed.
"""

from typing import Protocol, runtime_checkable
from pydantic import BaseModel


class PricingTier(BaseModel):
    """A single pricing tier from a provider."""
    name: str
    price: float
    currency: str = "USD"
    description: str
    features: list[str] = []
    min_audio_hours: float = 0
    max_audio_hours: float | None = None


class CompatibilityResult(BaseModel):
    """Whether the user has enough data for a provider."""
    compatible: bool
    message: str
    recommended_tier: str | None = None
    missing: list[str] = []  # What the user still needs


class DataStats(BaseModel):
    """User's data summary for compatibility checking."""
    hours_audio: float
    minutes_video: float
    total_words: int
    avg_quality: float


class PreparedPackage(BaseModel):
    """A data package ready to upload to a provider."""
    provider_id: str
    format: str  # "wav", "mp3", "zip", etc.
    total_files: int
    total_size_bytes: int
    metadata: dict = {}


class UploadResult(BaseModel):
    """Result from uploading data to a provider."""
    job_id: str
    status: str
    estimated_duration_seconds: int | None = None


class TrainingStatus(BaseModel):
    """Current status of a training job."""
    job_id: str
    status: str  # "queued", "processing", "training", "completed", "failed"
    progress: int  # 0-100
    message: str
    estimated_remaining_seconds: int | None = None


class CloneResult(BaseModel):
    """A completed clone from a provider."""
    model_id: str
    clone_type: str  # "voice" / "avatar"
    provider_id: str
    name: str
    quality_label: str
    preview_url: str | None = None


class ProviderInfo(BaseModel):
    """Static provider information for the marketplace."""
    id: str
    name: str
    provider_type: str  # "voice" | "avatar" | "both"
    description: str
    rating: float
    starting_price: float
    turnaround: str
    features: list[str]
    logo: str
    featured: bool = False
    coming_soon: bool = False


@runtime_checkable
class CloneProvider(Protocol):
    """Interface for voice clone / avatar providers."""

    name: str
    provider_type: str  # "voice" | "avatar" | "both"

    def get_info(self) -> ProviderInfo: ...

    async def get_pricing(self) -> list[PricingTier]: ...

    async def check_compatibility(self, data_stats: DataStats) -> CompatibilityResult: ...

    async def prepare_upload(self, bundles: list[dict]) -> PreparedPackage: ...

    async def upload(self, package: PreparedPackage) -> UploadResult: ...

    async def get_training_status(self, job_id: str) -> TrainingStatus: ...

    async def get_result(self, job_id: str) -> CloneResult: ...

    async def preview(self, model_id: str, text: str) -> bytes: ...
