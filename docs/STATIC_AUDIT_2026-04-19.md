# Windy Clone — Static Deploy-Posture Audit

**Date:** 2026-04-19
**Auditor:** overnight loop #7
**Why static, not smoke:** `windyclone.ai` answers HTTP 401 `WWW-Authenticate: Basic realm="Pre-Launch"` (Cloudflare Access pre-launch gate, not our origin). `api.windyclone.ai` 404s. `windyclone.com` no longer resolves. **Nothing is deployed** — this is a paper audit of the repo state on `main` at 35e6d4c, asking: if we hit FIRE today, what would break?

**TL;DR verdict:** Clone is roughly 90% deploy-ready. Three production-breaking drifts in the JWKS/Pro contract would 401 every live user on boot. One config drift (default Pro URLs) is already fenced by the boot guard — good. Everything else is green or cosmetic.

**Headline findings:**

| # | Severity | Finding |
|---|---|---|
| **D-1** | 🔴 BLOCKER | Every live Pro JWT is rejected — Clone requires `sub`, Pro never mints it. |
| **D-2** | 🔴 BLOCKER | Identity-ID extraction reads `windy_identity_id`; Pro sends `windyIdentityId` — humans 401 after we fix D-1. |
| **D-3** | 🔴 BLOCKER | Passport claim is `payload["passport"]`; Pro sends `eternitas_passport` — agents silently downgraded to humans, bypassing Eternitas trust gate. |
| A-1 | 🟡 medium | Default Pro URLs (`windypro.thewindstorm.uk`, `api.windypro.com`) dead — fenced by prod boot guard, but `.env.example` still ships them as defaults, so dev boots against dead hosts. |
| A-2 | 🟡 medium | `DASHBOARD_URL` default points at `windyclone.ai` which is still the Cloudflare pre-launch gate. Identity-webhook redirect → 401 until a real origin is stood up. |
| A-3 | 🟢 low | `CORS_ORIGINS` prod default omits `https://www.windyclone.ai` (present in `.env.production.example` but not in `config.py` default). Fine as long as prod copies the example. |
| A-4 | 🟢 low | `Dockerfile` runs as root. ECS Fargate tolerates it but the Wave 14 runbook should switch to uid 10001 per `deploy/aws/CLONE_DEPLOYMENT.md:52`. |
| A-5 | 🟢 low | `api.add_middleware(CORSMiddleware, ..., allow_credentials=True, allow_methods=["*"], allow_headers=["*"])` — safe because `allow_origins` is a closed list, but `allow_methods=["*"]` with credentials is louder than it needs to be. |
| A-6 | 🟢 info | No payment wiring in-repo — orders are affiliate links to providers, not Stripe-mediated. Expected. |

D-1 / D-2 / D-3 are the JWKS-drift findings called out in the brief. Full treatment below and in `docs/WAVE14_AWS_DEPLOY_PLAN.md` §7. Each has a one-line fix in Clone — no Pro change required.

---

## 1. Public surface

| Check | Result |
|---|---|
| `windyclone.ai` reachable | **401** Cloudflare Pre-Launch Basic Auth. Not our origin. |
| `api.windyclone.ai` reachable | **404**. No origin registered. |
| `www.windyclone.ai` reachable | same 401 (shared Cloudflare rule). |
| `windyclone.com` DNS | NXDOMAIN. Matches the Wave 12 P0 canonical-domain migration — `.com` is supposed to 302-redirect at CF page-rule level to `.ai`, but the page rule is not live yet (DNS is gone entirely). |
| `/health` on any of the above | n/a — no origin. |

**Implication for Wave 14:** until an origin is stood up, no public surface exists to smoke. The pre-launch gate is orthogonal — once we deploy Clone behind it, the 401 moves from the static Cloudflare page to the pre-launch username/password. Decide whether to keep Access in place during bake-in or strip it for GA.

**Action for Wave 14 deploy docs:** the `.com` → `.ai` page-rule work in `DEPLOY.md` §5.2 assumes `.com` resolves; verify that CF zone still exists before depending on it. If the zone was deleted, re-add it or remove the `.com` pathway from the DEPLOY runbook (current state suggests the latter is simpler).

## 2. Identity contract with Pro JWKS

**This is where every blocker lives.** Covered in detail; read it carefully.

