"""Provider registry — lookup providers by ID.

All registered providers are available in the marketplace.
Add new providers here to make them appear in the dashboard.
"""

from .base import ProviderInfo

# ── Static provider catalog ──
# Provider data stays fresh via config, not hardcoded in UI components.
# In the future this could come from a database or config API.

_PROVIDER_CATALOG: list[ProviderInfo] = [
    ProviderInfo(
        id="windy-native",
        name="Windy Clone Native",
        provider_type="both",
        description="Your data never leaves the Windy ecosystem. Built by us, for you. The most private and seamless way to create your digital twin.",
        rating=5.0,
        starting_price=0,
        turnaround="Coming Soon",
        features=["Zero data sharing", "Built-in privacy", "Full ecosystem integration"],
        logo="🌊",
        featured=True,
        coming_soon=True,
    ),
    ProviderInfo(
        id="elevenlabs",
        name="ElevenLabs",
        provider_type="voice",
        description="Industry-leading voice cloning with stunning accuracy. Create a Voice Twin that captures every nuance of how you speak.",
        rating=4.8,
        starting_price=5,
        turnaround="5-15 minutes",
        features=["Instant cloning", "29 languages", "Emotional range", "API access", "Commercial license"],
        logo="🎙️",
    ),
    ProviderInfo(
        id="heygen",
        name="HeyGen",
        provider_type="avatar",
        description="Create a lifelike Digital Avatar that looks and moves just like you. Perfect for video messages and presentations.",
        rating=4.7,
        starting_price=24,
        turnaround="2-5 minutes",
        features=["Lip sync", "40+ languages", "Custom backgrounds", "Templates", "API access"],
        logo="🎬",
    ),
    ProviderInfo(
        id="playht",
        name="PlayHT",
        provider_type="voice",
        description="Ultra-realistic voice synthesis with fine-grained control. Your Voice Twin with adjustable emotion and pacing.",
        rating=4.6,
        starting_price=8,
        turnaround="10-30 minutes",
        features=["Emotion control", "SSML support", "API access", "Streaming", "Custom pronunciation"],
        logo="▶️",
    ),
    ProviderInfo(
        id="resembleai",
        name="Resemble AI",
        provider_type="voice",
        description="Professional-grade voice cloning with real-time synthesis. Built for enterprise quality at personal scale.",
        rating=4.5,
        starting_price=10,
        turnaround="15-30 minutes",
        features=["Real-time synthesis", "Voice editing", "Watermarking", "Localization", "Neural TTS"],
        logo="🔊",
    ),
    ProviderInfo(
        id="synthesia",
        name="Synthesia",
        provider_type="avatar",
        description="Turn your video recordings into a studio-quality Digital Avatar. Create professional video content from just text.",
        rating=4.6,
        starting_price=22,
        turnaround="5-10 minutes",
        features=["Studio quality", "130+ languages", "Templates", "Brand kit", "Collaboration"],
        logo="🎥",
    ),
    ProviderInfo(
        id="did",
        name="D-ID",
        provider_type="avatar",
        description="Bring photos to life with natural animation. Transform a single photo into a speaking, animated Digital Avatar.",
        rating=4.4,
        starting_price=6,
        turnaround="1-3 minutes",
        features=["Photo animation", "Fast creation", "Chat mode", "Streaming API", "Emotions"],
        logo="👤",
    ),
    ProviderInfo(
        id="tavus",
        name="Tavus",
        provider_type="both",
        description="All-in-one voice and avatar creation. Record once, create personalized videos at scale with your digital twin.",
        rating=4.5,
        starting_price=15,
        turnaround="30-60 minutes",
        features=["Voice + Avatar", "Personalization", "Batch creation", "CRM integration", "Analytics"],
        logo="🪄",
    ),
]

# Index by ID for fast lookup
_PROVIDER_MAP: dict[str, ProviderInfo] = {p.id: p for p in _PROVIDER_CATALOG}


def get_all_providers() -> list[ProviderInfo]:
    """Return all registered providers."""
    return _PROVIDER_CATALOG


def get_provider_by_id(provider_id: str) -> ProviderInfo | None:
    """Look up a provider by ID. Returns None if not found."""
    return _PROVIDER_MAP.get(provider_id)


def get_providers_by_type(provider_type: str) -> list[ProviderInfo]:
    """Filter providers by type (voice / avatar / both)."""
    if provider_type == "all":
        return _PROVIDER_CATALOG
    return [p for p in _PROVIDER_CATALOG if p.provider_type == provider_type]
