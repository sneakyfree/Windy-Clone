"""Eternitas Trust API consumer (live wire).

Consumer-side implementation of the contract in Eternitas' `docs/trust-api.md`:

    GET {ETERNITAS_URL}/api/v1/trust/{passport}
      → { status, clearance_level, band, integrity_score,
          tier_multiplier, allowed_actions, denied_actions,
          cache_ttl_seconds, evaluated_at, ... }

Clone maps the response to a 5-level clearance ladder and enforces gates
against it. The LOWER-of rule and the `critical` / `suspended` / `revoked`
blockers from the contract collapse to a single invariant: if the live
response does not actively authorise the requested clearance, the caller
is treated as `UNVERIFIED`.

Caching: in-process TTL honoured from the response body (`cache_ttl_seconds`),
fallback to `ETERNITAS_TRUST_CACHE_TTL`. Invalidated on `trust.changed`
webhook delivery so we don't wait out stale state.

Mock switch: `ETERNITAS_USE_MOCK=true` returns TOP_SECRET for every agent
and skips HTTP — useful in CI when Eternitas isn't reachable. Default False.
"""

from __future__ import annotations

import enum
import logging
import time

import httpx

from ..auth.dependencies import CurrentUser
from ..config import get_settings

logger = logging.getLogger(__name__)


class TrustLevel(int, enum.Enum):
    """Ordered clearance ladder. Values are compared — don't renumber."""

    UNVERIFIED = 0
    VERIFIED = 1
    CLEARED = 2
    TOP_SECRET = 3
    ETERNAL = 4


# Map Eternitas `clearance_level` strings to our ladder. `registered` falls
# below any gate we enforce, so we collapse it to UNVERIFIED.
_CLEARANCE_FROM_STRING: dict[str, TrustLevel] = {
    "registered": TrustLevel.UNVERIFIED,
    "verified": TrustLevel.VERIFIED,
    "cleared": TrustLevel.CLEARED,
    "top_secret": TrustLevel.TOP_SECRET,
    "eternal": TrustLevel.ETERNAL,
}

# Band → TrustLevel ceiling. The trust-API doc encodes this as a multiplier
# table; we project those multipliers onto our ladder so the `min()` below
# can be a single comparison. Why these mappings:
#
#   exceptional → ETERNAL    (mult 5.0 ≥ eternal)
#   good        → TOP_SECRET (mult 2.0 ≥ cleared, used by Wave-4 task to allow exports)
#   fair        → CLEARED    (mult 1.0 = verified, allows clone but not soul export)
#   poor        → UNVERIFIED (mult 0.5 — read-only behavior per gating contract)
#   critical    → UNVERIFIED (mult 0.0 — blocks everything)
_BAND_CEILING: dict[str, TrustLevel] = {
    "exceptional": TrustLevel.ETERNAL,
    "good": TrustLevel.TOP_SECRET,
    "fair": TrustLevel.CLEARED,
    "poor": TrustLevel.UNVERIFIED,
    "critical": TrustLevel.UNVERIFIED,
}


class TrustGateError(Exception):
    """Raised when a gate denies an action. Carries structured detail."""

    def __init__(self, required: TrustLevel, actual: TrustLevel, action: str):
        self.required = required
        self.actual = actual
        self.action = action
        super().__init__(
            f"{action} requires clearance {required.name}; passport holder is {actual.name}"
        )


class GatedAction(str, enum.Enum):
    """Sensitive actions agents can attempt. Matrix in agent-trust-gates.md."""

    SUBMIT_CLONE_ORDER = "submit_clone_order"
    CLONE_HUMAN = "clone_human"
    EXPORT_SOUL_FILE_HUMAN = "export_soul_file_human"


_GATE_REQUIREMENTS: dict[GatedAction, TrustLevel] = {
    GatedAction.SUBMIT_CLONE_ORDER: TrustLevel.VERIFIED,
    GatedAction.CLONE_HUMAN: TrustLevel.CLEARED,
    GatedAction.EXPORT_SOUL_FILE_HUMAN: TrustLevel.TOP_SECRET,
}

# Actions that MUST skip the cache and re-fetch from Eternitas. Used for the
# highest-stakes gate where a stale cache window (up to `cache_ttl_seconds`
# across other tasks that didn't receive the `trust.changed` webhook) would
# be an unacceptable privilege-elevation risk.
#
# Cost: one extra round-trip per call to the gated action. Soul-file export
# is a rare, deliberate operation — paying ~50 ms to guarantee the band
# hasn't just flipped to `critical` or the status to `revoked` is worth it.
_CACHE_BYPASS_ACTIONS: frozenset[GatedAction] = frozenset({
    GatedAction.EXPORT_SOUL_FILE_HUMAN,
})