### 2a. Live Pro JWKS shape

From `https://api.windyword.ai/.well-known/jwks.json` at audit time (kid `37e8955762d43189`, alg `RS256`):

```json
{"keys":[{"kty":"RSA","use":"sig","alg":"RS256","kid":"37e8955762d43189","n":"...","e":"AQAB"}]}
```

Shape is exactly what `PyJWKClient` expects. No drift there.

### 2b. Live Pro JWT payload shape

From `windy-pro/account-server/src/routes/auth.ts:191-203`:

```ts
const tokenPayload: Record<string, any> = {
    userId: user.id,        // NOTE: camelCase, not "sub"
    email: user.email,
    tier: user.tier,
    accountId: user.id,
    windyIdentityId,        // NOTE: camelCase, not "windy_identity_id"
    type: identityType,     // 'human' | 'agent'
    scopes,
    products,
    iss: 'windy-identity',
};
if (passportNumber) tokenPayload.eternitas_passport = passportNumber;
```

No `sub`. No `windy_identity_id` (snake). No `aud`. Passport key is `eternitas_passport`.

### 2c. What Clone expects

From `api/app/auth/jwks.py:48-59`:

```python
required = ["exp", "sub"]          # ← "sub" required
decode_kwargs: dict = {"algorithms": ["RS256"]}
if settings.jwt_audience:
    decode_kwargs["audience"] = settings.jwt_audience
    required.append("aud")
if settings.jwt_issuer:
    decode_kwargs["issuer"] = settings.jwt_issuer
    required.append("iss")
decode_kwargs["options"] = {"require": required}
```

From `api/app/auth/jwks.py:65-67`:

```python
def extract_identity_id(payload: dict) -> str:
    return payload.get("windy_identity_id", payload.get("sub", ""))
```

From `api/app/auth/dependencies.py:86-92`:

```python
return CurrentUser(
    identity_id=identity_id,
    email=payload.get("email"),
    display_name=payload.get("display_name", payload.get("name")),
    raw_token=token,
    passport=payload.get("passport"),      # ← reads "passport"
)
```

### 2d. Findings

**D-1 (BLOCKER) — `sub` required but never minted.**
`jwt.decode(..., options={"require": ["exp", "sub"]})` raises `MissingRequiredClaimError: sub` on every real Pro token. Prod has `DEV_MODE=false`, so there is no mock-user fallback — every request 401s at the JWT layer.

Fix: make `sub` optional. Relax `required = ["exp", "sub"]` to `required = ["exp"]`, since identity is carried in `windyIdentityId` (fixed in D-2), not `sub`.

**D-2 (BLOCKER) — identity claim key mismatch.**
`extract_identity_id` reads `windy_identity_id` (snake_case). Pro emits `windyIdentityId` (camelCase). After fixing D-1, decode succeeds, but `identity_id` is `""` → `raise HTTPException(401, "Token missing identity claim")` at `dependencies.py:82-84`. Every user still 401s.

Fix: read `windyIdentityId` first (match the source of truth), fall back to `windy_identity_id` for forward-compat if Pro ever normalises, then `sub`:

```python
return (
    payload.get("windyIdentityId")
    or payload.get("windy_identity_id")
    or payload.get("sub", "")
)
```

**D-3 (BLOCKER) — passport claim key mismatch.**
`get_current_user` reads `payload.get("passport")`. Pro's `eternitas_passport` is never picked up. The consequences:

- Every agent token with a passport is constructed into a `CurrentUser(..., passport=None)`.
- `is_agent` returns `False`.
- Trust-gate dependencies that branch on `is_agent` silently take the human bypass path (`README.md:136`: "Human callers (JWT without a `passport` claim) bypass every gate").
- Agents reach sensitive actions (soul-file export, auto-hatch webhooks) without being checked against Eternitas at all.

This is a **security bypass**, not just a functional bug. It doesn't help an attacker forge a passport, but it does let a legitimate agent execute as though trust were TOP_SECRET with no lookup.

Fix: read `eternitas_passport` first, fall back to `passport` for symmetry with any older tokens:

```python
passport=payload.get("eternitas_passport") or payload.get("passport"),
```

**Aligned (no action needed):**

