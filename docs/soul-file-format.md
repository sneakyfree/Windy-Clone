# Windy Soul File Format — v1.0.0

**Canonical spec.** Any reader or writer of a `.windysoul` archive MUST conform to this document. Version bumps (v1.1, v2) will be communicated via the `spec_version` field in `manifest.json`.

## What a soul file is

A `.windysoul` is a self-contained, signed ZIP archive that packages everything needed to prove continuity of a Clone and rehydrate it elsewhere — voice model pointers, sample media, transcripts, an agent birth certificate (when applicable), and a cryptographic signature over the manifest.

Produced by Windy Clone. Consumable by any service that trusts Windy Clone's public signing key (e.g. Eternitas, Windy Fly, Windy Mail's agent importer).

## File extension & MIME type

| Extension | MIME type          |
| --------- | ------------------ |
| `.windysoul` | `application/zip` |

Servers MUST send `Content-Disposition: attachment; filename="<clone_id>.windysoul"`.

## Archive layout

```
<clone_id>.windysoul
├── manifest.json                    (required)
├── voice/                           (if clone_type ∈ {voice, both})
│   ├── voice_model.json
│   └── sample.wav
├── avatar/                          (if clone_type ∈ {avatar, both})
│   ├── avatar_model.json
│   └── preview_video.mp4
├── transcripts/
│   └── transcripts.ndjson           (required, may be empty)
├── birth_certificate.pdf            (required iff clone represents an agent)
└── signature.json                   (required)
```

Archive member ordering in the central directory is **deterministic**: `manifest.json` first, then content in the order listed above, then `signature.json` last. Two exports of identical content produce byte-identical archives.

## `manifest.json`

Canonical JSON (sorted keys, 2-space indent, LF line endings). Signed by `signature.json`.

```json
{
  "spec_version": "1.0.0",
  "clone_id": "a3f1...",
  "passport": "ET26-7F3A-9B21",
  "owner_email": "grant@windypro.com",
  "created_at": "2026-04-16T17:40:12+00:00",
  "content_summary": {
    "clone_type": "voice",
    "provider_id": "elevenlabs",
    "provider_model_id": "el-voice-xyz",
    "quality_label": "Studio Quality",
    "is_agent": true,
    "name": "Grant's Voice"
  },
  "files": [
    "birth_certificate.pdf",
    "transcripts/transcripts.ndjson",
    "voice/sample.wav",
    "voice/voice_model.json"
  ],
  "signing_key": {
    "alg": "ES256",
    "fingerprint_sha256": "<hex sha256 of DER-encoded SubjectPublicKeyInfo>"
  }
}
```

Fields:

| Field | Type | Notes |
| ----- | ---- | ----- |
| `spec_version` | string | SemVer. Readers MUST reject unknown majors. |
| `clone_id` | string | Clone's UUID. |
| `passport` | string \| null | `ET26-XXXX-XXXX` if agent, else null. |
| `owner_email` | string \| null | Null when exported via service token. |
| `created_at` | string | RFC 3339 UTC. |
| `content_summary` | object | See below. |
| `files` | array[string] | Sorted list of all non-manifest/non-signature members. |
| `signing_key.alg` | string | Always `"ES256"` in v1. |
| `signing_key.fingerprint_sha256` | string | Hex SHA-256 of the signing public key (DER SPKI). |

## `voice/`

- `voice_model.json` — provider, model ID, name. JSON, sorted keys.
- `sample.wav` — RIFF/WAVE PCM. V1 guarantees a valid header; content may be a single silent frame if no rendered sample is available.

## `avatar/`

- `avatar_model.json` — provider, model ID, name.
- `preview_video.mp4` — ISO-BMFF container. V1 may emit a minimal `ftyp` + `mdat` stub when no preview has been generated yet.

## `transcripts/transcripts.ndjson`

Newline-delimited JSON. One utterance per line. Each line is sorted-keys JSON:

```
{"speaker":"Grant","text":"...","ts":"2026-04-16T17:40:12+00:00"}
```

Empty files are not permitted; at minimum the export contains one "no transcripts recorded" placeholder line so consumers can assume the file is present and parseable.

## `birth_certificate.pdf`

Required **only** when `manifest.content_summary.is_agent == true` (i.e. the clone has a `passport`). PDF 1.4, single page. Human-readable rendering of the Eternitas-issued identity record. V1 emits a minimal template; richer rendering can land without changing the spec.

## `signature.json`

Detached ES256 signature over the **exact bytes** of `manifest.json` as stored in the archive.

```json
{
  "alg": "ES256",
  "signed_object": "manifest.json",
  "signature_b64": "<base64 of 64-byte r||s>",
  "public_key_pem": "-----BEGIN PUBLIC KEY-----\n...",
  "fingerprint_sha256": "<same value as manifest.signing_key.fingerprint_sha256>"
}
```

Signature format: **raw concatenated `r || s`** (each 32 bytes, big-endian) — same as JWS ES256, NOT the ASN.1/DER form. Consumers must convert to DER before calling most `cryptography` verify APIs.

### Verification procedure

1. Read `manifest.json` bytes (exact storage bytes, no re-canonicalisation).
2. Compute `SHA-256(SPKI_DER)` of the public key in `signature.json.public_key_pem`.
3. Confirm it matches both `signature.json.fingerprint_sha256` and `manifest.signing_key.fingerprint_sha256`.
4. Verify the ECDSA-P256-SHA256 signature over the manifest bytes.
5. Reject on any mismatch.

## Export endpoint

```
POST /api/v1/clones/{clone_id}/export-soul-file
```

Auth:

- Authenticated user who owns the clone (`clone.identity_id == user.identity_id`), **or**
- `Authorization: Bearer <WINDY_SERVICE_TOKEN>` for cross-service callers.

Agents additionally pass the `EXPORT_SOUL_FILE_HUMAN` trust gate when exporting a clone whose content is human-derived (no passport on the clone) — see [`agent-trust-gates.md`](./agent-trust-gates.md).

Response: `200 OK`, `application/zip`, streamed as an attachment.

## Stability contract

- v1.x is forwards-compatible for additive fields.
- Removing or renaming a required field requires a major bump.
- The `ES256` algorithm is fixed in v1; v2 may add algorithm negotiation.
