"""Tests for optional JWT audience/issuer verification (P1 #2)."""

import datetime

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.auth import jwks as jwks_mod
from app.config import get_settings


def _mint_rsa_keypair():
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub = priv.public_key()
    return priv_pem, pub


def _mint_token(priv_pem: bytes, *, aud: str | None = None, iss: str | None = None) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    claims = {
        "sub": "user-123",
        "windy_identity_id": "user-123",
        "exp": int((now + datetime.timedelta(hours=1)).timestamp()),
    }
    if aud is not None:
        claims["aud"] = aud
    if iss is not None:
        claims["iss"] = iss
    return pyjwt.encode(claims, priv_pem, algorithm="RS256")


@pytest.fixture
def patched_jwks(monkeypatch):
    """Replace the JWKS client with one that serves a known pubkey for any token."""
    priv_pem, pub = _mint_rsa_keypair()

    class _FakeSigningKey:
        def __init__(self, key): self.key = key

    class _FakeClient:
        def get_signing_key_from_jwt(self, token):
            return _FakeSigningKey(pub)

    monkeypatch.setattr(jwks_mod, "_get_jwks_client", lambda: _FakeClient())
    return priv_pem


@pytest.fixture(autouse=True)
def _clear_aud_iss(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "jwt_audience", "")
    monkeypatch.setattr(s, "jwt_issuer", "")
    yield


def test_permissive_mode_accepts_token_without_aud(patched_jwks):
    """Default (empty JWT_AUDIENCE) — backward compat, no aud required."""
    token = _mint_token(patched_jwks)
    payload = jwks_mod.validate_token(token)
    assert payload["sub"] == "user-123"


def test_strict_audience_rejects_missing_aud(patched_jwks, monkeypatch):
    monkeypatch.setattr(get_settings(), "jwt_audience", "windy-clone")
    token = _mint_token(patched_jwks)  # no aud claim
    with pytest.raises(pyjwt.exceptions.MissingRequiredClaimError):
        jwks_mod.validate_token(token)


def test_strict_audience_rejects_wrong_aud(patched_jwks, monkeypatch):
    monkeypatch.setattr(get_settings(), "jwt_audience", "windy-clone")
    token = _mint_token(patched_jwks, aud="windy-mail")
    with pytest.raises(pyjwt.exceptions.InvalidAudienceError):
        jwks_mod.validate_token(token)


def test_strict_audience_accepts_matching_aud(patched_jwks, monkeypatch):
    monkeypatch.setattr(get_settings(), "jwt_audience", "windy-clone")
    token = _mint_token(patched_jwks, aud="windy-clone")
    payload = jwks_mod.validate_token(token)
    assert payload["aud"] == "windy-clone"


def test_strict_issuer_rejects_wrong_iss(patched_jwks, monkeypatch):
    monkeypatch.setattr(get_settings(), "jwt_issuer", "https://auth.windy.example")
    token = _mint_token(patched_jwks, iss="https://evil.example")
    with pytest.raises(pyjwt.exceptions.InvalidIssuerError):
        jwks_mod.validate_token(token)


def test_strict_issuer_accepts_matching_iss(patched_jwks, monkeypatch):
    monkeypatch.setattr(get_settings(), "jwt_issuer", "https://auth.windy.example")
    token = _mint_token(patched_jwks, iss="https://auth.windy.example")
    payload = jwks_mod.validate_token(token)
    assert payload["iss"] == "https://auth.windy.example"


def test_both_aud_and_iss_enforced_together(patched_jwks, monkeypatch):
    monkeypatch.setattr(get_settings(), "jwt_audience", "windy-clone")
    monkeypatch.setattr(get_settings(), "jwt_issuer", "https://auth.windy.example")
    token = _mint_token(
        patched_jwks, aud="windy-clone", iss="https://auth.windy.example"
    )
    payload = jwks_mod.validate_token(token)
    assert payload["aud"] == "windy-clone"
    assert payload["iss"] == "https://auth.windy.example"
