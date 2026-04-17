"""Tests for P1 #4: EXPORT_SOUL_FILE_HUMAN bypasses the trust cache.

Wave-7 gap analysis: in a multi-task deploy, `trust.changed` only flushes
the cache on the task that receives it. Other replicas keep stale state
for up to `cache_ttl_seconds`. For the highest-stakes gate, we pay one
extra HTTP call to close that window.
"""

import httpx
import pytest

from app.auth.dependencies import CurrentUser
from app.config import get_settings
from app.services import trust_client
from app.services.trust_client import (
    GatedAction,
    TrustGateError,
    TrustLevel,
    enforce_gate,
    reset_cache,
)


def _patch_httpx(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    real = trust_client.httpx.AsyncClient

    def factory(*a, **kw):
        kw["transport"] = transport
        return real(*a, **kw)

    monkeypatch.setattr(trust_client.httpx, "AsyncClient", factory)


def _response(clearance: str, band: str = "exceptional", status: str = "active"):
    return {
        "passport_number": "ET26-BYPASS",
        "status": status,
        "integrity_score": 950 if band == "exceptional" else 200,
        "band": band,
        "clearance_level": clearance,
        "tier_multiplier": 5.0,
        "allowed_actions": ["read", "send"] if status == "active" and band != "critical" else [],
        "denied_actions": [],
        "cache_ttl_seconds": 300,
        "evaluated_at": "2026-04-17T00:00:00+00:00",
    }


@pytest.fixture(autouse=True)
def _fresh():
    reset_cache()


@pytest.fixture
def live_settings(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "eternitas_url", "http://eternitas.test")
    monkeypatch.setattr(s, "eternitas_use_mock", False)
    return s


@pytest.mark.anyio
async def test_submit_clone_order_uses_cache(monkeypatch, live_settings):
    """Non-bypass gates hit Eternitas once, then serve from cache."""
    calls = {"n": 0}

    def handler(r):
        calls["n"] += 1
        return httpx.Response(200, json=_response("top_secret"))

    _patch_httpx(monkeypatch, handler)
    agent = CurrentUser(identity_id="a", passport="ET26-CACHED")

    await enforce_gate(agent, GatedAction.SUBMIT_CLONE_ORDER)
    await enforce_gate(agent, GatedAction.SUBMIT_CLONE_ORDER)
    await enforce_gate(agent, GatedAction.CLONE_HUMAN)  # also non-bypass

    assert calls["n"] == 1, f"expected 1 cached lookup, got {calls['n']}"


@pytest.mark.anyio
async def test_export_soul_file_bypasses_cache(monkeypatch, live_settings):
    """EXPORT_SOUL_FILE_HUMAN re-fetches from Eternitas every call."""
    calls = {"n": 0}

    def handler(r):
        calls["n"] += 1
        return httpx.Response(200, json=_response("top_secret"))

    _patch_httpx(monkeypatch, handler)
    agent = CurrentUser(identity_id="a", passport="ET26-BYPASS")

    await enforce_gate(agent, GatedAction.EXPORT_SOUL_FILE_HUMAN)
    await enforce_gate(agent, GatedAction.EXPORT_SOUL_FILE_HUMAN)
    await enforce_gate(agent, GatedAction.EXPORT_SOUL_FILE_HUMAN)

    assert calls["n"] == 3, f"expected 3 fresh lookups, got {calls['n']}"


@pytest.mark.anyio
async def test_stale_cache_doesnt_let_revoked_passport_export(monkeypatch, live_settings):
    """The scenario the fix exists to prevent: cached TOP_SECRET + live REVOKED."""
    # First call (any non-bypass action) caches the old TOP_SECRET state.
    responses = [_response("top_secret"), _response("top_secret", band="critical", status="revoked")]

    def handler(r):
        return httpx.Response(200, json=responses.pop(0))

    _patch_httpx(monkeypatch, handler)
    agent = CurrentUser(identity_id="a", passport="ET26-FLIPPED")

    # Warm the cache at TOP_SECRET via a non-bypass gate.
    await enforce_gate(agent, GatedAction.SUBMIT_CLONE_ORDER)
    assert trust_client._cache_get("ET26-FLIPPED") is TrustLevel.TOP_SECRET

    # Now Eternitas has flipped the passport to revoked — but cache is stale.
    # A bypass gate call should see the fresh revoked state and deny.
    with pytest.raises(TrustGateError) as exc:
        await enforce_gate(agent, GatedAction.EXPORT_SOUL_FILE_HUMAN)
    assert exc.value.actual is TrustLevel.UNVERIFIED
