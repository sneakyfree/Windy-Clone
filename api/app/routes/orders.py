"""Order endpoints — /api/v1/orders/*

Create, list, and manage clone training orders.
Backed by SQLAlchemy async DB.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import CurrentUser, get_current_user
from ..db.engine import get_db
from ..db.models import Order, OrderStatus
from ..providers.registry import get_provider_by_id
from ..services.clone_pipeline import run_elevenlabs_pipeline
from ..services.trust_client import GatedAction, TrustGateError, enforce_gate

router = APIRouter()


class CreateOrderRequest(BaseModel):
    provider_id: str
    clone_type: str  # "voice" | "avatar"
    target_identity_id: str | None = None  # If cloning someone other than self (agents only)


@router.post("")
async def create_order(
    request: CreateOrderRequest,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new order — package user data and send to a provider.

    ElevenLabs orders kick off a real training pipeline in the background:
    upload → poll → Eternitas auto-hatch → Clone row. Other providers are
    tracked at the DB level only until their adapters are wired.
    """
    provider = get_provider_by_id(request.provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider '{request.provider_id}' not found")

    if provider.coming_soon:
        raise HTTPException(status_code=400, detail=f"Provider '{provider.name}' is not yet available")

    # ── Agent trust gates (humans bypass). Order of checks matters: ─────
    # any clone order needs VERIFIED, cloning a HUMAN target needs CLEARED.
    try:
        await enforce_gate(user, GatedAction.SUBMIT_CLONE_ORDER)
        cloning_someone_else = (
            request.target_identity_id is not None
            and request.target_identity_id != user.identity_id
        )
        if cloning_someone_else:
            await enforce_gate(user, GatedAction.CLONE_HUMAN)
    except TrustGateError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    order = Order(
        identity_id=user.identity_id,
        provider_id=request.provider_id,
        provider_type=request.clone_type,
        status=OrderStatus.PENDING.value,
        progress=0,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)

    if request.provider_id == "elevenlabs":
        background_tasks.add_task(
            run_elevenlabs_pipeline,
            order.id,
            user.identity_id,
            user.display_name,
            user.raw_token,
        )

    return {
        "order_id": order.id,
        "provider_id": order.provider_id,
        "clone_type": order.provider_type,
        "status": order.status,
        "message": f"Order created for {provider.name}. Training will begin shortly.",
    }


@router.get("")
async def list_orders(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all orders for the current user."""
    result = await db.execute(
        select(Order)
        .where(Order.identity_id == user.identity_id)
        .order_by(Order.created_at.desc())
    )
    orders = result.scalars().all()

    provider_cache: dict[str, str] = {}
    def get_provider_name(pid: str) -> str:
        if pid not in provider_cache:
            p = get_provider_by_id(pid)
            provider_cache[pid] = p.name if p else pid
        return provider_cache[pid]

    return {
        "orders": [
            {
                "id": o.id,
                "provider_id": o.provider_id,
                "provider_name": get_provider_name(o.provider_id),
                "clone_type": o.provider_type,
                "status": o.status,
                "progress": o.progress,
                "estimated_completion": "Pending" if o.status == "pending" else "In progress",
                "created_at": o.created_at.isoformat() if o.created_at else "",
            }
            for o in orders
        ],
        "total": len(orders),
    }


@router.get("/{order_id}")
async def get_order(
    order_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get order detail with training status."""
    result = await db.execute(
        select(Order).where(Order.id == order_id, Order.identity_id == user.identity_id)
    )
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    provider = get_provider_by_id(order.provider_id)

    return {
        "id": order.id,
        "provider_id": order.provider_id,
        "provider_name": provider.name if provider else order.provider_id,
        "clone_type": order.provider_type,
        "status": order.status,
        "progress": order.progress,
        "estimated_completion": _estimated_completion(order.status),
        "error_message": order.error_message,
        "created_at": order.created_at.isoformat() if order.created_at else "",
    }


def _estimated_completion(status: str) -> str:
    """Human-readable progress hint for the dashboard."""
    if status == OrderStatus.AWAITING_UPSTREAM.value:
        return "Waiting on Windy Pro"
    if status == OrderStatus.PENDING.value:
        return "Pending"
    return "In progress"


@router.post("/{order_id}/cancel")
async def cancel_order(
    order_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a pending or training order."""
    result = await db.execute(
        select(Order).where(Order.id == order_id, Order.identity_id == user.identity_id)
    )
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status in (OrderStatus.COMPLETED.value, OrderStatus.CANCELLED.value):
        raise HTTPException(status_code=400, detail=f"Cannot cancel order with status '{order.status}'")

    order.status = OrderStatus.CANCELLED.value
    await db.commit()

    return {
        "id": order.id,
        "status": "cancelled",
        "message": "Order cancelled successfully.",
    }
