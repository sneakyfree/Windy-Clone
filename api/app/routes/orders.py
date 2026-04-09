"""Order endpoints — /api/v1/orders/*

Create, list, and manage clone training orders.
Backed by SQLAlchemy async DB.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import CurrentUser, get_current_user
from ..db.engine import get_db
from ..db.models import Order, OrderStatus
from ..providers.registry import get_provider_by_id

router = APIRouter()


class CreateOrderRequest(BaseModel):
    provider_id: str
    clone_type: str  # "voice" | "avatar"


@router.post("")
async def create_order(
    request: CreateOrderRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new order — package user data and send to a provider.

    Creates a DB record and will trigger provider upload in Phase 4.
    """
    provider = get_provider_by_id(request.provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider '{request.provider_id}' not found")

    if provider.coming_soon:
        raise HTTPException(status_code=400, detail=f"Provider '{provider.name}' is not yet available")

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
        "estimated_completion": "Pending" if order.status == "pending" else "In progress",
        "error_message": order.error_message,
        "created_at": order.created_at.isoformat() if order.created_at else "",
    }


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
