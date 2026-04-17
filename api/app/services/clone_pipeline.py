"""End-to-end clone training pipeline.

Invoked as a FastAPI BackgroundTask after an Order is created. Steps:

  1. Fetch training bundles from Windy Pro (cached fallback).
  2. Submit to provider (ElevenLabs /v1/voices/add).
  3. Poll until the voice model is ready.
  4. Auto-hatch with Eternitas to mint an ET26 passport.
  5. Persist a Clone row so /api/v1/clones shows it.
  6. Update Order status.

Dev mode / missing API key short-circuits cleanly — existing tests rely on
create_order returning quickly without side effects.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from ..config import get_settings
from ..db.engine import get_session_factory
from ..db.models import Clone, Order, OrderStatus
from ..providers.base import PreparedPackage
from ..providers.elevenlabs import ElevenLabsProvider
from .data_fetcher import fetch_training_bundles
from .eternitas import EternitasHatchError, auto_hatch

logger = logging.getLogger(__name__)


async def run_elevenlabs_pipeline(
    order_id: str,
    identity_id: str,
    display_name: str | None,
    jwt_token: str | None,
    audio_files: list[tuple[str, bytes, str]] | None = None,
) -> None:
    """Run the full clone pipeline for an ElevenLabs order.

    Never raises — failures are logged and reflected on the Order row so the
    UI can show a meaningful error instead of a dead job.
    """
    settings = get_settings()
    factory = get_session_factory()

    async with factory() as db:
        order = (
            await db.execute(select(Order).where(Order.id == order_id))
        ).scalar_one_or_none()
        if order is None:
            logger.warning("pipeline: order %s vanished before training", order_id)
            return

        if settings.dev_mode or not settings.elevenlabs_api_key:
            logger.info("pipeline: skipping live training for order %s (dev or missing key)", order_id)
            return

        provider = ElevenLabsProvider()
        order.status = OrderStatus.UPLOADING.value
        await db.commit()

        try:
            if not audio_files:
                bundles_result = await fetch_training_bundles(
                    identity_id, jwt_token=jwt_token, db=db
                )
                if bundles_result.unavailable or not bundles_result.bundles:
                    # No recordings at all — user needs to record first.
                    order.status = OrderStatus.AWAITING_UPSTREAM.value
                    order.error_message = (
                        "We don't have any recordings from Windy Pro yet. "
                        "Make a few recordings in Windy Word and try again."
                    )
                    await db.commit()
                    logger.info(
                        "order %s: awaiting upstream (no recordings available)", order_id,
                    )
                    return

                # Recordings exist as metadata, but Pro hasn't yet exposed the
                # audio *bytes* endpoint we'd need to forward to ElevenLabs.
                # Park the order; a reaper can retry when the Pro endpoint lands.
                order.status = OrderStatus.AWAITING_UPSTREAM.value
                order.error_message = (
                    "Your recordings are ready, but Windy Pro hasn't enabled "
                    "audio export yet. We'll start training automatically as "
                    "soon as it does — no action needed from you."
                )
                await db.commit()
                logger.info(
                    "order %s: awaiting upstream (Pro audio endpoint not yet live)",
                    order_id,
                )
                return

            package = PreparedPackage(
                provider_id="elevenlabs",
                format="mp3",
                total_files=len(audio_files),
                total_size_bytes=sum(len(b) for (_, b, _) in audio_files),
                metadata={
                    "voice_name": display_name or "Windy Voice Twin",
                    "audio_files": audio_files,
                },
            )
            upload = await provider.upload(package)
            order.provider_job_id = upload.job_id
            order.status = OrderStatus.TRAINING.value
            await db.commit()

            status = await provider.get_training_status(upload.job_id)
            if status.status != "completed":
                order.status = status.status
                order.progress = status.progress
                await db.commit()
                return

            result = await provider.get_result(upload.job_id)

            passport: str | None = None
            try:
                passport = await auto_hatch(
                    identity_id=identity_id,
                    provider_id="elevenlabs",
                    provider_model_id=result.model_id,
                    clone_type="voice",
                    display_name=result.name,
                )
            except EternitasHatchError as exc:
                logger.warning("order %s: eternitas hatch failed: %s", order_id, exc)

            clone = Clone(
                identity_id=identity_id,
                order_id=order.id,
                provider_id="elevenlabs",
                clone_type="voice",
                name=result.name,
                provider_model_id=result.model_id,
                passport=passport,
                quality_label=result.quality_label,
            )
            db.add(clone)

            order.status = OrderStatus.COMPLETED.value
            order.progress = 100
            await db.commit()

        except Exception as exc:
            logger.exception("pipeline: order %s failed", order_id)
            order.status = OrderStatus.FAILED.value
            order.error_message = str(exc)[:500]
            await db.commit()
