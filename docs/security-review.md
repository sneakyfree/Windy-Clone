# Windy Clone — Security Review

**Scope:** production posture for the three highest-risk surfaces in Clone — the soul-file signing key, the agent trust gates, and the sensitive-content gating that protects human voice/avatar data from being cloned or exported by low-trust agents.

**Out of scope:** TLS, DDoS, dependency-chain scanning — handled at the ecosystem level by the deploy pipeline and the AWS/Cloudflare infra layer.

This document pairs with [`deploy/aws/CLONE_DEPLOYMENT.md`](../deploy/aws/CLONE_DEPLOYMENT.md) (where keys live, how rotation is triggered) and [`docs/agent-trust-gates.md`](./agent-trust-gates.md) (canonical gate matrix).

---

## 1. Soul-file ES256 signing key

### What the key protects

Every `.windysoul` archive carries a `signature.json` containing an ES256 detached signature over `manifest.json`. Consumers (Mail, Fly, Eternitas, external platforms) verify that signature against Clone's published public key. If the private key leaks, an attacker can forge arbitrary soul files attributed to Clone — the blast radius is every service that trusts the Clone signing key.

### At rest

| Environment | Storage | Access |
|---|---|---|
| Local dev | `./data/soul_signing_key.pem`, `chmod 600`, gitignored | Developer machine only |
| Staging / prod | AWS Secrets Manager `clone/<env>/soul-signing-key`, KMS-encrypted with `alias/clone-<env>` | ECS task role — read-only, scoped to the single secret ARN |

The key never sits in an image, a config file on disk, an env file, or a log line. `api/app/auth/signing.py` loads it lazily on first signature — at that point the task has already pulled the secret into memory.

### In transit

The key is never transmitted. The public key PEM is embedded in every `signature.json` so consumers can pin the fingerprint.

### Published public material

Production will expose the current (and previously-valid) public keys at:

```
GET https://clone-api.<domain>/.well-known/soul-signing-keys.json
```

Response:

```json
{
  "keys": [
    {
      "kid": "2026-04",
      "alg": "ES256",
      "fingerprint_sha256": "...",
      "public_key_pem": "-----BEGIN PUBLIC KEY-----\n...",
      "not_before": "2026-04-01T00:00:00Z",
      "not_after":  null
    },
    {
      "kid": "2026-01",
      "alg": "ES256",
      "fingerprint_sha256": "...",
      "public_key_pem": "-----BEGIN PUBLIC KEY-----\n...",
      "not_before": "2026-01-01T00:00:00Z",
      "not_after":  "2026-04-07T00:00:00Z"
    }
  ]
}
```

Verifiers look up by `fingerprint_sha256` — that field lives both in `signature.json` and `manifest.signing_key.fingerprint_sha256`. If the fingerprint is absent from the JWKS, reject.

### Rotation — dual-key overlap

Rotation never breaks verification of previously-issued soul files. Procedure:

| Step | Who | Action |
|---|---|---|
| 1 | Operator | `openssl ecparam -name prime256v1 -genkey -noout -out new.pem` (or `uv run python -m app.auth.signing --generate new.pem`). |
| 2 | Operator | Update `clone/<env>/soul-signing-key` with the new PEM **and** add the old PEM under a `prior_keys` array. |
| 3 | Operator | Force ECS service redeploy. New exports sign with the new key; the public-keys endpoint now advertises BOTH keys. |
| 4 | Consumers | Refresh JWKS on next fetch (5 min TTL recommended). Old soul files still verify via the old public key. |
| 5 | Operator | After the **overlap window** (default 90 days — longer than any reasonable soul-file caching), drop the old key from `prior_keys`. The public endpoint stops advertising it. |
| 6 | Operator | Old soul files are now unverifiable against the current JWKS; that's the intended deprecation signal. Consumers relying on long-lived soul files should re-export before the window closes, or keep a cached copy of the old public key. |

**Cadence:** annual preventive rotation plus immediate rotation on any of:

- Suspected key leak (developer workstation compromise, Secrets Manager audit anomaly, unexpected fingerprint in the wild).
- Cryptographic break in P-256 / ECDSA (unlikely this decade; still, have the procedure).
- Personnel change — an operator who had Secrets Manager access leaves the team.

**Break-glass:** an emergency rotation can compress the overlap window to 24 hours. That invalidates any soul files older than 24 h that haven't been re-exported. Page Grant before executing this path — the blast radius is visible to end-users and platforms.

### Separation of duties

