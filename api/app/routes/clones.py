"""Clone preview endpoints — /api/v1/clones/*

List completed clones, generate previews, download/delete.
Backed by SQLAlchemy async DB.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import CurrentUser, get_current_user
from ..db.engine import get_db
from ..db.models import Clone
from ..providers.registry import get_provider_by_id

router = APIRouter()


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

    # TODO: Call provider.preview(clone.provider_model_id, request.text)
    return {
        "clone_id": clone_id,
        "text": request.text,
        "status": "preview_generation_scaffolded",
        "message": "Preview generation will be available once provider adapters are fully wired.",
    }


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

    return {
        "clone_id": clone_id,
        "status": "download_scaffolded",
        "message": "Download will be available once provider adapters are fully wired.",
    }


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
