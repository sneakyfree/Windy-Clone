"""Reaper for orders orphaned by a task restart.

Background-task pipelines run inside the API process. A Fargate replacement,
SIGKILL, or OOM loses any in-flight pipeline — the order row stays pinned in
UPLOADING or TRAINING with no code running on it.

`reap_orphaned_orders` finds those rows on boot (or on a scheduled cron tick)
and flips them back to PENDING so the next create_order-triggered pipeline,
or a dedicated re-enqueue job, can pick them up. Running it on startup is
safe: the API hasn't begun accepting requests yet, so no other code is
writing to Order.status during the sweep.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from ..db.engine import get_session_factory
from ..db.models import Order, OrderStatus

logger = logging.getLogger(__name__)

# Treat these two as "in flight" — neither is a terminal state, and both are
# only reachable from an actively-running pipeline. If we see one older than
# `max_age_minutes`, that pipeline died.
_IN_FLIGHT_STATUSES = (OrderStatus.UPLOADING.value, OrderStatus.TRAINING.value)


async def reap_orphaned_orders(
    max_age_minutes: int = 30,
    *,
    reason: str = "pipeline task replaced — retrying",
) -> list[str]:
    """Flip orphaned in-flight orders back to PENDING.

    Args:
      max_age_minutes: an order stuck in UPLOADING/TRAINING this long is
        considered orphaned. ElevenLabs instant-clone completes in seconds;
        the professional tier in under 20 min. 30 min is generous.
      reason: written to Order.error_message so operators can trace why a
        particular order was retried.

    Returns the list of reaped order IDs (useful for tests + metrics).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
    factory = get_session_factory()
    reaped: list[str] = []

    async with factory() as db:
        result = await db.execute(
            select(Order).where(
                Order.status.in_(_IN_FLIGHT_STATUSES),
                Order.updated_at < cutoff,
            )
        )
        stale = result.scalars().all()
        for order in stale:
            logger.warning(
                "reaper: order %s stuck in %s since %s — flipping to PENDING",
                order.id, order.status, order.updated_at,
            )
            order.status = OrderStatus.PENDING.value
            order.error_message = reason
            order.progress = 0
            reaped.append(order.id)

        if reaped:
            await db.commit()

    if reaped:
        logger.info("reaper: flipped %d orphaned order(s) back to PENDING", len(reaped))
    return reaped
