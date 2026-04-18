# Windy Clone — Deployment Runbook

This runbook covers shipping Windy Clone to production. There are two
supported targets:

- **AWS + Cloudflare R2** — the same stack as `windy-cloud`. Pick this if
  you're running the full ecosystem and want Clone co-located with the
  other services.
- **Standalone Docker on any VPS** — a single `docker compose up` on a
  Hostinger/Linode/EC2 box. Pick this if you're running Clone alone or
  bootstrapping a staging environment.

For the cross-service ops doc (lifecycle, monitoring, env-var ownership),
see `windy-cloud/deploy/aws/CLOUD_DEPLOYMENT.md`. Per-product secrets and
env vars are listed in `.env.production.example` at the repo root.

---

## 1. Architecture

```
 ┌──────────────┐          ┌──────────────────┐          ┌─────────────────┐
 │   Windy Pro  │          │   Windy Clone    │          │  Provider APIs  │
 │ account-srv  │◀────────▶│   API + Web      │────────▶│  ElevenLabs     │
 │ (JWKS, stats)│  JWT +   │   :8400 / :443   │  model   │  HeyGen         │
 └──────────────┘  /stats  └────────┬─────────┘  orders  │  PlayHT         │
                                    │                    │  ResembleAI     │
                                    │                    └─────────────────┘
                                    │                     (affiliate IDs
                                    │                      carried on every
                                    │                      order URL)
                                    ▼
                          ┌─────────────────────┐
                          │     Eternitas       │
                          │ POST /bots/         │
                          │     auto-hatch      │
                          │  → ET26-XXXX-XXXX   │
                          └─────────────────────┘
```

- **Clone stores:** orders, completed-clone rows, user preferences,
  cached recording-stats snapshots (for the "data may be stale" banner).
- **Clone does NOT store:** audio, video, user accounts, or any raw
  recording bytes. Those live in Windy Pro's account-server; Clone
  reaches in via Pro's `/api/v1/clone/training-data` endpoint with the
  user's own JWT.
- **Clone port:** `8400` in-container. Fronted by nginx or ALB on 443.
- **Domain:** `windyclone.com` (see §5).

---

## 2. Target A — AWS + Cloudflare R2

Prereqs: an AWS account with ECS/ECR/RDS/ALB/Secrets Manager access, a
Cloudflare account with R2 enabled, and access to the existing
`windy-cloud/deploy/aws-terraform/` module if you want to reuse it.

### 2.1 Storage

