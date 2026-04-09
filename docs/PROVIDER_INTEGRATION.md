# Provider Integration Guide

How to add a new voice/avatar provider to Windy Clone.

## Architecture

Windy Clone uses a **provider adapter pattern** — each provider implements a Python Protocol (`CloneProvider`). Adding a new provider requires:

1. One new Python class
2. One registry entry
3. One config variable for the API key

No route changes, no frontend changes needed.

## Step 1: Create the Adapter

Create a new file at `api/app/providers/{provider_name}.py`:

```python
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


class MyNewProvider:
    """My New Provider voice cloning adapter."""

    name = "My New Provider"
    provider_type = "voice"  # or "avatar" or "both"

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            id="my-provider",
            name="My New Provider",
            provider_type="voice",
            description="Description for grandma — no jargon!",
            rating=4.5,
            starting_price=10,
            turnaround="5-10 minutes",
            features=["Feature 1", "Feature 2"],
            logo="🎵",
        )

    async def get_pricing(self) -> list[PricingTier]:
        return [
            PricingTier(
                name="Basic",
                price=10.0,
                description="Basic tier description.",
                features=["Feature"],
                min_audio_hours=0.1,
            ),
        ]

    async def check_compatibility(self, data_stats: DataStats) -> CompatibilityResult:
        if data_stats.hours_audio < 0.1:
            return CompatibilityResult(
                compatible=False,
                message="Need more audio.",
                missing=["audio recordings"],
            )
        return CompatibilityResult(
            compatible=True,
            message="Ready to go!",
            recommended_tier="Basic",
        )

    async def prepare_upload(self, bundles: list[dict]) -> PreparedPackage:
        # Package bundles for upload
        ...

    async def upload(self, package: PreparedPackage) -> UploadResult:
        # Upload to provider API
        ...

    async def get_training_status(self, job_id: str) -> TrainingStatus:
        # Poll provider for training status
        ...

    async def get_result(self, job_id: str) -> CloneResult:
        # Get completed clone
        ...

    async def preview(self, model_id: str, text: str) -> bytes:
        # Generate TTS/video preview
        ...
```

## Step 2: Register the Provider

Add a `ProviderInfo` entry to `api/app/providers/registry.py`:

```python
ProviderInfo(
    id="my-provider",
    name="My New Provider",
    provider_type="voice",
    description="...",
    rating=4.5,
    starting_price=10,
    turnaround="5-10 minutes",
    features=["..."],
    logo="🎵",
),
```

## Step 3: Add Config

Add the API key to `api/app/config.py`:

```python
my_provider_api_key: str = ""
```

And to `.env.example`:

```
MY_PROVIDER_API_KEY=
```

## Step 4: Wire to Job Tracker

Add the adapter instance to `api/app/services/job_tracker.py`:

```python
from ..providers.my_provider import MyNewProvider

_ADAPTERS["my-provider"] = MyNewProvider()
```

## Design Rules (The Grandma Test)

When writing provider descriptions and messages:

- ❌ "API-based voice synthesis with SSML support"
- ✅ "Your voice, recreated with incredible accuracy"
- ❌ "Upload WAV files to begin training"
- ✅ "We'll send your recordings — just one button"

Every user-facing string should be understandable by a non-technical person.

## Existing Adapters

| Provider | File | Type | Status |
|----------|------|------|--------|
| ElevenLabs | `elevenlabs.py` | Voice | Scaffolded |
| HeyGen | `heygen.py` | Avatar | Scaffolded |
| PlayHT | `playht.py` | Voice | Scaffolded |
| Resemble AI | `resembleai.py` | Voice | Scaffolded |
| Windy Clone Native | — | Both | Coming Soon (Phase 5) |
