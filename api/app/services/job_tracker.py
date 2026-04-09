"""Job tracker — poll provider APIs for training status.

Runs as a background task to update order progress in the database.
"""

import asyncio
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.engine import get_session_factory
from ..db.models import Order, Clone, OrderStatus
from ..providers.registry import get_provider_by_id

# Import provider adapters
from ..providers.elevenlabs import ElevenLabsProvider
from ..providers.heygen import HeyGenProvider
from ..providers.playht import PlayHTProvider
from ..providers.resembleai import ResembleAIProvider


# ── Provider adapter instances ──
_ADAPTERS: dict[str, object] = {
    "elevenlabs": ElevenLabsProvider(),
    "heygen": HeyGenProvider(),
    "playht": PlayHTProvider(),
    "resembleai": ResembleAIProvider(),
}

# ── Poll interval ──
POLL_INTERVAL_SECONDS = 30


async def poll_training_jobs():
    """
    Background task: poll all active training jobs and update status.

    Called periodically to check provider APIs for training progress.
    """
    factory = get_session_factory()
    async with factory() as db:
        # Find all active orders
        result = await db.execute(
            select(Order).where(
                Order.status.in_([
                    OrderStatus.UPLOADING.value,
                    OrderStatus.TRAINING.value,
                ])
            )
        )
        active_orders = result.scalars().all()

        for order in active_orders:
            adapter = _ADAPTERS.get(order.provider_id)
            if not adapter or not order.provider_job_id:
                continue

            try:
                status = await adapter.get_training_status(order.provider_job_id)

                order.progress = status.progress
                order.status = status.status

                if status.status == "completed":
                    order.status = OrderStatus.COMPLETED.value
                    order.progress = 100

                    # Create clone record
                    clone_result = await adapter.get_result(order.provider_job_id)
                    clone = Clone(
                        identity_id=order.identity_id,
                        order_id=order.id,
                        provider_id=order.provider_id,
                        clone_type=order.provider_type,
                        name=clone_result.name,
                        provider_model_id=clone_result.model_id,
                        quality_label=clone_result.quality_label,
                    )
                    db.add(clone)

                elif status.status == "failed":
                    order.status = OrderStatus.FAILED.value
                    order.error_message = status.message

            except Exception as exc:
                print(f"⚠️  Error polling {order.provider_id} job {order.provider_job_id}: {exc}")

        await db.commit()


async def run_job_tracker():
    """Run the job tracker as a continuous background loop."""
    print("🔄 Job tracker started")
    while True:
        try:
            await poll_training_jobs()
        except Exception as exc:
            print(f"⚠️  Job tracker error: {exc}")

        await asyncio.sleep(POLL_INTERVAL_SECONDS)
