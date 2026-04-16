"""Live integration tests against Eternitas at ETERNITAS_LIVE_URL.

Auto-skipped when ETERNITAS_LIVE_URL is unset or the host doesn't answer
/health. With a live Eternitas seeded with ET26-TEST-{EXCP,GOOD,FAIR,POOR,REVD}:

    ETERNITAS_LIVE_URL=http://localhost:8500 \
    pytest api/tests/integration/test_trust_live.py -v

These tests make REAL HTTP calls against /api/v1/trust/{passport}. Their job
is to catch contract drift the unit tests can't see — response shape, band
semantics, status handling, and the LOWER-of rule end-to-end.
"""

from __future__ import annotations

import os

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
    invalidate,
    reset_cache,
)

LIVE_URL = os.getenv("ETERNITAS_LIVE_URL", "").rstrip("/")

# Seeded passports — defaults match the Eternitas dev fixture set. Override
# via env for staging or alternate seed packs.
PASSPORT_EXCP = os.getenv("WINDY_CLONE_LIVE_PASSPORT_EXCP", "ET26-TEST-EXCP")
PASSPORT_GOOD = os.getenv("WINDY_CLONE_LIVE_PASSPORT_GOOD", "ET26-TEST-GOOD")
PASSPORT_FAIR = os.getenv("WINDY_CLONE_LIVE_PASSPORT_FAIR", "ET26-TEST-FAIR")
PASSPORT_POOR = os.getenv("WINDY_CLONE_LIVE_PASSPORT_POOR", "ET26-TEST-POOR")
PASSPORT_REVD = os.getenv("WINDY_CLONE_LIVE_PASSPORT_REVD", "ET26-TEST-REVD")


def _live_reachable() -> bool:
    if not LIVE_URL:
        return False
    try:
        r = httpx.get(f"{LIVE_URL}/health", timeout=2.0)
        return r.status_code == 200
    except httpx.HTTPError:
        return False


pytestmark = pytest.mark.skipif(
    not _live_reachable(),
    reason="ETERNITAS_LIVE_URL unset or unreachable — skipping live suite",
)


@pytest.fixture(autouse=True)
def _live_settings(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "eternitas_url", LIVE_URL)
    monkeypatch.setattr(s, "eternitas_use_mock", False)
    reset_cache()


def _agent(passport: str, tag: str) -> CurrentUser:
    return CurrentUser(
        identity_id=f"agent-{tag}",
        email=f"{tag}@bots.test",
        display_name=tag,
        passport=passport,
    )


# ─────────────────────── Per-band gate behaviour ──────────────────────────


@pytest.mark.anyio
async def test_exceptional_passes_every_gate():
    """EXCP — full clone + soul file export allowed."""
    agent = _agent(PASSPORT_EXCP, "excp")
    assert await enforce_gate(agent, GatedAction.SUBMIT_CLONE_ORDER) is not None
    assert await enforce_gate(agent, GatedAction.CLONE_HUMAN) is not None
    assert await enforce_gate(agent, GatedAction.EXPORT_SOUL_FILE_HUMAN) is not None


@pytest.mark.anyio
async def test_good_passes_every_gate():
    """GOOD — full clone + soul file export allowed."""
    agent = _agent(PASSPORT_GOOD, "good")
    assert await enforce_gate(agent, GatedAction.SUBMIT_CLONE_ORDER) is not None
    assert await enforce_gate(agent, GatedAction.CLONE_HUMAN) is not None
    assert await enforce_gate(agent, GatedAction.EXPORT_SOUL_FILE_HUMAN) is not None


@pytest.mark.anyio
async def test_fair_clones_but_blocks_soul_export():
    """FAIR — clone allowed, soul file export of human content blocked."""
    agent = _agent(PASSPORT_FAIR, "fair")
    assert await enforce_gate(agent, GatedAction.SUBMIT_CLONE_ORDER) is not None
    assert await enforce_gate(agent, GatedAction.CLONE_HUMAN) is not None

    with pytest.raises(TrustGateError) as exc:
        await enforce_gate(agent, GatedAction.EXPORT_SOUL_FILE_HUMAN)
    assert exc.value.required is TrustLevel.TOP_SECRET
    assert exc.value.actual is TrustLevel.CLEARED


@pytest.mark.anyio
async def test_poor_is_read_only():
    """POOR — read-only; cannot even submit a clone order."""
    agent = _agent(PASSPORT_POOR, "poor")

    for action in (
        GatedAction.SUBMIT_CLONE_ORDER,
        GatedAction.CLONE_HUMAN,
        GatedAction.EXPORT_SOUL_FILE_HUMAN,
    ):
        with pytest.raises(TrustGateError):
            await enforce_gate(agent, action)


@pytest.mark.anyio
async def test_revoked_is_blocked_entirely():
    """REVD — revoked status, every gate denies."""
    agent = _agent(PASSPORT_REVD, "revd")

    for action in (
        GatedAction.SUBMIT_CLONE_ORDER,
        GatedAction.CLONE_HUMAN,
        GatedAction.EXPORT_SOUL_FILE_HUMAN,
    ):
        with pytest.raises(TrustGateError) as exc:
            await enforce_gate(agent, action)
        assert exc.value.actual is TrustLevel.UNVERIFIED


# ─────────────────────── Contract & cache behaviour ───────────────────────


@pytest.mark.anyio
async def test_response_carries_v1_contract_fields():
    """Drift canary — assert every field documented in trust-api.md is present."""
    async with httpx.AsyncClient(timeout=5.0) as c:
        resp = await c.get(f"{LIVE_URL}/api/v1/trust/{PASSPORT_EXCP}")
    assert resp.status_code == 200
    data = resp.json()
    for field in (
        "passport_number",
        "status",
        "integrity_score",
        "dimensions",
        "band",
        "clearance_level",
        "tier_multiplier",
        "allowed_actions",
        "denied_actions",
        "cache_ttl_seconds",
        "evaluated_at",
    ):
        assert field in data, f"contract drift: response missing `{field}`"


@pytest.mark.anyio
async def test_human_caller_skips_trust_call_entirely(monkeypatch):
    """Humans bypass enforce_gate without any HTTP call."""
    real_client = trust_client.httpx.AsyncClient

    def fail(request):
        raise AssertionError("unexpected HTTP call for human caller")

    def factory(*a, **kw):
        kw["transport"] = httpx.MockTransport(fail)
        return real_client(*a, **kw)

    monkeypatch.setattr(trust_client.httpx, "AsyncClient", factory)
    human = CurrentUser(identity_id="human-live", email="h@x.com", passport=None)
    assert await enforce_gate(human, GatedAction.EXPORT_SOUL_FILE_HUMAN) is None


@pytest.mark.anyio
async def test_invalidate_clears_local_cache():
    """trust.changed-style invalidate() drops the entry mid-TTL."""
    await get_agent_trust(PASSPORT_EXCP)
    assert trust_client._cache_get(PASSPORT_EXCP) is not None
    invalidate(PASSPORT_EXCP)
    assert trust_client._cache_get(PASSPORT_EXCP) is None
