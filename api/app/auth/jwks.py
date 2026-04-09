"""JWKS fetcher — downloads and caches public keys from Windy Pro."""

import time
import httpx
import jwt
from jwt import PyJWKClient

from ..config import get_settings

# Cache JWKS client to avoid re-fetching keys on every request
_jwks_client: PyJWKClient | None = None
_jwks_client_created_at: float = 0
_JWKS_CACHE_TTL = 3600  # Refresh keys every hour


def _get_jwks_client() -> PyJWKClient:
    """Get or create a cached JWKS client."""
    global _jwks_client, _jwks_client_created_at

    now = time.time()
    if _jwks_client is None or (now - _jwks_client_created_at) > _JWKS_CACHE_TTL:
        settings = get_settings()
        _jwks_client = PyJWKClient(settings.windy_pro_jwks_url)
        _jwks_client_created_at = now

    return _jwks_client


def validate_token(token: str) -> dict:
    """
    Validate a JWT using Windy Pro's JWKS endpoint.

    Returns the decoded payload containing at minimum:
        - windy_identity_id: str  (cross-product UUID)
        - sub: str
        - exp: int

    Raises jwt.exceptions.* on failure.
    """
    client = _get_jwks_client()
    signing_key = client.get_signing_key_from_jwt(token)

    payload = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        options={"require": ["exp", "sub"]},
    )

    return payload


def extract_identity_id(payload: dict) -> str:
    """Extract the Windy identity UUID from a decoded JWT payload."""
    # Try windy_identity_id first, fall back to sub
    return payload.get("windy_identity_id", payload.get("sub", ""))
