"""ES256 signing key management for soul-file exports.

Clone issues a single long-lived P-256 keypair stored as PEM on disk. First
use generates the key; subsequent calls load and cache it. The public-key
fingerprint is the SHA-256 of the DER-encoded SubjectPublicKeyInfo, hex.
"""

from __future__ import annotations

import hashlib
import os
import threading
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

from ..config import get_settings

_lock = threading.Lock()
_cached: tuple[ec.EllipticCurvePrivateKey, str] | None = None


def _load_or_create() -> tuple[ec.EllipticCurvePrivateKey, str]:
    """Load the signing key from disk, generating it on first use.

    Returns (private_key, public_fingerprint_hex).
    """
    path = Path(get_settings().soul_signing_key_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        pem = path.read_bytes()
        priv = serialization.load_pem_private_key(pem, password=None)
        if not isinstance(priv, ec.EllipticCurvePrivateKey):
            raise RuntimeError(f"{path} is not an EC private key")
    else:
        priv = ec.generate_private_key(ec.SECP256R1())
        pem = priv.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        # Restrictive perms — key material at rest
        path.write_bytes(pem)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    pub_der = priv.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    fingerprint = hashlib.sha256(pub_der).hexdigest()
    return priv, fingerprint


def get_signing_key() -> tuple[ec.EllipticCurvePrivateKey, str]:
    """Return the cached signing key + fingerprint (thread-safe, lazy)."""
    global _cached
    if _cached is not None:
        return _cached
    with _lock:
        if _cached is None:
            _cached = _load_or_create()
    return _cached


def reset_cache() -> None:
    """Test hook — drop the cached key so the next call re-reads from disk."""
    global _cached
    _cached = None


def sign_es256_raw(payload: bytes) -> bytes:
    """Sign payload with ES256.

    Returns the raw (r||s, 64-byte) signature form used by JWS ES256 — not
    the ASN.1/DER form. Soul-file readers expect raw per the v1 spec.
    """
    priv, _ = get_signing_key()
    der_sig = priv.sign(payload, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der_sig)
    return r.to_bytes(32, "big") + s.to_bytes(32, "big")


def public_key_pem() -> bytes:
    """PEM-encoded public key — embedded verbatim in signature.json."""
    priv, _ = get_signing_key()
    return priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
