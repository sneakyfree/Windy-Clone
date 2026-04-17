"""Clone preview endpoints — /api/v1/clones/*

List completed clones, generate previews, download/delete, export soul file.
Backed by SQLAlchemy async DB.
"""

import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import CurrentUser, get_current_user
from ..config import get_settings
from ..db.engine import get_db
from ..db.models import Clone
from ..providers.registry import get_provider_by_id
from ..services.soul_file import build_soul_file
from ..services.trust_client import GatedAction, TrustGateError, enforce_gate

router = APIRouter()


def _verify_service_token(authorization: str | None) -> bool:
    """Return True iff Authorization matches WINDY_SERVICE_TOKEN."""
    expected = get_settings().windy_service_token
    if not expected or not authorization:
        return False
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return False
    return hmac.compare_digest(parts[1], expected)


@router.get("")
async def list_clones(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all completed clones for the current user."""
    result = await db.execute(
        select(Clone)
        .where(Clone.identity_id == user.identity_id)
        .order_by(Clone.created_at.desc())
    )
    clones = result.scalars().all()

    provider_cache: dict[str, str] = {}
    def get_provider_name(pid: str) -> str:
        if pid not in provider_cache:
            p = get_provider_by_id(pid)
            provider_cache[pid] = p.name if p else pid
        return provider_cache[pid]

    return {
        "clones": [
            {
                "id": c.id,
                "provider_id": c.provider_id,
                "provider_name": get_provider_name(c.provider_id),
                "clone_type": c.clone_type,
                "name": c.name,
                "quality_label": c.quality_label,
                "created_at": c.created_at.isoformat() if c.created_at else "",
            }
            for c in clones
        ],
        "total": len(clones),
    }


class PreviewRequest(BaseModel):
    text: str


@router.post("/{clone_id}/preview")
async def generate_preview(
    clone_id: str,
    request: PreviewRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a TTS preview using the clone.

    Will call the provider's preview API when adapters are fully wired.
    """
    result = await db.execute(
        select(Clone).where(Clone.id == clone_id, Clone.identity_id == user.identity_id)
    )
    clone = result.scalar_one_or_none()

    if not clone:
        raise HTTPException(status_code=404, detail="Clone not found")

    # Scaffold until provider.preview() is wired end-to-end. Returning 501
    # instead of a success-shaped placeholder so the frontend can't mistake
    # it for a real preview.
    raise HTTPException(
        status_code=501,
        detail="Preview generation not yet implemented.",
    )


@router.get("/{clone_id}/download")
async def download_clone(
    clone_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download clone model/assets."""
    result = await db.execute(
        select(Clone).where(Clone.id == clone_id, Clone.identity_id == user.identity_id)
    )
    clone = result.scalar_one_or_none()

    if not clone:
        raise HTTPException(status_code=404, detail="Clone not found")

    # See /preview comment — 501 rather than a misleading success shape.
    raise HTTPException(
        status_code=501,
        detail="Clone download not yet implemented. Use /export-soul-file for the signed archive.",
    )


@router.post("/{clone_id}/export-soul-file")
async def export_soul_file(
    clone_id: str,
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Export a soul file (.windysoul) for this clone.

    Auth: the authenticated caller must own the clone, OR the request must
    carry a valid service-token Authorization bearer. Agents exporting a
    soul file that contains human voice/avatar data need TOP_SECRET clearance
    (humans bypass all gates for their own clones).
    """
    is_service = _verify_service_token(authorization)

    result = await db.execute(select(Clone).where(Clone.id == clone_id))
    clone = result.scalar_one_or_none()
    if not clone:
        raise HTTPException(status_code=404, detail="Clone not found")

    if not is_service and clone.identity_id != user.identity_id:
        raise HTTPException(status_code=403, detail="Not the clone owner")

    # ── Agent gate: exporting a human's voice/avatar is TOP_SECRET ─────
    # A human-owned clone is one without a passport (agents have passports
    # on their bot identities). If the clone has no passport, its content
    # is human-derived and needs the highest clearance to export.
    if not is_service and user.is_agent and not clone.passport:
        try:
            await enforce_gate(user, GatedAction.EXPORT_SOUL_FILE_HUMAN)
        except TrustGateError as exc:
            raise HTTPException(status_code=403, detail=str(exc))

    archive = build_soul_file(clone, owner_email=user.email if not is_service else None)
    filename = f"{clone.id}.windysoul"
    return Response(
        content=archive,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/{clone_id}")
async def delete_clone(
    clone_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a clone — removes from DB and optionally from provider."""
    result = await db.execute(
        select(Clone).where(Clone.id == clone_id, Clone.identity_id == user.identity_id)
    )
    clone = result.scalar_one_or_none()

    if not clone:
        raise HTTPException(status_code=404, detail="Clone not found")

    await db.delete(clone)
    await db.commit()

    return {
        "clone_id": clone_id,
        "status": "deleted",
        "message": "Clone deleted successfully.",
    }
