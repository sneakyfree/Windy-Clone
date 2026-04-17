"""ES256 signing key management for soul-file exports.

Resolution order (first match wins):
  1. SOUL_SIGNING_KEY_PEM env var — inline PKCS8 PEM. Used in prod (secret
     injected from AWS Secrets Manager via ECS task definition). Wins over
     file because it lets every task in a multi-replica deploy load the
     same key without sharing a volume.
  2. SOUL_SIGNING_KEY_PATH on disk.
  3. Auto-generate and persist at SOUL_SIGNING_KEY_PATH — DEV ONLY. Refused
     when DEV_MODE=false so a misconfigured prod task can't quietly mint
     its own per-replica key and fork the fleet's signing identity.

The public-key fingerprint is the SHA-256 of the DER-encoded SubjectPublicKeyInfo.
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

from ..config import get_settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_cached: tuple[ec.EllipticCurvePrivateKey, str] | None = None


class MissingSigningKey(RuntimeError):
    """Raised when no signing key is available and auto-generation is disallowed."""


def _parse_pem(pem: bytes, origin: str) -> ec.EllipticCurvePrivateKey:
    priv = serialization.load_pem_private_key(pem, password=None)
    if not isinstance(priv, ec.EllipticCurvePrivateKey):
        raise RuntimeError(f"{origin} is not an EC private key")
    return priv


def _load_or_create() -> tuple[ec.EllipticCurvePrivateKey, str]:
    """Resolve the signing key per the module docstring order."""
    settings = get_settings()

    # 1. Inline PEM from env (preferred in prod).
    if settings.soul_signing_key_pem.strip():
        priv = _parse_pem(settings.soul_signing_key_pem.encode(), "SOUL_SIGNING_KEY_PEM")
        logger.info("soul-file signing key loaded from SOUL_SIGNING_KEY_PEM env")
    else:
        # 2. PEM on disk.
        path = Path(settings.soul_signing_key_path)
        if path.exists():
            priv = _parse_pem(path.read_bytes(), str(path))
            logger.info("soul-file signing key loaded from %s", path)
        else:
            # 3. Auto-generate — DEV ONLY.
            if not settings.dev_mode:
                raise MissingSigningKey(
                    "No soul-file signing key found. Set SOUL_SIGNING_KEY_PEM in "
                    "the environment (recommended) or place a PEM at "
                    f"{path}. Auto-generation is refused when DEV_MODE=false."
                )
            path.parent.mkdir(parents=True, exist_ok=True)
            priv = ec.generate_private_key(ec.SECP256R1())
            pem = priv.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
            path.write_bytes(pem)
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
            logger.warning(
                "soul-file signing key auto-generated at %s — DEV ONLY path, "
                "never relied on in production.", path,
            )

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
    """Test hook — drop the cached key so the next call re-reads."""
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