Clone itself has almost no blob storage — the recording bytes never touch
Clone's process. The one thing it *does* export is signed `.windysoul`
soul-file bundles. Those can stay in RDS (they're small) or, if you're
already paying for the R2 bucket `windy-cloud` uses, write them there
under the prefix `windy-clone/souls/`.

If you use R2, copy four values into a new secret:

```bash
aws secretsmanager create-secret \
  --name /prod/windy-clone/r2 \
  --secret-string '{
    "R2_ACCOUNT_ID":        "...",
    "R2_ACCESS_KEY_ID":     "...",
    "R2_SECRET_ACCESS_KEY": "...",
    "R2_BUCKET":            "windy-cloud-storage-prod",
    "R2_ENDPOINT":          "https://<account>.r2.cloudflarestorage.com"
  }'
```

### 2.2 Database

Clone's tables fit on the smallest RDS you'll ever provision. Two options:

- **Reuse the `windy-cloud` RDS cluster** with a separate `windy_clone`
  database inside it. Cheap, one IAM auth path, one backup.
- **Separate RDS instance** if you want hard isolation. `db.t4g.micro`
  is plenty — the whole schema is four tables.

`DATABASE_URL` format: `postgresql+asyncpg://<user>:<pass>@<host>:5432/windy_clone`

### 2.3 ECS Fargate

Build and push:

```bash
aws ecr create-repository --repository-name windy-clone
docker buildx build --platform linux/amd64 -t <account>.dkr.ecr.us-east-1.amazonaws.com/windy-clone:$(git rev-parse --short HEAD) --push .
```

Task definition — two containers:

1. `api` — the image above, listens on `:8400`. `environment` from
   `.env.production.example` non-secret keys. `secrets` from AWS Secrets
   Manager for: `SOUL_SIGNING_KEY_PEM`, `ELEVENLABS_API_KEY`,
   `HEYGEN_API_KEY`, `PLAYHT_API_KEY`, `PLAYHT_USER_ID`,
   `RESEMBLEAI_API_KEY`, `ETERNITAS_API_KEY`, `ETERNITAS_WEBHOOK_SECRET`,
   `WINDY_SERVICE_TOKEN`, `DATABASE_URL`.
2. `nginx` (optional) — only needed if you're not using ALB to terminate
   TLS. See `deploy/nginx.conf` for the canonical config.

**Health check:** `curl -f http://localhost:8400/health` every 30s.
**Replicas:** at least 2. The Wave-7 audit baked in signing-key-from-env
so two tasks sign soul files with the same fingerprint; do not skip the
secret, or half your signatures won't verify.

### 2.4 Provider affiliate IDs

`ELEVENLABS_AFFILIATE_ID=windy` and `HEYGEN_AFFILIATE_ID=windy` are
baked in. Override only if you're running a separate affiliate program.

---

## 3. Target B — Standalone Docker on a VPS

For a single-box deploy (e.g. the existing VPS at `72.60.118.54`):

```bash
ssh root@<vps>
git clone https://github.com/sneakyfree/Windy-Clone.git
cd Windy-Clone
cp .env.production.example .env
# Edit .env with real secrets. Every ELEVENLABS_/HEYGEN_/PLAYHT_/
# RESEMBLEAI_ key is required for the matching provider; omit to
# disable that provider cleanly.
docker compose up -d
```

Nginx + Let's Encrypt:

```bash
cp deploy/nginx.conf /etc/nginx/sites-available/windyclone
ln -s /etc/nginx/sites-available/windyclone /etc/nginx/sites-enabled/
certbot --nginx -d windyclone.com -d www.windyclone.com
systemctl reload nginx
```

A single `docker compose up` gives you API + web. SQLite lives in the
`clone-data` named volume (`docker volume inspect clone-data` for path).
For prod scale, switch `DATABASE_URL` to a managed Postgres before
traffic arrives.

---

## 4. Providers

Clone uses four third-party provider adapters. Each needs its own API
account and key in `.env`. All adapters implement the `Provider`
Protocol in `api/app/providers/base.py`; missing keys mean the relevant
provider returns 501 instead of accepting orders and stalling.

| Provider     | Kind  | Sign up                                  | Tier notes                                                                                      |
| ------------ | ----- | ---------------------------------------- | ----------------------------------------------------------------------------------------------- |
| ElevenLabs   | Voice | https://elevenlabs.io/app/settings/api-keys | Creator tier ($22/mo) minimum for voice cloning. Pro tier for Professional Voice Clone quality. |
| HeyGen       | Video | https://app.heygen.com/settings/api      | Enterprise tier for API access — contact their sales. Trial API keys expire in 7 days.          |
| PlayHT       | Voice | https://play.ht/studio/api-access        | Growth plan for API; needs both `PLAYHT_API_KEY` and `PLAYHT_USER_ID`.                          |
| Resemble AI  | Voice | https://app.resemble.ai/account/api      | Creator plan or above for programmatic cloning. Webhook secret configured per-project.          |

**ElevenLabs is the only provider wired end-to-end today** (Wave-7
landed `P0 #6 reject scaffolded providers` — HeyGen/PlayHT/Resemble all
return 501 until their adapters ship). Provision the keys now so the day
each adapter lands you only need to redeploy, not re-ops.

---

## 5. Domain + DNS

- Apex: `windyclone.com`
- www: `www.windyclone.com` (nginx 301s to apex)

DNS records:

| Type  | Name            | Target                                                |
| ----- | --------------- | ----------------------------------------------------- |
| A     | `windyclone.com` | ALB IP (AWS) or VPS IP (Hostinger)                   |
| CNAME | `www`           | `windyclone.com`                                      |

If you're fronting with AWS:

```
windyclone.com → CNAME → <alb-dns>.us-east-1.elb.amazonaws.com
```

Route53 only — any external CNAME at the apex breaks AWS ALIAS. Use an
ALIAS record to the ALB instead.

TLS is terminated at the ALB (AWS) or by nginx + certbot (VPS). The
API container itself only listens on HTTP 8400; never expose it
directly to the internet.

---

## 6. Eternitas auto-hatch

Already wired in `api/app/services/eternitas.py`. When a clone finishes
training, the pipeline calls `auto_hatch(identity_id, provider_id,
provider_model_id, clone_type, display_name)`:

```
┌──────────────────┐   clone ready   ┌────────────────────────────────┐
│ ElevenLabs /     │────────────────▶│ clone_pipeline.py              │
│ HeyGen webhook   │                 │   1. persist Clone row         │
└──────────────────┘                 │   2. POST {ETERNITAS_URL}      │
                                     │      /api/v1/bots/auto-hatch   │
                                     │   3. stash returned passport   │
                                     │      (ET26-XXXX-XXXX) on row   │
                                     └────────────────────────────────┘
```

Operational contract:

- **Request:** JSON `{owner_identity_id, bot_name, bot_type,
  provider, provider_model_id, source_product: "windy-clone"}` with an
  optional `Authorization: Bearer $ETERNITAS_API_KEY` header.
- **Response:** `{passport: "ET26-XXXX-XXXX"}` (or `passport_id` —
  both accepted).
- **Failure mode:** `EternitasHatchError` is raised; the pipeline
  logs and proceeds with a passport-less clone. The order is still
  marked `completed` — the clone works, it's just not Eternitas-verified
  yet. A follow-up sweep can re-hatch later.
- **Mock for local:** set `ETERNITAS_USE_MOCK=true` to treat every
  agent as `TOP_SECRET` and skip the HTTP call. Never set this in prod
  — it disables every trust gate.

The passport flows back through `/api/v1/clones/{id}` to the `My Clones`
page, which is how the "verified" badge appears in the UI.

Webhook side (`trust.changed`): Eternitas calls `POST /api/v1/webhooks/
trust/changed` with an HMAC-SHA256 signature over the body; the secret
is `ETERNITAS_WEBHOOK_SECRET`. On receipt Clone invalidates its in-process
trust cache for the passport, so the next gate re-fetches instead of
waiting out the TTL.

---

## 7. Pulling recording data from Windy Pro

Every `/api/v1/legacy/*` request validates a JWT against Pro's JWKS
(`api/app/auth/jwks.py:_get_jwks_client`), extracts
`windy_identity_id`, and calls Pro's `/api/v1/clone/training-data` with
the *same* JWT forwarded as a Bearer — Clone is a pure delegate, never
a privileged principal.

```
browser ──JWT──▶ Clone API ──validate via JWKS──▶ Pro's /.well-known
                     │
                     ├──JWT──▶ Pro /api/v1/clone/training-data
                     │                  │
                     │                  ▼
                     │         training bundles, stats
                     │
                     ├──write-through cache (CachedRecordingStats)
                     │
                     ▼
                 response
```

Fallback behavior when Pro is unreachable (see
`api/app/services/data_fetcher.py`):

1. Serve the last-known-good cached stats with a `stale=true` envelope
   field. The Legacy dashboard shows an amber "data may be stale" banner.
2. If nothing has ever been cached, return `unavailable=true`.
3. `/legacy/readiness` degrades the same way.

Ops implications:

- **JWKS rotation:** Pro rotates its keypair → Clone picks up the new
  JWK within 1 hour (the cache TTL in `jwks.py:_JWKS_CACHE_TTL`). If you
  need to force a rotation mid-hour, roll the Clone tasks.
- **JWT audience:** default is permissive (no `aud` check) because Pro
  hasn't committed to a per-product claim yet. Once it does, set
  `JWT_AUDIENCE=windy-clone` — Wave-7 PR #13 shipped the plumbing, it's
  off by default pending Pro's matching change.
- **Webhook signatures:** `POST /api/v1/webhooks/identity/created` fires
  when Pro mints a new user. Secret is `WINDY_PRO_WEBHOOK_SECRET`;
  `webhook_require_timestamp=true` enforces the `{ts}.{body}` HMAC form
  once Pro's side is on the new contract.

---

## 8. First-boot checklist

Run through this on the very first deploy:

- [ ] `ENVIRONMENT=production` and `DEV_MODE=false` — boot guards in
      `api/app/main.py:_enforce_boot_guards` will refuse to start
      otherwise.
- [ ] None of `WINDY_PRO_JWKS_URL` / `WINDY_PRO_API_URL` /
      `ETERNITAS_URL` are still the placeholder defaults (same guard).
- [ ] `SOUL_SIGNING_KEY_PEM` is set in Secrets Manager. Without it,
      each task self-generates its own ES256 key on first boot and soul-file
      verification fails for ~half the traffic behind a multi-task ALB.
- [ ] `JWT_AUDIENCE` left blank unless Pro is already minting
      `aud=windy-clone` tokens (otherwise 100% of auth 401s).
- [ ] `./scripts/smoke-test.sh` passes against the new deploy before
      pointing DNS at it.
- [ ] CORS_ORIGINS includes exactly the prod frontend origins; no
      `http://localhost` left over.
- [ ] Provider API keys are present for every provider you've enabled
      in the Discover page (missing keys → 501, not a crash).
