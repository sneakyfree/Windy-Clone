# Windy Clone — AWS Deployment Runbook

**Audience:** the person (or agent) standing up Clone in a fresh AWS account. Assumes familiarity with `aws-cli`, Terraform or CloudFormation, and that the Eternitas live Trust API is already reachable from the Clone VPC.

All infra lives in **one account, one region, per environment** (`staging`, `prod`). Names below use `<env>` as a placeholder (`clone-api-prod`, `clone-db-staging`, …).

---

## Topology

```
Internet
   │
   ▼
Route 53 (clone-api.windy...) ──► ACM cert ──► ALB
                                                │
                                                ▼
                                      ECS Fargate service
                                      (clone-api-<env>)
                                      │
         ┌──────────────────┬─────────┴──────────┬─────────────────────┐
         ▼                  ▼                    ▼                     ▼
  RDS Postgres        Secrets Manager       Cloudflare R2        Eternitas Trust API
  (orders/clones/     (keys, tokens,        (soul files +        (http over VPC
   preferences)       webhook secrets)      cached stats)         peering / NAT)
```

Job workers run on the same task definition as the API (`mode=worker`) — see [Provider job queue](#provider-job-queue-scaling) for when to split them out.

## Prerequisites

| What | Purpose |
|---|---|
| AWS account with admin-capable deploy user | CloudFormation/Terraform apply |
| Route 53 hosted zone for the Clone domain | Public DNS |
| ACM cert in `us-east-1` (or region-matched) for `clone-api.<domain>` | HTTPS on ALB |
| Cloudflare account with R2 enabled | Soul file storage |
| Live Eternitas URL + webhook secret | Trust gate + cache invalidation |
| Windy Pro JWKS URL | JWT verification for auth |

## Container image

Build once per release, tag with the Git SHA, push to ECR:

```bash
aws ecr create-repository --repository-name clone-api --image-scanning-configuration scanOnPush=true
docker build -t clone-api:$(git rev-parse --short HEAD) .
docker tag clone-api:$(git rev-parse --short HEAD) $ECR_URI:$(git rev-parse --short HEAD)
docker push $ECR_URI:$(git rev-parse --short HEAD)
```

Base the image on `python:3.12-slim`. Run as a non-root user (`uid 10001`). Only expose `PORT=8400`.

---

## API on ECS Fargate

**Cluster:** `clone-<env>`. One cluster per environment, isolates scaling failures.

**Task definition (`clone-api-<env>`):**

| Setting | Value | Notes |
|---|---|---|
| Launch type | `FARGATE` | No EC2 to manage. |
| CPU / memory | 1 vCPU / 2 GB (staging), 2 vCPU / 4 GB (prod) | Soul-file ZIP assembly peaks on upload; monitor and scale up if p95 exceeds 500 ms. |
| Platform version | `1.4.0` or later | Gets EFS support if we ever need it for signing keys. |
| Network mode | `awsvpc` | Each task gets its own ENI. |
| Logging | `awslogs` → CloudWatch `/ecs/clone-api-<env>` | Retention 30 d staging / 90 d prod. |
| Health check | `/health` every 15 s, 3 retries | Matches the ALB health check. |
| Stop timeout | 120 s | Gives background pipeline tasks time to flush on deploy. |

**Environment variables injected from Secrets Manager** — see [Secrets Manager layout](#secrets-manager-layout). Non-secret config (`PORT`, `LOG_LEVEL`, `CORS_ORIGINS`, `DASHBOARD_URL`, `ETERNITAS_URL`) goes in plain env.

**Service:** `clone-api-<env>`. Desired count 2 for HA. Deployment circuit breaker enabled. Rolling deploy (`maximumPercent=200`, `minimumHealthyPercent=100`).

**Auto-scaling:**

| Metric | Threshold | Action |
|---|---|---|
| `CPUUtilization` | > 70% for 3 min | +1 task (min 2, max 10) |
| `ALBRequestCountPerTarget` | > 500 rpm | +1 task |
| `MemoryUtilization` | > 80% for 2 min | +1 task |

Scale in is lazy — 10-minute cooldown — so soul-file spikes don't cause thrash.

**Load balancer:** ALB with one HTTPS listener on :443, HTTP :80 redirects to HTTPS. Target group health check at `GET /health`, grace period 60 s.

**IAM task role** (least-privilege):

```
  - secretsmanager:GetSecretValue on the five secrets below
  - logs:CreateLogStream, logs:PutLogEvents on /ecs/clone-api-<env>
  - rds-db:connect on the Clone DB user
  - s3:PutObject, s3:GetObject on the R2 bucket *via the R2-compatible endpoint*
    (R2 uses S3 API; the IAM policy is applied at the Cloudflare token layer, not AWS)
```

---

## PostgreSQL via RDS

**Engine:** PostgreSQL 16, `aurora-postgresql` if we want read replicas cheaply, `postgres` otherwise. Start with single-AZ `db.t4g.medium` in staging, Multi-AZ `db.r6g.large` in prod.

**Instance identifier:** `clone-db-<env>`.

| Setting | Value |
|---|---|
| Storage | `gp3`, 50 GB, autoscale to 200 GB |
| Backups | 7 d retention staging / 35 d prod, daily window 05:00 UTC |
| Encryption | KMS customer-managed key `alias/clone-<env>` |
| Subnets | Private DB subnet group (no public IPs) |
| Parameter group | Default, with `rds.force_ssl=1` |
| Security group | Ingress 5432 from the Fargate task SG only |
| Deletion protection | ON in prod |

**Migrations:** the API does `create_all` on boot today. Before prod, bolt on Alembic:

```bash
uv run alembic init api/migrations
uv run alembic revision --autogenerate -m "Initial schema"
```

Run `alembic upgrade head` as an ECS one-off task (`clone-migrate-<env>`) on every deploy, gated on success before the service rolls.

**Secrets:** RDS master password goes into `clone/<env>/db/master` at create time. The app never reads the master; it connects as `clone_app` with CRUD on the app tables only.

---

## Secrets Manager layout

One secret per logical group. Rotate on the schedule noted in the [Security Review](../../docs/security-review.md).

| Secret name | Fields | Rotation |
|---|---|---|
| `clone/<env>/db/app` | `DATABASE_URL` | 90 d (AWS managed) |
| `clone/<env>/windy` | `WINDY_PRO_WEBHOOK_SECRET`, `WINDY_SERVICE_TOKEN` | 180 d manual |
| `clone/<env>/eternitas` | `ETERNITAS_API_KEY`, `ETERNITAS_WEBHOOK_SECRET` | 180 d manual, coordinated with Eternitas |
| `clone/<env>/providers` | `ELEVENLABS_API_KEY`, `HEYGEN_API_KEY`, `PLAYHT_API_KEY`, `PLAYHT_USER_ID`, `RESEMBLEAI_API_KEY` | Per-provider policy |
| `clone/<env>/r2` | `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | 90 d rolling |
| `clone/<env>/soul-signing-key` | `SOUL_SIGNING_KEY_PEM` (PKCS8) | See [security review](../../docs/security-review.md) — dual-key overlap rotation |

**ElevenLabs API key handling:**

- The key sits only in `clone/<env>/providers` under field `ELEVENLABS_API_KEY`.
- ECS task role has `secretsmanager:GetSecretValue` scoped to that ARN.
- Task pulls the secret at boot via the ECS `secrets` directive — it never lands in the image or in an env file on disk.
- Any rotation fires `aws ecs update-service --force-new-deployment` to pick up the new value. No code change.

---

## Soul file ZIP storage on Cloudflare R2

R2 is the cold store for exported `.windysoul` archives. Chosen over S3 because egress is free and the user's ecosystem standard for cold storage is R2.

**Bucket:** `windy-clone-soul-files-<env>`. One bucket per env — do not share prod and staging.

**Object key pattern:** `soul/<clone_id>/<export_id>.windysoul` where `export_id` is a fresh UUID per export (not a collision-prone content hash — we want a distinct object per export so revocation is per-artifact).

**Lifecycle:**

| Rule | Action |
|---|---|
| Age > 90 d, no download in last 30 d | Delete |
| Age > 7 d, no download ever | Delete |
| Tagged `legal_hold=true` | Retain indefinitely (manually set) |

**Upload flow:**

1. `POST /api/v1/clones/{id}/export-soul-file` builds the archive in-memory (current Wave-3 behavior).
2. For anything > 5 MB the API streams directly to R2 instead of returning inline. Response becomes `{ "download_url": "...", "expires_at": "..." }`.
3. For smaller archives, optionally still stream inline — avoids a needless R2 round-trip.

**Signed URL expiry policy:**

| Audience | Expiry | One-use? |
|---|---|---|
| End-user download from dashboard | **15 minutes** | No (user may click twice) |
| Service-token cross-service export (Mail importing a clone, Fly re-hydrating) | **5 minutes** | Yes — server embeds a `nonce` that's consumed on first successful GET |
| Legal export / audit | **24 hours** | No, but writes an access log row per GET |

**Generation:**

```python
# R2 is S3-compatible, use boto3 with the R2 endpoint.
s3 = boto3.client(
    "s3",
    endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
    aws_access_key_id=..., aws_secret_access_key=..., region_name="auto",
)
url = s3.generate_presigned_url(
    "get_object",
    Params={"Bucket": bucket, "Key": key},
    ExpiresIn=900,  # 15 min — coordinated with frontend refresh behavior
)
```

Clock skew between the API and R2 can invalidate URLs that look fresh. Keep the API's system clock in sync (ECS Fargate tasks use AWS NTP automatically — no action needed — but alarm if drift exceeds 2 s).

---

## Provider job queue scaling

Today `run_elevenlabs_pipeline` runs as a `FastAPI BackgroundTask` inside the same process that served the POST. That's fine for dev and first prod traffic (≤ a few clones per minute), but has three limits:

1. The pipeline dies with the task if a deploy rolls or a task OOMs.
2. Long ElevenLabs polls (5–15 min turnaround) pin a task slot.
3. Retry semantics are ad hoc — a failed pipeline updates `Order.status = FAILED` and stops there.

**Tier-1 rollout (< 100 orders/day):** keep the BackgroundTask path. Add:

- A `migrate-and-reap` ECS one-off on deploy that moves any `UPLOADING`/`TRAINING` orders older than 30 minutes back to `PENDING` so the next process picks them up.
- A CloudWatch alarm: `Order.status = 'FAILED' count > 5 in 10 min → page on-call`.

**Tier-2 rollout (> 100 orders/day OR premium SLA):** extract workers onto SQS.

1. Create two queues per env: `clone-pipeline-<env>` (main), `clone-pipeline-dlq-<env>` (DLQ with `maxReceiveCount=3`).
2. `POST /api/v1/orders` persists the Order row, then enqueues `{"order_id": ...}` to the main queue.
3. Deploy a second ECS service `clone-worker-<env>` with the same image but `CMD=["python", "-m", "app.workers.pipeline"]`. Its worker loop long-polls SQS.
4. Scale the worker service on `ApproximateNumberOfMessagesVisible` (1 msg → 1 worker, up to 20).
5. Visibility timeout: 20 min (longer than the longest ElevenLabs poll cycle).
6. Retryable failures (5xx from ElevenLabs, transient Eternitas) leave the message; poison messages land in the DLQ and page.

Do not split workers until metrics say you need to — premature split doubles the infra surface for zero user-visible win.

---

## Observability

| Signal | Where |
|---|---|
| API request logs | CloudWatch `/ecs/clone-api-<env>` |
| Pipeline outcomes | Structured log line per order transition, filter on `event=pipeline_*` |
| Trust gate denials | `WARN` with passport + action + required/actual level |
| R2 download counts | R2 built-in analytics + monthly export to S3 for long retention |
| RDS perf | Performance Insights on |

One dashboard per env, eyes-on metrics: p95 latency of `/api/v1/orders`, rate of `Order.status='FAILED'`, rate of `403` responses from the trust gate, ElevenLabs API error rate, R2 5xx rate.

---

## Deploy checklist

Before first prod deploy:

- [ ] Alembic bolted on, autogenerated initial migration reviewed + applied.
- [ ] All six Secrets Manager secrets populated with real values (not placeholders).
- [ ] `ETERNITAS_URL` points at the live Eternitas prod endpoint, `ETERNITAS_USE_MOCK=false`.
- [ ] Eternitas has Clone's webhook URL (`/api/v1/webhooks/trust/changed`) registered + sharing a secret with us.
- [ ] Windy Pro has Clone's identity webhook URL registered.
- [ ] R2 bucket created with lifecycle + CORS set for the dashboard origin.
- [ ] RDS snapshot schedule verified — test restore once before go-live.
- [ ] Soul signing key generated via the dual-key overlap procedure in [security review](../../docs/security-review.md); public key PEM published at `/.well-known/soul-signing-keys.json`.
- [ ] Route 53 + ACM DNS validation complete.
- [ ] `DEV_MODE=false` on prod task env (otherwise the mock dev user is served when a JWT is missing).

---

## Rollback

- Deploy failures: ECS circuit breaker auto-reverts.
- Data issue post-deploy: RDS point-in-time restore to a new instance, swap DATABASE_URL via Secrets Manager, force task redeploy. Allot 20 min RTO for this path.
- Signing key compromise: rotate per [security review](../../docs/security-review.md) — does NOT require downtime; new keys join, old keys retire after a publication window.
