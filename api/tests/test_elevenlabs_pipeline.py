"""Tests for ElevenLabs adapter and the end-to-end clone pipeline.

Covers:
  * Provider adapter hits the expected ElevenLabs endpoints with correct headers.
  * Pipeline: order → upload → status → Eternitas auto-hatch → Clone row (passport persisted).
  * Pipeline short-circuits cleanly in dev mode (existing orders tests already rely on this).
"""

import asyncio
import uuid
from typing import Any

import httpx
import pytest
from sqlalchemy import select

from app.config import get_settings
from app.db.engine import get_session_factory, init_db
from app.db.models import Clone, Order, OrderStatus
from app.providers import elevenlabs as el_module
from app.providers.base import PreparedPackage
from app.providers.elevenlabs import ElevenLabsProvider
from app.services import clone_pipeline as pipeline_module
from app.services import eternitas as eternitas_module
from app.services.clone_pipeline import run_elevenlabs_pipeline


class _FakeRouter:
    """Dispatches httpx requests to per-URL handlers."""

    def __init__(self):
        self.handlers: dict[tuple[str, str], Any] = {}
        self.calls: list[httpx.Request] = []

    def add(self, method: str, url_suffix: str, handler):
        self.handlers[(method.upper(), url_suffix)] = handler

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        for (method, suffix), handler in self.handlers.items():
            if request.method == method and request.url.path.endswith(suffix):
                return handler(request)
        return httpx.Response(404, json={"error": f"no handler for {request.method} {request.url}"})


def _patch(monkeypatch, module, router: _FakeRouter):
    transport = httpx.MockTransport(router.handle)
    real = module.httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real(*args, **kwargs)

    monkeypatch.setattr(module.httpx, "AsyncClient", factory)


@pytest.fixture
def live_keys(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "dev_mode", False)
    monkeypatch.setattr(settings, "elevenlabs_api_key", "test-xi-key")
    monkeypatch.setattr(settings, "eternitas_url", "https://eternitas.test")
    monkeypatch.setattr(settings, "eternitas_api_key", "test-et-key")
    return settings


@pytest.mark.anyio
async def test_adapter_upload_hits_voices_add(monkeypatch, live_keys):
    router = _FakeRouter()

    def on_add(request: httpx.Request):
        assert request.headers["xi-api-key"] == "test-xi-key"
        assert b'name="Windy Voice Twin"' in request.content or b"Windy Voice Twin" in request.content
        return httpx.Response(200, json={"voice_id": "v-abc-123"})

    router.add("POST", "/v1/voices/add", on_add)
    _patch(monkeypatch, el_module, router)

    package = PreparedPackage(
        provider_id="elevenlabs",
        format="mp3",
        total_files=1,
        total_size_bytes=4,
        metadata={
            "voice_name": "Windy Voice Twin",
            "audio_files": [("sample.mp3", b"\x00\x00\x00\x00", "audio/mpeg")],
        },
    )
    provider = ElevenLabsProvider()
    result = await provider.upload(package)

    assert result.job_id == "v-abc-123"
    assert result.status == "queued"


@pytest.mark.anyio
async def test_adapter_status_maps_fine_tuned(monkeypatch, live_keys):
    router = _FakeRouter()
    router.add(
        "GET",
        "/v1/voices/v-abc-123",
        lambda r: httpx.Response(
            200,
            json={
                "voice_id": "v-abc-123",
                "name": "Grant",
                "fine_tuning": {"state": {"eleven_multilingual_v2": "fine_tuned"}},
            },
        ),
    )
    _patch(monkeypatch, el_module, router)

    provider = ElevenLabsProvider()
    status = await provider.get_training_status("v-abc-123")

    assert status.status == "completed"
    assert status.progress == 100


@pytest.mark.anyio
async def test_adapter_upload_refuses_without_api_key(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "elevenlabs_api_key", "")

    provider = ElevenLabsProvider()
    with pytest.raises(RuntimeError, match="ELEVENLABS_API_KEY"):
        await provider.upload(
            PreparedPackage(
                provider_id="elevenlabs",
                format="mp3",
                total_files=0,
                total_size_bytes=0,
                metadata={"audio_files": [("f.mp3", b"x", "audio/mpeg")]},
            )
        )