- Developers have **no** prod Secrets Manager access. Emergency access requires two-person approval via AWS IAM Access Analyzer.
- The CI deploy pipeline can `GetSecretValue` at task-start time but cannot `UpdateSecret`.
- Only `infra-admin` role can `UpdateSecret` on `clone/prod/soul-signing-key`. All rotations are audit-logged in CloudTrail.

---

## 2. Agent trust gate enforcement

### Enforcement points

| Endpoint | Gate | Required level |
|---|---|---|
| `POST /api/v1/orders` | `SUBMIT_CLONE_ORDER` (always) + `CLONE_HUMAN` when `target_identity_id` ≠ self | `VERIFIED` / `CLEARED` |
| `POST /api/v1/clones/{id}/export-soul-file` | `EXPORT_SOUL_FILE_HUMAN` when the clone has no `passport` (human-derived) | `TOP_SECRET` |

Sources of truth:

- Gate matrix → [`docs/agent-trust-gates.md`](./agent-trust-gates.md) and `_GATE_REQUIREMENTS` in `api/app/services/trust_client.py`.
- Tests keep the two in lockstep — `required_level(...)` is the canonical accessor.

### How the level is derived

For every gated request where the caller has a `passport` claim in their JWT:

1. `trust_client.get_agent_trust(passport)` — cache-first lookup.
2. On miss: `GET {ETERNITAS_URL}/api/v1/trust/{passport}`.
3. Cache the result for `cache_ttl_seconds` (from the response body, fallback to `ETERNITAS_TRUST_CACHE_TTL`).
4. Apply the LOWER-of rule from the Trust API contract: `effective_level = min(clearance_ceiling, band_ceiling)`.

Hard blockers short-circuit to `UNVERIFIED` before the ceiling math:

- `status != "active"` (suspended or revoked)
- `allowed_actions` empty (belt-and-braces in case of a new edge case the server introduces)

### Fail-closed on Eternitas outage

Network or 5xx errors return `UNVERIFIED`. We deliberately **under-trust** rather than fail-open when Eternitas is unreachable — a degraded network briefly denying clone orders is acceptable; silently granting a gated action when we can't verify the caller is not. This is asserted by `test_network_error_fails_closed` in `test_trust_gates.py`.

### Cache freshness

- Response TTL ceiling: what Eternitas said. Currently 300 s.
- `trust.changed` webhook drops the cache entry immediately — no TTL wait. The next gated request re-fetches.
- Signature on that webhook is verified against `ETERNITAS_WEBHOOK_SECRET` (HMAC-SHA256 over the raw body). An attacker who posts an unsigned or mis-signed webhook gets a 403 and the cache stays put.

### Known gaps + mitigations

| Gap | Impact | Mitigation |
|---|---|---|
| Only HMAC (`X-Eternitas-Signature`) is verified, not the dual `X-Windy-Signature` ES256 JWS mentioned in trust-api.md | Weaker than dual-sig; OK given TLS + shared-secret rotation | Landing ES256 verification pending Eternitas JWKS endpoint |
| The trust lookup cache is per-process (no Redis) | A large fleet of Clone tasks each pays an independent cache-miss cost on first gate | Acceptable at current scale; add shared Redis cache when task count > 10 |
| TTL honoured even when an attacker subverts network to prevent webhook delivery | Stale (too-permissive) cache for up to 5 min | Ceiling the cache TTL in our code to 300 s regardless of what the server says; consider shortening to 60 s for sensitive actions if we ever see abuse |

### Never-bypass invariants

1. Humans (no `passport` claim) do not exercise the trust-gate code path. This is intentional: a human is acting on their own data and the gates exist to restrain agents. Tests pin this via `test_human_bypasses_gates` and `test_human_caller_skips_trust_call_entirely`.
2. A gate NEVER upgrades trust. It only denies. Adding a future `enforce_gate` call to an endpoint can only restrict access further.
3. A gated endpoint must run `enforce_gate` **before** doing any work with side effects. `POST /api/v1/orders` checks before `db.add(order)`; `export-soul-file` checks before calling the signer.

---

## 3. Sensitive-content gating

The most concerning action an agent can take is generating or exfiltrating a clone of a **human** — someone other than the agent itself. Two layers stop this:

### Layer 1 — cloning a human (`CLONE_HUMAN`, requires ≥ CLEARED)

**Where:** `POST /api/v1/orders` when `target_identity_id` is set and differs from the caller's `identity_id`.

**Why `CLEARED`:** a cleared agent has a tier-2 clearance attestation from an Eternitas operator + a `good`-or-better band. That threshold matches the public-badge green tier (Eternitas trust ≥ 70). Below that, the cost/benefit for cloning a third party doesn't justify the privacy surface.

