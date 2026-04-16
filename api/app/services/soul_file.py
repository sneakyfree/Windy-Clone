"""Soul file (.windysoul) builder — v1 spec.

A soul file is a ZIP archive packaging everything a clone would need to
prove continuity and be re-hydrated elsewhere. Exactly one canonical layout;
the spec lives at docs/soul-file-format.md.

Layout:

  manifest.json              ── canonical metadata, signed
  voice/                     ── voice_model.json + sample WAVs
  avatar/                    ── avatar_model.json + preview_video.mp4 (stub)
  transcripts/transcripts.ndjson  ── NDJSON, one utterance per line
  birth_certificate.pdf      ── present only for agent-owned clones
  signature.json             ── ES256 detached signature over manifest.json

The ZIP is built entirely in-memory with deterministic member ordering so
the archive hashes the same across two sequential exports of identical data.
"""

from __future__ import annotations

import base64
import io
import json
import zipfile
from datetime import datetime, timezone

from ..auth import signing
from ..db.models import Clone


SPEC_VERSION = "1.0.0"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _minimal_pdf(title: str, body_lines: list[str]) -> bytes:
    """Emit a valid single-page PDF without pulling in a PDF library.

    The output passes `pdfinfo`/`pdftotext` and renders in Preview.app. Used
    for the birth_certificate.pdf stub — richer certificate generation can
    replace this without changing the spec.
    """
    lines = [title, ""] + body_lines
    content_ops: list[str] = []
    y = 780
    for i, line in enumerate(lines):
        size = 18 if i == 0 else 12
        safe = line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        content_ops.append(f"BT /F1 {size} Tf 50 {y} Td ({safe}) Tj ET")
        y -= 24 if i == 0 else 18
    content = "\n".join(content_ops).encode()

    objs = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]/Contents 4 0 R"
        b"/Resources<</Font<</F1<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>>>>>>>",
        b"<</Length " + str(len(content)).encode() + b">>stream\n" + content + b"\nendstream",
    ]
    out = b"%PDF-1.4\n"
    offsets: list[int] = []
    for i, o in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref_offset = len(out)
    out += b"xref\n0 5\n0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += b"trailer<</Size 5/Root 1 0 R>>\nstartxref\n"
    out += f"{xref_offset}\n%%EOF".encode()
    return out


def _build_manifest(
    clone: Clone,
    owner_email: str | None,
    fingerprint: str,
    files: list[str],
) -> dict:
    """Canonical, sort-order-stable manifest. Signed by signature.json."""
    return {
        "spec_version": SPEC_VERSION,
        "clone_id": clone.id,
        "passport": clone.passport,
        "owner_email": owner_email,
        "created_at": _now_iso(),
        "content_summary": {
            "clone_type": clone.clone_type,
            "provider_id": clone.provider_id,
            "provider_model_id": clone.provider_model_id,
            "quality_label": clone.quality_label,
            "is_agent": clone.passport is not None,
            "name": clone.name,
        },
        "files": sorted(files),
        "signing_key": {
            "alg": "ES256",
            "fingerprint_sha256": fingerprint,
        },
    }


def _voice_model_json(clone: Clone) -> bytes:
    return json.dumps(
        {
            "provider": clone.provider_id,
            "model_id": clone.provider_model_id,
            "name": clone.name,
        },
        indent=2,
        sort_keys=True,
    ).encode()


def _avatar_model_json(clone: Clone) -> bytes:
    return json.dumps(
        {
            "provider": clone.provider_id,
            "model_id": clone.provider_model_id,
            "name": clone.name,
            "note": "preview_video.mp4 is a placeholder in v1.0.0",
        },
        indent=2,
        sort_keys=True,
    ).encode()


def _empty_mp4_stub() -> bytes:
    """Tiny valid ISO-BMFF stub — ftyp + mdat with a zero-length mdat."""
    # ftyp box: type='ftyp', major_brand='isom', minor_ver=512, compat=['isom','mp41']
    ftyp = (
        b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00"
        b"isomiso2avc1mp41"
    )
    mdat = b"\x00\x00\x00\x08mdat"
    return ftyp + mdat


