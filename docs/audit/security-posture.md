# Security Posture Audit — Wave 7

Checked via `grep`, config inspection, and live probes against a running API.
Each finding has a severity. Full reproduction context is in `docs/GAP_ANALYSIS.md`.

## CORS

- `CORSMiddleware` wired in `api/app/main.py:43`.
- `allow_origins = settings.cors_origin_list`, default `"https://windyclone.com,http://localhost:5173"`.
- `allow_credentials=True`, `allow_methods=["*"]`, `allow_headers=["*"]`.
- **Finding:** `http://localhost:5173` is in the default prod list. Low risk (must clear DNS + request from that origin) but sloppy. **P2.**

## Rate limits

- **None.** No `slowapi`, no `Limiter`, no `RateLimit` middleware anywhere in `api/app/`.
- Every route is unbounded from a single IP.
- Practical impact: cheap DoS on HMAC verification endpoints (`/webhooks/*`) — each request forces a SHA-256 over the body regardless of whether the signature is valid. Order creation is likewise unbounded. **P1.**

## Auth coverage

Cross-checked `docs/audit/endpoint-inventory.txt` against the public-vs-authed list:

| Path | Required auth | Correct? |
|---|---|---|
| `GET /health` | Public | ✅ |
| `GET /docs`, `/openapi.json`, `/redoc` | Public | ⚠ In prod, OpenAPI exposes the full schema. Non-critical but leaks internal knowledge. **P3.** |
| `POST /api/v1/webhooks/identity/created` | HMAC | ✅ (`windy_pro_webhook_secret`) |
| `POST /api/v1/webhooks/trust/changed` | HMAC | ✅ (`eternitas_webhook_secret`) |
| All `/api/v1/{legacy,orders,clones,preferences,providers}/*` | `get_current_user` | ✅ in code, ⚠ dev-mode fallback bypasses verification — see P0 #1 in `GAP_ANALYSIS.md`. |

## JWT validation

`api/app/auth/jwks.py:43`:

```python
payload = jwt.decode(
    token, signing_key.key,
    algorithms=["RS256"],
    options={"require": ["exp", "sub"]},
)
```

- **Algorithm pinned to RS256.** Good — `alg=none` is rejected by PyJWT since `algorithms=["RS256"]` is a positive allow-list.
- **`exp` required** — expiry enforced.
- **`aud` NOT validated.** A JWT minted by Windy Pro for any other service in the ecosystem (Mail, Chat, Cloud) will validate successfully against Clone. If any of those services mints tokens with different trust assumptions, Clone silently inherits them. **P1.**
- **`iss` NOT validated.** Same concern — anything signed by the Windy Pro key is accepted regardless of intended issuer. **P1.**

## SQL injection

- All DB access goes through SQLAlchemy Core `select(...)` / `update(...)` / ORM. No string concatenation against user input.
- Surface: **none identified.** ✅

## XSS

- No `HTMLResponse`, no Jinja templates, no direct HTML rendering. API returns JSON / ZIP only.
- Surface: **none identified.** ✅

## SSRF

- Outbound HTTP is limited to:
  - `WINDY_PRO_API_URL` + fixed paths
  - `ETERNITAS_URL` + fixed paths
  - Provider `API_BASE` constants (ElevenLabs, HeyGen, …) — hard-coded, not user-controlled
- No endpoint accepts a user-supplied URL for outbound fetch.
- Surface: **none identified.** ✅

## Open redirect

- No `RedirectResponse`. ✅

## Webhook replay

- HMAC signatures are verified but there is no `timestamp` + freshness check and no nonce.
- An attacker who captures a single valid `trust.changed` or `identity/created` webhook delivery can replay it arbitrarily.
- Impact on `trust.changed`: cache gets invalidated again — low (transient cache miss).
- Impact on `identity/created`: idempotent upsert — low (no new row created for an existing `identity_id`).
- **Severity: P2** — not currently damaging but brittle; any future non-idempotent webhook handler would inherit the hole.

## Secrets hygiene

- No `AKIA*`, `sk_live_`, `whsec_*`, or hard-coded API keys in the tree.
- `git log -p` scan for obvious patterns returned only test fixtures (`test-xi-key`).
- All secret material is loaded via env → `Settings` → functions. ✅

## Dependencies

- `pyjwt[crypto]>=2.9.0`, `cryptography>=43.0.0`, `sqlalchemy>=2.0` — all modern. Not audited in depth; CI should run `pip-audit`.
