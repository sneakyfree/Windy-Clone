"""Tests for the Wave-7 housekeeping bundle (P2 + P3 items).

Covers:
  * /preview and /download return 501 instead of success-shaped placeholders.
  * Dead-code services (job_tracker, packager) are gone.
"""

import uuid

import pytest
from sqlalchemy import select

from app.db.engine import get_session_factory
from app.db.models import Clone


@pytest.mark.anyio
async def test_preview_returns_501(client):
    factory = get_session_factory()
    clone_id = f"prev-{uuid.uuid4().hex[:8]}"
    async with factory() as db:
        db.add(Clone(
            id=clone_id, identity_id="dev-mock-user-001",
            provider_id="elevenlabs", clone_type="voice",
            name="T", provider_model_id="m", passport=None,
            quality_label="Studio",
        ))
        await db.commit()

    resp = await client.post(
        f"/api/v1/clones/{clone_id}/preview", json={"text": "hello"}
    )
    assert resp.status_code == 501
    assert "not yet implemented" in resp.json()["detail"].lower()


@pytest.mark.anyio
async def test_download_returns_501(client):
    factory = get_session_factory()
    clone_id = f"dl-{uuid.uuid4().hex[:8]}"
    async with factory() as db:
        db.add(Clone(
            id=clone_id, identity_id="dev-mock-user-001",
            provider_id="elevenlabs", clone_type="voice",
            name="T", provider_model_id="m", passport=None,
            quality_label="Studio",
        ))
        await db.commit()

    resp = await client.get(f"/api/v1/clones/{clone_id}/download")
    assert resp.status_code == 501
    # Points users at the actually-working export endpoint.
    assert "export-soul-file" in resp.json()["detail"]


def test_dead_code_services_deleted():
    """job_tracker and packager were 0% covered and never imported. Gone."""
    import importlib
    for mod in ("app.services.job_tracker", "app.services.packager"):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(mod)