# ─────────────────────────────── cache ────────────────────────────────────

# passport → (expires_at_monotonic, TrustLevel)
_cache: dict[str, tuple[float, TrustLevel]] = {}


def _cache_get(passport: str) -> TrustLevel | None:
    entry = _cache.get(passport)
    if entry is None:
        return None
    expires_at, level = entry
    if time.monotonic() >= expires_at:
        _cache.pop(passport, None)
        return None
    return level


def _cache_set(passport: str, level: TrustLevel, ttl: int) -> None:
    _cache[passport] = (time.monotonic() + max(ttl, 1), level)


def reset_cache() -> None:
    """Test hook — wipe the in-process cache."""
    _cache.clear()


def invalidate(passport: str) -> None:
    """Drop a single passport from the cache (called from trust.changed webhook)."""
    _cache.pop(passport, None)


# ─────────────────────── response → TrustLevel mapping ────────────────────


def _level_from_response(data: dict) -> TrustLevel:
    """Collapse the trust-API response to a single gate-comparable level.

    Implements the LOWER-of rule from eternitas/docs/trust-api.md:

        effective = min(clearance_ceiling, band_ceiling)

    Both ceilings are projected onto our TrustLevel ladder. Hard blockers
    (suspended/revoked status, empty allowed_actions) short-circuit to
    UNVERIFIED before the ceiling math runs.
    """
    if str(data.get("status", "")) != "active":
        return TrustLevel.UNVERIFIED
    if not data.get("allowed_actions"):
        return TrustLevel.UNVERIFIED

    clearance_str = str(data.get("clearance_level", "")).lower()
    band_str = str(data.get("band", "")).lower()

    clearance_ceiling = _CLEARANCE_FROM_STRING.get(clearance_str, TrustLevel.UNVERIFIED)
    band_ceiling = _BAND_CEILING.get(band_str, TrustLevel.UNVERIFIED)

    return TrustLevel(min(clearance_ceiling.value, band_ceiling.value))


# ─────────────────────────── trust lookup ─────────────────────────────────


async def get_agent_trust(passport: str, *, bypass_cache: bool = False) -> TrustLevel:
    """Fetch the current clearance level for an Eternitas passport.

    Cache-first by default. When `bypass_cache=True`, the in-process cache
    is dropped for this passport before the fetch so the request sees
    live Eternitas state — used by sensitive gates where a stale cache is
    unacceptable (see `_CACHE_BYPASS_ACTIONS`).

    On network failure, degrades to UNVERIFIED (fail-closed) — better to
    under-privilege for a few seconds than to silently allow a gated
    action when Eternitas is unreachable.
    """
    settings = get_settings()

    if settings.eternitas_use_mock:
        return TrustLevel.TOP_SECRET

    if bypass_cache:
        invalidate(passport)
    else:
        cached = _cache_get(passport)
        if cached is not None:
            return cached

    url = f"{settings.eternitas_url.rstrip('/')}/api/v1/trust/{passport}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        logger.warning("trust lookup failed for %s: %s", passport, exc)
        return TrustLevel.UNVERIFIED

    level = _level_from_response(data)
    ttl = int(data.get("cache_ttl_seconds", settings.eternitas_trust_cache_ttl))
    _cache_set(passport, level, ttl)
    return level


# ─────────────────────────── gate enforcement ─────────────────────────────


async def enforce_gate(user: CurrentUser, action: GatedAction) -> TrustLevel | None:
    """Raise TrustGateError if an agent fails the gate.

    Returns the agent's actual TrustLevel on success, or None when the
    caller is a human — humans bypass every gate and never hit Eternitas.

    For actions in `_CACHE_BYPASS_ACTIONS`, the trust lookup bypasses the
    in-process cache so a just-flipped band or just-revoked passport is
    honoured even if this replica hasn't received the `trust.changed`
    webhook yet. Today that's EXPORT_SOUL_FILE_HUMAN only.
    """
    if not user.is_agent:
        return None

    required = _GATE_REQUIREMENTS[action]
    bypass = action in _CACHE_BYPASS_ACTIONS
    actual = await get_agent_trust(user.passport, bypass_cache=bypass)  # type: ignore[arg-type]
    if actual.value < required.value:
        raise TrustGateError(required=required, actual=actual, action=action.value)
    return actual


def required_level(action: GatedAction) -> TrustLevel:
    """Public accessor — used in docs and tests to avoid drift."""
    return _GATE_REQUIREMENTS[action]