- `iss` — Pro sets `"windy-identity"`, Clone's `JWT_ISSUER=""` (not enforced). If prod ever flips `JWT_ISSUER=windy-identity` it'll keep working. Don't flip this in Wave 14 unless every sibling service does too.
- `aud` — Pro doesn't mint an `aud`, Clone's `JWT_AUDIENCE=""` (not enforced). Do not set `JWT_AUDIENCE=windy-clone` in prod env until Pro mints it; setting it early 401s everyone, which the `.env.production.example` header already warns about.
- `kid` — Pro publishes `kid` in the JWKS, signs with it; PyJWKClient resolves correctly. No drift.

## 3. Avatar / voice-twin creation

- `POST /api/v1/orders` → `api/app/routes/orders.py` → `clone_pipeline.run_elevenlabs_pipeline` as `BackgroundTask`.
- Wave-12 M-1 fix (`services/clone_pipeline.py:80-109`) is present on main: dev-mode marks AWAITING_UPSTREAM with an explanatory `error_message`; non-dev without `ELEVENLABS_API_KEY` marks FAILED with a clear reason.
- Wave-12 boot guard (`main.py:90-103`) refuses to start prod without every wired provider's key. `WIRED_PROVIDER_IDS = frozenset({"elevenlabs"})` — only ElevenLabs is wired; HeyGen/PlayHT/Resemble are `coming_soon=True` and don't trip the guard.
- HeyGen adapter exists (`providers/heygen.py`) but is marked `coming_soon=True` in the registry, so avatar orders that target it will be rejected at `POST /orders` before reaching the pipeline.

Posture: good. No change needed for Wave 14 first-cut (voice-only launch).

## 4. ElevenLabs / HeyGen upstream integration

- ElevenLabs affiliate ID baked in at `ELEVENLABS_AFFILIATE_ID=windy`.
- HeyGen affiliate ID at `HEYGEN_AFFILIATE_ID=windy`.
- Both are carried on every provider URL per `docs/PROVIDER_INTEGRATION.md`.
- No cross-service signing or shared secrets with ElevenLabs — we're a pass-through referrer, not an OEM, so there's no secret to rotate on their side.
- The affiliate string is in `config.py` defaults, not a secret — good (it would be fine if it leaked).

## 5. Payments

- **No internal payment handling.** The marketplace is affiliate-based: Clone never touches a card. Confirmed by `grep -rn "stripe\|payment\|checkout\|invoice" api` → 0 hits.
- Implication: no PCI scope, no Stripe webhook to configure, no webhook-secret rotation schedule. Wave 14 deploy does not need a Stripe secret.
- If this changes post-launch (e.g., Clone charges a markup on ElevenLabs orders), the whole webhook plumbing in `routes/webhooks.py` is already in place and just needs a Stripe handler added.

## 6. CORS

- `Settings.cors_origins` default: `"https://windyclone.ai"` (single origin).
- `.env.production.example`: `"https://windyclone.ai,https://www.windyclone.ai"`.
- Wave-12 P0 shipped the `.com`→`.ai` migration; CORS correctly excludes the legacy `.com` origin (which should never terminate TLS on our origin anyway).
- `CORSMiddleware` config: `allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"]`.
- **Finding (A-5, low):** `allow_methods=["*"]` with `allow_credentials=True` is permissive for an API that actually only uses GET/POST/PATCH/DELETE. Tightening to `["GET","POST","PATCH","DELETE","OPTIONS"]` costs nothing and trims one CORS-abuse vector. Safe to do pre-launch; post-launch we'd need to confirm no frontend bundle ships a TRACE/CONNECT etc.

## 7. Security headers

- Provided at the nginx layer, not FastAPI (`deploy/nginx.conf:34-38`):
  - `X-Frame-Options: SAMEORIGIN`
  - `X-Content-Type-Options: nosniff`
  - `X-XSS-Protection: 1; mode=block`
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- No CSP. Not a blocker for GA, but once we have a stable frontend bundle we should add one — Vite output is predictable.
- No `Referrer-Policy` or `Permissions-Policy`. Also low — add in a header-polish wave post-launch.

**Wave 14 note:** ECS Fargate behind ALB means nginx is optional. The runbook is ALB→ECS direct; headers can move to a middleware in FastAPI *or* be set on the ALB listener rules. Recommend FastAPI middleware so headers travel with the app and nginx isn't load-bearing.