@pytest.mark.anyio
async def test_pipeline_happy_path_persists_passport(monkeypatch, live_keys):
    """Full pipeline: mocked ElevenLabs + Eternitas → Clone row has ET26 passport."""
    await init_db()
    factory = get_session_factory()
    identity_id = f"pipe-ok-{uuid.uuid4().hex[:8]}"

    async with factory() as db:
        order = Order(
            identity_id=identity_id,
            provider_id="elevenlabs",
            provider_type="voice",
            status=OrderStatus.PENDING.value,
            progress=0,
        )
        db.add(order)
        await db.commit()
        await db.refresh(order)
        order_id = order.id

    router = _FakeRouter()
    router.add("POST", "/v1/voices/add", lambda r: httpx.Response(200, json={"voice_id": "v-ok"}))
    router.add(
        "GET",
        "/v1/voices/v-ok",
        lambda r: httpx.Response(
            200,
            json={
                "voice_id": "v-ok",
                "name": "Grant's Voice",
                "fine_tuning": {"state": {"eleven_multilingual_v2": "fine_tuned"}},
            },
        ),
    )

    def on_hatch(request: httpx.Request):
        assert request.headers["authorization"] == "Bearer test-et-key"
        return httpx.Response(200, json={"passport": "ET26-7F3A-9B21"})
    router.add("POST", "/api/v1/bots/auto-hatch", on_hatch)

    _patch(monkeypatch, el_module, router)
    _patch(monkeypatch, eternitas_module, router)

    await run_elevenlabs_pipeline(
        order_id=order_id,
        identity_id=identity_id,
        display_name="Grant",
        jwt_token="t",
        audio_files=[("grant.mp3", b"\x00" * 8, "audio/mpeg")],
    )

    async with factory() as db:
        order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one()
        assert order.status == OrderStatus.COMPLETED.value
        assert order.provider_job_id == "v-ok"

        clone = (
            await db.execute(select(Clone).where(Clone.identity_id == identity_id))
        ).scalar_one()
        assert clone.passport == "ET26-7F3A-9B21"
        assert clone.provider_model_id == "v-ok"


@pytest.mark.anyio
async def test_pipeline_eternitas_failure_still_creates_clone(monkeypatch, live_keys):
    """If Eternitas is unreachable, clone is still persisted (passport=None)."""
    await init_db()
    factory = get_session_factory()
    identity_id = f"pipe-nohatch-{uuid.uuid4().hex[:8]}"

    async with factory() as db:
        order = Order(
            identity_id=identity_id,
            provider_id="elevenlabs",
            provider_type="voice",
            status=OrderStatus.PENDING.value,
            progress=0,
        )
        db.add(order)
        await db.commit()
        await db.refresh(order)
        order_id = order.id

    router = _FakeRouter()
    router.add("POST", "/v1/voices/add", lambda r: httpx.Response(200, json={"voice_id": "v-nohatch"}))
    router.add(
        "GET",
        "/v1/voices/v-nohatch",
        lambda r: httpx.Response(
            200,
            json={
                "voice_id": "v-nohatch",
                "name": "Voice",
                "fine_tuning": {"state": {"eleven_multilingual_v2": "fine_tuned"}},
            },
        ),
    )
    router.add("POST", "/api/v1/bots/auto-hatch", lambda r: httpx.Response(503))

    _patch(monkeypatch, el_module, router)

    await run_elevenlabs_pipeline(
        order_id=order_id,
        identity_id=identity_id,
        display_name="Voice",
        jwt_token="t",
        audio_files=[("x.mp3", b"\x00" * 4, "audio/mpeg")],
    )

    async with factory() as db:
        order = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one()
        assert order.status == OrderStatus.COMPLETED.value

        clone = (
            await db.execute(select(Clone).where(Clone.identity_id == identity_id))
        ).scalar_one()
        assert clone.passport is None
        assert clone.provider_model_id == "v-nohatch"


@pytest.mark.anyio
async def test_pipeline_dev_mode_marks_awaiting_upstream(client):
    """Wave-12 M-1 fix: the dev-mode short-circuit must update the order
    row so the UI can render a banner — not leave it silently `pending`.
    """
    resp = await client.post(
        "/api/v1/orders", json={"provider_id": "elevenlabs", "clone_type": "voice"}
    )
    assert resp.status_code == 200
    order_id = resp.json()["order_id"]

    # Pipeline runs as a BackgroundTask; give it a moment to commit the
    # AWAITING_UPSTREAM update before we read.
    factory = get_session_factory()
    final_status = None
    for _ in range(50):
        async with factory() as db:
            order = (
                await db.execute(select(Order).where(Order.id == order_id))
            ).scalar_one()
            final_status = order.status
            error_message = order.error_message
        if final_status == OrderStatus.AWAITING_UPSTREAM.value:
            break
        await asyncio.sleep(0.05)

    assert final_status == OrderStatus.AWAITING_UPSTREAM.value, (
        f"expected AWAITING_UPSTREAM after dev-mode short-circuit, got {final_status}"
    )
    assert error_message
    assert "dev mode" in error_message.lower()