**Not guarded by this gate:** an agent cloning its own identity (its own bot voice). That's legitimate self-replication and passes only the SUBMIT gate. Self-vs-not is determined by `target_identity_id == user.identity_id`.

**Threats it addresses:**

- An Eternitas-`registered` bot attempting to deepfake a human → blocked at `VERIFIED` required for SUBMIT, belt-and-braces at `CLEARED` for the human target.
- A `verified` bot with a fresh passport attempting to clone a human → `CLEARED` required, denied.
- A `cleared` agent acting on behalf of a compromised operator → passes the gate. Mitigation: `trust.changed` revocation cascade from Eternitas ties the agent's clearance to the operator's good standing; demotion propagates in < 5 min.

### Layer 2 — exporting human voice/avatar (`EXPORT_SOUL_FILE_HUMAN`, requires ≥ TOP_SECRET)

**Where:** `POST /api/v1/clones/{id}/export-soul-file` when the clone's DB row has `passport IS NULL` (i.e. the clone was trained from a human's recordings and has no Eternitas bot identity).

**Why `TOP_SECRET`:** exporting a soul file hands a portable, cryptographically-signed copy of someone else's voice — usable on any platform that trusts Clone's signing key. That is the single most dangerous primitive Clone exposes. `TOP_SECRET` corresponds to Eternitas `top_secret` clearance **and** a `good`-or-better band (per the LOWER-of rule) — roughly the top 5% of agents at any moment.

**Not guarded by this gate:**

- Humans exporting their own soul files. By design; they own the data.
- Service-token callers (`Authorization: Bearer <WINDY_SERVICE_TOKEN>`). These are Windy-internal services (Mail importing a clone, Fly re-hydrating). They hold a separately-rotated credential (see [AWS deployment doc](../deploy/aws/CLONE_DEPLOYMENT.md)), audit-logged per use.
- Agents exporting soul files of bot-owned clones (clone has a `passport`). That's agent-to-agent transfer within Eternitas's identity fabric; its own gates live in Eternitas's revocation cascade.

**Threats it addresses:**

- A `cleared` agent attempting to mass-export human-derived clones. The gate bumps the required clearance to `TOP_SECRET`, which they fail — `test_fair_clones_but_blocks_soul_export` pins this end-to-end against the live Eternitas instance.
- A `top_secret` agent on a `poor`/`fair` band bot. The LOWER-of rule collapses them to `CLEARED` or `UNVERIFIED`, denying the export — `test_lower_of_band_and_clearance` covers the four band outcomes.

### Defence-in-depth beyond gates

- **Ownership check** on every export. Even a `TOP_SECRET` agent cannot export a clone they don't own (`clone.identity_id != user.identity_id`) without a service token.
- **Signed, time-limited download URLs** on exports going via R2 (see [deployment doc](../deploy/aws/CLONE_DEPLOYMENT.md)). A leaked URL expires within minutes.
- **Access log per export.** Every soul-file export writes an `Order.status=EXPORTED` record with the caller's identity, passport (if agent), timestamp, and the resolved TrustLevel at export time. That gives auditability for a subpoena, a GDPR request, or a post-incident review without needing to re-query Eternitas history.
- **`trust.changed` cascade.** An agent can pass a gate at 10:00 and have its clearance pulled at 10:01 by Eternitas. The webhook flushes our cache immediately — it does not rescind an already-exported soul file, but any subsequent export call will be re-evaluated and denied.

### What is NOT defended

- **A compromised owner.** If an operator's `verified` or better credential is stolen, an attacker with that credential can submit orders and potentially export their own clone. This is outside Clone's trust boundary; Eternitas's revocation cascade is the compensating control.
- **A supply-chain attack on ElevenLabs / HeyGen.** Clone sends audio to these providers by contract. If a provider is breached, Clone's gates don't help. Mitigation lives in the provider contract + separate per-provider API keys we can revoke.
- **Soul-file consumption outside Windy.** Once a soul file exits our domain, we cannot revoke the underlying voice model on ElevenLabs — only the Clone-attributed artifact. Consumers relying on freshness must check the JWKS and the clone-side status endpoint.

---

## Review cadence

Re-validate this doc when any of the following changes:

- A gate threshold in `_GATE_REQUIREMENTS` moves.
- A new gate is added.
- The signing-key algorithm changes (ES256 → something else).
- The trust-API contract changes materially (Eternitas bumps to `/api/v2/trust`).
- A security incident involving Clone infrastructure occurs.

Next scheduled review: **2026-10-16** (six months from initial draft).