## 8. Observability

- Structured stdout logs via Python `logging` — `print` statements in `main.py:208-213` for startup banner.
- No metrics endpoint.
- No OpenTelemetry hook.
- No health endpoint expansion beyond `/health` (simple `200 {"status":"healthy"}`).
- Wave 14 needs:
  - `/health` → keep for ALB target-group checks.
  - Consider adding `/health/full` exercising DB, Pro JWKS fetch, Eternitas reachability (Cloud shipped `/health/full` in Phase 3 — steal the pattern).
  - CloudWatch log group `/ecs/clone-api-<env>` per `deploy/aws/CLONE_DEPLOYMENT.md:68` is already planned.

## 9. Docker + compose hygiene

### Dockerfile
- Multi-stage: `node:20-alpine` frontend build → `python:3.12-slim` API. Good.
- Exposes `:8400`, `CMD uvicorn --workers 2`. Two workers is fine for first-cut on a 1-vCPU Fargate task.
- **Finding A-4 (low):** runs as root. The Wave 14 runbook says uid 10001. Add `RUN useradd -u 10001 -m appuser && chown -R appuser:appuser /app && USER appuser` before the `CMD`.

### docker-compose.yml
- Two services: `api` (always on) and `web-dev` (behind `profiles: [dev]`). Sensible for dev/prod parity.
- Named volumes `clone-data` and `web-node-modules` — both fine.
- `CORS_ORIGINS` hard-coded to `https://windyclone.ai,http://localhost:5173` — prod should override with `.env.production.example` values.
- No `docker-compose.prod.yml`. Cloud (Phase 3) wrote one at deploy time; Clone should follow the same pattern in Wave 14 so dev compose isn't the prod compose.
- Healthcheck uses `curl` which is installed in the Dockerfile — good.

## 10. Boot guards (self-audit)

`api/app/main.py:49-110` is solid:

- Prod + DEV_MODE → abort ✓
- Prod + placeholder URLs → abort ✓
- Prod + wired provider without API key → abort ✓ (Wave-12 addition)
- Dev + DEV_MODE → loud WARN ✓
- Eternitas mock in any env → loud WARN ✓ (lifespan, lines 191-195)

**Gap:** guards don't check `DASHBOARD_URL` or `CORS_ORIGINS` for placeholder shapes. A prod env that forgot to override `DASHBOARD_URL` would boot with the default `https://windyclone.ai`, which right now 401s. Low-priority — the identity webhook would fail noisily on first use — but worth bolting on to `_UNSAFE_URL_MARKERS` in Wave 14 once `api.windyclone.ai` exists for real.

---

## Summary — what to carry into Wave 14

**Must-fix in the Wave 14 PR:**

- D-1, D-2, D-3 (JWKS drift) — three one-liner edits in `api/app/auth/jwks.py` + `api/app/auth/dependencies.py`, plus a regression test per finding.

**Wave 14 runbook-scope (not code):**

- New RDS + ECS stack per `deploy/aws/CLONE_DEPLOYMENT.md` but hoisted into the shared `vpc-011cc35a43403f9ef` like Phase 3, not the module's private VPC.
- DNS: `clone.windyword.ai` → EIP, Cloudflare zone `86085f0869c360f79fef22db2b4b9b60`, `proxied=false`.
- Fresh `HMAC_WINDY_CLONE` is already in the lockbox (`~/.eternitas-phase2-state`); use it for `ETERNITAS_WEBHOOK_SECRET` — do not mint.
- `IDENTITY_WEBHOOK_SECRET` → mint fresh, then hand to Pro for the subscribers table entry pointing at `https://clone.windyword.ai/api/v1/webhooks/identity/created`.
- `SOUL_SIGNING_KEY_PEM` → generate once, store in Secrets Manager, publish the public half at `/.well-known/soul-signing-keys.json`.
- `ELEVENLABS_API_KEY` → required to pass boot guard. Pull from Grant's ElevenLabs dashboard.

**Post-launch polish (defer):**

- Tighten `CORS_ORIGINS` middleware methods.
- Non-root container user.
- `/health/full` deep probe.
- Extend `_UNSAFE_URL_MARKERS` once dashboard origin is stable.
- CSP + Referrer-Policy + Permissions-Policy headers.
