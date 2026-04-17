"""Tests for soul-file signing-key resolution order.

Covers P0 #7: env-var source wins over file, auto-generation refused in prod.
"""

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.auth import signing
from app.auth.signing import MissingSigningKey
from app.config import get_settings


def _fresh_pem() -> str:
    k = ec.generate_private_key(ec.SECP256R1())
    return k.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    """Isolate signing-key resolution for each test."""
    s = get_settings()
    monkeypatch.setattr(s, "soul_signing_key_path", str(tmp_path / "soul_key.pem"))
    monkeypatch.setattr(s, "soul_signing_key_pem", "")
    signing.reset_cache()
    yield


def test_env_pem_wins_over_file(monkeypatch):
    """When SOUL_SIGNING_KEY_PEM is set, it's used even if the file exists."""
    s = get_settings()
    pem_env = _fresh_pem()
    pem_file = _fresh_pem()

    # Write a different key to disk.
    from pathlib import Path
    Path(s.soul_signing_key_path).write_text(pem_file)

    monkeypatch.setattr(s, "soul_signing_key_pem", pem_env)

    priv, fp = signing.get_signing_key()
    env_priv = serialization.load_pem_private_key(pem_env.encode(), password=None)
    # Compare the public keys (same private → same public DER).
    assert priv.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ) == env_priv.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def test_file_used_when_env_empty():
    """When env is empty, an existing PEM file is loaded."""
    s = get_settings()
    pem_file = _fresh_pem()
    from pathlib import Path
    Path(s.soul_signing_key_path).write_text(pem_file)

    priv, _ = signing.get_signing_key()
    file_priv = serialization.load_pem_private_key(pem_file.encode(), password=None)
    assert priv.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ) == file_priv.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def test_autogenerate_in_dev_mode_only():
    """With no env and no file, dev_mode=True generates and persists a key."""
    s = get_settings()
    s.dev_mode = True  # conftest autouse already sets this, but make it explicit

    priv, fp = signing.get_signing_key()
    assert priv is not None
    # And it was persisted.
    from pathlib import Path
    assert Path(s.soul_signing_key_path).exists()


def test_autogenerate_refused_in_prod(monkeypatch):
    """With no env, no file, and dev_mode=False, get_signing_key raises."""
    s = get_settings()
    monkeypatch.setattr(s, "dev_mode", False)

    with pytest.raises(MissingSigningKey, match="SOUL_SIGNING_KEY_PEM"):
        signing.get_signing_key()


def test_env_pem_used_in_prod(monkeypatch):
    """Prod with an inline PEM env var loads successfully."""
    s = get_settings()
    monkeypatch.setattr(s, "dev_mode", False)
    monkeypatch.setattr(s, "soul_signing_key_pem", _fresh_pem())

    priv, fp = signing.get_signing_key()
    assert priv is not None
    assert len(fp) == 64  # sha256 hex
