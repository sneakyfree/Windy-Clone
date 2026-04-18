"""SQLAlchemy models — orders, clones, preferences.

Windy Clone only stores its OWN data here (orders, training jobs, preferences).
Recording data lives in Windy Pro's account-server.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, Float, Text, DateTime, Boolean, Enum
from sqlalchemy.orm import DeclarativeBase
import enum


class Base(DeclarativeBase):
    pass


class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    UPLOADING = "uploading"
    TRAINING = "training"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    # Pipeline ran but cannot complete until an upstream dependency is live
    # (today: Windy Pro exposing bundle audio bytes). Not a failure — the
    # order will be picked up again when the dependency lands.
    AWAITING_UPSTREAM = "awaiting_upstream"


class ProviderType(str, enum.Enum):
    VOICE = "voice"
    AVATAR = "avatar"
    BOTH = "both"


class Order(Base):
    """A user's order to create a clone via a provider."""
    __tablename__ = "orders"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    identity_id = Column(String, nullable=False, index=True)
    provider_id = Column(String, nullable=False)
    provider_type = Column(String, nullable=False)  # voice / avatar / both
    status = Column(String, nullable=False, default=OrderStatus.PENDING.value)
    progress = Column(Integer, default=0)  # 0-100
    provider_job_id = Column(String, nullable=True)  # External job ID from provider
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Clone(Base):
    """A completed clone (voice model or avatar) from a provider."""
    __tablename__ = "clones"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    identity_id = Column(String, nullable=False, index=True)
    order_id = Column(String, nullable=True)
    provider_id = Column(String, nullable=False)
    clone_type = Column(String, nullable=False)  # voice / avatar
    name = Column(String, nullable=False)
    provider_model_id = Column(String, nullable=True)  # External model ID
    passport = Column(String, nullable=True, index=True)  # Eternitas passport (ET26-XXXX-XXXX)
    quality_label = Column(String, default="Standard")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class CachedRecordingStats(Base):
    """Last-known-good recording stats from Windy Pro.

    Written through on every successful fetch; read when Pro is unreachable
    so the Legacy Dashboard can show stale-but-present data with a banner.
    """
    __tablename__ = "cached_recording_stats"

    identity_id = Column(String, primary_key=True)
    stats_json = Column(Text, nullable=True)
    bundles_json = Column(Text, nullable=True)
    fetched_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class UserPreference(Base):
    """Per-user preferences (default provider, notification settings)."""
    __tablename__ = "user_preferences"

    identity_id = Column(String, primary_key=True)
    default_provider = Column(String, default="elevenlabs")
    email_notifications = Column(Boolean, default=True)
    push_notifications = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