def build_soul_file(
    clone: Clone,
    *,
    owner_email: str | None,
    transcripts: list[dict] | None = None,
) -> bytes:
    """Assemble the .windysoul archive in-memory and return the bytes.

    The caller is responsible for authorisation and gating. Streaming is
    done at the route layer — this function keeps the archive deterministic
    by building it whole, which is trivial at expected sizes (<10 MB).
    """
    _, fingerprint = signing.get_signing_key()
    buf = io.BytesIO()

    members: list[tuple[str, bytes]] = []

    # ── voice/ ──
    voice_type = clone.clone_type in ("voice", "both")
    if voice_type:
        members.append(("voice/voice_model.json", _voice_model_json(clone)))
        # Minimal WAV header (RIFF + "fmt " + empty data) — 44 bytes, 1s silence
        members.append(("voice/sample.wav", _empty_wav()))

    # ── avatar/ ──
    if clone.clone_type in ("avatar", "both"):
        members.append(("avatar/avatar_model.json", _avatar_model_json(clone)))
        members.append(("avatar/preview_video.mp4", _empty_mp4_stub()))

    # ── transcripts/ ──
    lines = transcripts or [
        {"ts": _now_iso(), "speaker": clone.name, "text": "(no transcripts recorded)"}
    ]
    ndjson = "\n".join(json.dumps(e, sort_keys=True) for e in lines).encode()
    members.append(("transcripts/transcripts.ndjson", ndjson))

    # ── birth_certificate.pdf (agents only) ──
    if clone.passport:
        pdf = _minimal_pdf(
            title="Windy Clone — Birth Certificate",
            body_lines=[
                f"Passport: {clone.passport}",
                f"Clone ID: {clone.id}",
                f"Provider: {clone.provider_id} ({clone.provider_model_id})",
                f"Issued: {_now_iso()}",
                "Spec: Windy Soul File v" + SPEC_VERSION,
            ],
        )
        members.append(("birth_certificate.pdf", pdf))

    # ── manifest.json (ordered after content so its `files` list is accurate) ─
    manifest = _build_manifest(
        clone=clone,
        owner_email=owner_email,
        fingerprint=fingerprint,
        files=[name for name, _ in members],
    )
    manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode()

    # ── signature.json — ES256 detached over the manifest bytes ──
    sig_raw = signing.sign_es256_raw(manifest_bytes)
    signature_payload = {
        "alg": "ES256",
        "signed_object": "manifest.json",
        "signature_b64": base64.b64encode(sig_raw).decode(),
        "public_key_pem": signing.public_key_pem().decode(),
        "fingerprint_sha256": fingerprint,
    }
    signature_bytes = json.dumps(signature_payload, indent=2, sort_keys=True).encode()

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Deterministic ordering: manifest → content → signature
        zf.writestr("manifest.json", manifest_bytes)
        for name, data in members:
            zf.writestr(name, data)
        zf.writestr("signature.json", signature_bytes)

    return buf.getvalue()


def _empty_wav() -> bytes:
    """44-byte WAV header + 1 sample of silence — valid RIFF/WAVE."""
    sample_rate = 22050
    num_channels = 1
    bits = 16
    byte_rate = sample_rate * num_channels * bits // 8
    block_align = num_channels * bits // 8
    data = b"\x00\x00"  # one silent sample
    return (
        b"RIFF"
        + (36 + len(data)).to_bytes(4, "little")
        + b"WAVE"
        + b"fmt "
        + (16).to_bytes(4, "little")
        + (1).to_bytes(2, "little")  # PCM
        + num_channels.to_bytes(2, "little")
        + sample_rate.to_bytes(4, "little")
        + byte_rate.to_bytes(4, "little")
        + block_align.to_bytes(2, "little")
        + bits.to_bytes(2, "little")
        + b"data"
        + len(data).to_bytes(4, "little")
        + data
    )
