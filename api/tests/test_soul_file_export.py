"""Tests for POST /api/v1/clones/{clone_id}/export-soul-file + the builder."""

import base64
import io
import json
import uuid
import zipfile

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from sqlalchemy import select

from app.auth import dependencies as auth_deps
from app.auth import signing
from app.auth.dependencies import CurrentUser
from app.config import get_settings
from app.db.engine import get_session_factory
from app.db.models import Clone
from app.services import trust_client
from app.services.soul_file import SPEC_VERSION, build_soul_file


@pytest.fixture(autouse=True)
def _fresh_signing(tmp_path, monkeypatch):
    """Give each test a fresh signing key on disk so runs don't bleed keys."""
    settings = get_settings()
    monkeypatch.setattr(settings, "soul_signing_key_path", str(tmp_path / "soul_key.pem"))
    signing.reset_cache()
    trust_client.reset_cache()


def _make_clone(*, passport: str | None, identity_id: str) -> Clone:
    return Clone(
        id=f"clone-{uuid.uuid4().hex[:8]}",
        identity_id=identity_id,
        order_id=None,
        provider_id="elevenlabs",
        clone_type="voice",
        name="Grant's Voice",
        provider_model_id="el-voice-xyz",
        passport=passport,
        quality_label="Studio Quality",
    )


def test_build_soul_file_structure_and_signature():
    clone = _make_clone(passport="ET26-ABCD-1234", identity_id="id-1")
    data = build_soul_file(clone, owner_email="grant@x.com")

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = set(zf.namelist())
        assert {
            "manifest.json",
            "voice/voice_model.json",
            "voice/sample.wav",
            "transcripts/transcripts.ndjson",
            "birth_certificate.pdf",
            "signature.json",
        }.issubset(names)
        assert "avatar/" not in "\n".join(names)  # voice-only clone → no avatar/

        manifest = json.loads(zf.read("manifest.json"))
        assert manifest["spec_version"] == SPEC_VERSION
        assert manifest["passport"] == "ET26-ABCD-1234"
        assert manifest["signing_key"]["alg"] == "ES256"
        assert manifest["content_summary"]["is_agent"] is True

        sig = json.loads(zf.read("signature.json"))
        assert sig["alg"] == "ES256"
        assert sig["signed_object"] == "manifest.json"
        assert sig["fingerprint_sha256"] == manifest["signing_key"]["fingerprint_sha256"]

        # Verify the ES256 signature with the embedded public key
        pub = serialization.load_pem_public_key(sig["public_key_pem"].encode())
        raw_sig = base64.b64decode(sig["signature_b64"])
        assert len(raw_sig) == 64
        r = int.from_bytes(raw_sig[:32], "big")
        s = int.from_bytes(raw_sig[32:], "big")
        der = encode_dss_signature(r, s)
        pub.verify(der, zf.read("manifest.json"), ec.ECDSA(hashes.SHA256()))  # raises on bad sig


def test_soul_file_omits_birth_certificate_for_human_clone():
    clone = _make_clone(passport=None, identity_id="id-2")
    data = build_soul_file(clone, owner_email="grant@x.com")
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = zf.namelist()
        assert "birth_certificate.pdf" not in names
        assert json.loads(zf.read("manifest.json"))["content_summary"]["is_agent"] is False


@pytest.mark.anyio
async def test_export_route_owner_downloads_zip(client, monkeypatch):
    """Default dev user owns the clone → 200 with a ZIP payload."""
    factory = get_session_factory()
    async with factory() as db:
        clone = _make_clone(passport="ET26-AAAA-BBBB", identity_id="dev-mock-user-001")
        db.add(clone)
        await db.commit()
        clone_id = clone.id

    resp = await client.post(f"/api/v1/clones/{clone_id}/export-soul-file")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    assert resp.headers["content-disposition"].startswith("attachment;")
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        assert "manifest.json" in zf.namelist()
        assert "signature.json" in zf.namelist()


@pytest.mark.anyio
async def test_export_route_rejects_non_owner(client, monkeypatch):
    """A different user gets 403."""
    factory = get_session_factory()
    async with factory() as db:
        clone = _make_clone(passport=None, identity_id="other-human")
        db.add(clone)
        await db.commit()
        clone_id = clone.id

    resp = await client.post(f"/api/v1/clones/{clone_id}/export-soul-file")
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_export_route_accepts_service_token(client, monkeypatch):
    """A cross-service caller with WINDY_SERVICE_TOKEN can export any clone."""
    settings = get_settings()
    monkeypatch.setattr(settings, "windy_service_token", "svc-secret")

    factory = get_session_factory()
    async with factory() as db:
        clone = _make_clone(passport=None, identity_id="someone-else")
        db.add(clone)
        await db.commit()
        clone_id = clone.id

    resp = await client.post(
        f"/api/v1/clones/{clone_id}/export-soul-file",
        headers={"Authorization": "Bearer svc-secret"},
    )
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_export_route_top_secret_gate_for_agent_on_human_clone(client, monkeypatch):
    """Agent (passport set) exporting a clone with NO passport = human voice → TOP_SECRET."""
    agent = CurrentUser(
        identity_id="agent-x",
        email="bot@x.com",
        display_name="Bot",
        passport="ET26-MID",
    )
    monkeypatch.setattr(auth_deps, "_DEV_USER", agent)

    # Patch trust_client.httpx so the gate sees CLEARED (below TOP_SECRET).
    transport = httpx.MockTransport(
        lambda r: httpx.Response(
            200,
            json={
                "passport_number": "ET26-MID",
                "status": "active",
                "integrity_score": 800,
                "band": "good",
                "clearance_level": "cleared",
                "tier_multiplier": 1.5,
                "allowed_actions": ["read", "send", "execute", "dm_bots", "install_packages"],
                "denied_actions": [],
                "cache_ttl_seconds": 300,
                "evaluated_at": "2026-04-16T20:11:03+00:00",
            },
        )
    )
    real = trust_client.httpx.AsyncClient
    monkeypatch.setattr(
        trust_client.httpx,
        "AsyncClient",
        lambda *a, **kw: real(*a, **{**kw, "transport": transport}),
    )

    factory = get_session_factory()
    async with factory() as db:
        # Human-derived clone (no passport), and the agent happens to own it
        # (unusual but lets us reach the gate without hitting the owner check).
        clone = _make_clone(passport=None, identity_id="agent-x")
        db.add(clone)
        await db.commit()
        clone_id = clone.id

    resp = await client.post(f"/api/v1/clones/{clone_id}/export-soul-file")
    assert resp.status_code == 403
    assert "TOP_SECRET" in resp.json()["detail"]
