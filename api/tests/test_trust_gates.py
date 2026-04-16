"""Unit tests for the live-wired trust client + the order-submission gate.

Uses httpx.MockTransport against the real `/api/v1/trust/{passport}` response
shape documented in eternitas/docs/trust-api.md. Live HTTP is exercised by
tests/integration/test_trust_live.py when Eternitas is reachable.
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
    get_agent_trust,
    reset_cache,
)


def _patch_httpx(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    real = trust_client.httpx.AsyncClient

    def factory(*a, **kw):
        kw["transport"] = transport
        return real(*a, **kw)

    monkeypatch.setattr(trust_client.httpx, "AsyncClient", factory)


def _trust_response(
    *,
    clearance: str = "verified",
    band: str = "good",
    status: str = "active",
    score: int = 800,
    allowed: list[str] | None = None,
    ttl: int = 300,
):
    """Minimal trust-API payload matching docs/trust-api.md."""
    defaults = {
        "registered": ["read"],
        "verified": ["read", "send"],
        "cleared": ["read", "send", "execute", "dm_bots", "install_packages"],
        "top_secret": [
            "read", "send", "execute", "dm_bots", "install_packages",
            "commit_push", "broadcast", "mention_strangers",
        ],
        "eternal": [
            "read", "send", "execute", "dm_bots", "install_packages",
            "commit_push", "broadcast", "mention_strangers", "bypass_rate_caps",
        ],
    }
    return {
        "passport_number": "ET26-TEST-0000",
        "status": status,
        "integrity_score": score,
        "band": band,
        "clearance_level": clearance,
        "tier_multiplier": 1.5,
        "allowed_actions": allowed if allowed is not None else defaults.get(clearance, []),
        "denied_actions": [],
        "cache_ttl_seconds": ttl,
        "evaluated_at": "2026-04-16T20:11:03+00:00",
    }


@pytest.fixture(autouse=True)
def _fresh_cache():
    reset_cache()


@pytest.fixture
def live_settings(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "eternitas_url", "http://eternitas.test")
    monkeypatch.setattr(s, "eternitas_use_mock", False)
    return s


@pytest.mark.anyio
@pytest.mark.parametrize(
    # Pair each clearance with a band that doesn't lower the ceiling, so this
    # test exercises clearance mapping in isolation. Band-driven LOWER-of is
    # covered by `test_lower_of_band_and_clearance` below.
    "clearance,band,expected",
    [
        ("registered", "good", TrustLevel.UNVERIFIED),
        ("verified", "good", TrustLevel.VERIFIED),
        ("cleared", "good", TrustLevel.CLEARED),
        ("top_secret", "good", TrustLevel.TOP_SECRET),
        ("eternal", "exceptional", TrustLevel.ETERNAL),
    ],
)
async def test_clearance_strings_map_to_ladder(monkeypatch, live_settings, clearance, band, expected):
    _patch_httpx(
        monkeypatch,
        lambda r: httpx.Response(200, json=_trust_response(clearance=clearance, band=band)),
    )
    assert await get_agent_trust("ET26-AAAA-BBBB") is expected


@pytest.mark.anyio
@pytest.mark.parametrize(
    # Clearance always top_secret — band drives the result. Mirrors the live
    # seeded passport set (ET26-TEST-EXCP/GOOD/FAIR/POOR all have clearance
    # top_secret; band differentiates them).
    "band,expected",
    [
        ("exceptional", TrustLevel.TOP_SECRET),  # min(top_secret=3, eternal=4) = top_secret
        ("good", TrustLevel.TOP_SECRET),         # min(top_secret=3, top_secret=3)
        ("fair", TrustLevel.CLEARED),            # min(top_secret=3, cleared=2)
        ("poor", TrustLevel.UNVERIFIED),         # min(top_secret=3, unverified=0)
    ],
)
async def test_lower_of_band_and_clearance(monkeypatch, live_settings, band, expected):
    _patch_httpx(
        monkeypatch,
        lambda r: httpx.Response(200, json=_trust_response(clearance="top_secret", band=band)),
    )
    assert await get_agent_trust(f"ET26-BAND-{band[:4].upper()}") is expected


@pytest.mark.anyio
async def test_critical_band_blocks_any_clearance(monkeypatch, live_settings):
    # top_secret clearance on a critical-band bot → UNVERIFIED (LOWER-of rule).
    _patch_httpx(
        monkeypatch,
        lambda r: httpx.Response(
            200,
            json=_trust_response(clearance="top_secret", band="critical", score=200, allowed=[]),
        ),
    )
    assert await get_agent_trust("ET26-CRIT") is TrustLevel.UNVERIFIED


@pytest.mark.anyio
async def test_suspended_status_blocks_every_action(monkeypatch, live_settings):
    _patch_httpx(
        monkeypatch,
        lambda r: httpx.Response(
            200,
            json=_trust_response(clearance="cleared", band="good", status="suspended", allowed=[]),
        ),
    )
    assert await get_agent_trust("ET26-SUSP") is TrustLevel.UNVERIFIED


@pytest.mark.anyio
async def test_revoked_status_blocks_every_action(monkeypatch, live_settings):
    _patch_httpx(
        monkeypatch,
        lambda r: httpx.Response(
            200,
            json=_trust_response(clearance="top_secret", band="good", status="revoked", allowed=[]),
        ),
    )
    assert await get_agent_trust("ET26-REVK") is TrustLevel.UNVERIFIED


@pytest.mark.anyio
async def test_network_error_fails_closed(monkeypatch, live_settings):
    def handler(request):
        raise httpx.ConnectError("dns fail")

    _patch_httpx(monkeypatch, handler)
    assert await get_agent_trust("ET26-OFFLINE") is TrustLevel.UNVERIFIED


@pytest.mark.anyio
async def test_response_ttl_is_honoured(monkeypatch, live_settings):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(200, json=_trust_response(ttl=60))

    _patch_httpx(monkeypatch, handler)
    await get_agent_trust("ET26-CACHE")
    await get_agent_trust("ET26-CACHE")
    assert calls["n"] == 1  # second call was cache hit


@pytest.mark.anyio
async def test_invalidate_drops_cached_entry(monkeypatch, live_settings):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(200, json=_trust_response())

    _patch_httpx(monkeypatch, handler)
    await get_agent_trust("ET26-INVAL")
    trust_client.invalidate("ET26-INVAL")
    await get_agent_trust("ET26-INVAL")
    assert calls["n"] == 2


@pytest.mark.anyio
async def test_mock_flag_skips_http(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "eternitas_use_mock", True)

    def fail(request):
        raise AssertionError("HTTP call made despite ETERNITAS_USE_MOCK=true")

    _patch_httpx(monkeypatch, fail)
    assert await get_agent_trust("ET26-MOCK") is TrustLevel.TOP_SECRET


@pytest.mark.anyio
async def test_human_bypasses_gates(live_settings):
    human = CurrentUser(identity_id="human-1", email="h@x.com", passport=None)
    assert await enforce_gate(human, GatedAction.EXPORT_SOUL_FILE_HUMAN) is None


@pytest.mark.anyio
async def test_agent_denied_when_below_threshold(monkeypatch, live_settings):
    _patch_httpx(
        monkeypatch,
        lambda r: httpx.Response(200, json=_trust_response(clearance="registered")),
    )
    agent = CurrentUser(identity_id="agent-1", passport="ET26-LOW")
    with pytest.raises(TrustGateError) as exc:
        await enforce_gate(agent, GatedAction.SUBMIT_CLONE_ORDER)
    assert exc.value.required is TrustLevel.VERIFIED
    assert exc.value.actual is TrustLevel.UNVERIFIED


@pytest.mark.anyio
async def test_agent_allowed_at_threshold(monkeypatch, live_settings):
    _patch_httpx(
        monkeypatch,
        lambda r: httpx.Response(200, json=_trust_response(clearance="cleared")),
    )
    agent = CurrentUser(identity_id="agent-2", passport="ET26-MID")
    assert await enforce_gate(agent, GatedAction.CLONE_HUMAN) is TrustLevel.CLEARED


@pytest.mark.anyio
async def test_orders_endpoint_gates_low_trust_agent(monkeypatch, live_settings, client):
    from app.auth import dependencies as deps

    agent = CurrentUser(
        identity_id="agent-deny",
        email="bot@x.com",
        display_name="Bot",
        passport="ET26-DENY",
    )
    monkeypatch.setattr(deps, "_DEV_USER", agent)

    _patch_httpx(
        monkeypatch,
        lambda r: httpx.Response(200, json=_trust_response(clearance="registered")),
    )

    resp = await client.post(
        "/api/v1/orders", json={"provider_id": "elevenlabs", "clone_type": "voice"}
    )
    assert resp.status_code == 403
    assert "VERIFIED" in resp.json()["detail"]
