"""Eternitas auto-hatch client.

When a clone finishes training, we register it with Eternitas so the trained
voice becomes a first-class verified identity (ET26-XXXX-XXXX passport).
The returned passport is persisted on the Clone DB row so /my-clones can
surface it and downstream services (Mail, Fly) can verify the bot.
"""

from __future__ import annotations

import logging

import httpx

from ..config import get_settings

logger = logging.getLogger(__name__)


class EternitasHatchError(RuntimeError):
    """Raised when Eternitas auto-hatch cannot assign a passport."""


async def auto_hatch(
    *,
    identity_id: str,
    provider_id: str,
    provider_model_id: str,
    clone_type: str,
    display_name: str,
) -> str:
    """POST {ETERNITAS_URL}/api/v1/bots/auto-hatch.

    Returns the assigned passport (format: ET26-XXXX-XXXX).
    Raises EternitasHatchError on any failure — caller decides whether to
    proceed with a passport-less clone or mark the order failed.
    """
    settings = get_settings()

    headers = {"Content-Type": "application/json"}
    if settings.eternitas_api_key:
        headers["Authorization"] = f"Bearer {settings.eternitas_api_key}"

    payload = {
        "owner_identity_id": identity_id,
        "bot_name": display_name,
        "bot_type": f"{clone_type}_clone",
        "provider": provider_id,
        "provider_model_id": provider_model_id,
        "source_product": "windy-clone",
    }

    url = f"{settings.eternitas_url.rstrip('/')}/api/v1/bots/auto-hatch"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        logger.warning("eternitas auto-hatch failed for %s: %s", identity_id, exc)
        raise EternitasHatchError(str(exc)) from exc

    passport = data.get("passport") or data.get("passport_id")
    if not passport:
        raise EternitasHatchError("response missing passport field")
    return passport
