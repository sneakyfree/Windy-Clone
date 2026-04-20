# Wave 14 — Windy Clone AWS migration plan

**Scope:** stand up Clone's API + DB in AWS under the shared TheWindstorm infrastructure (account `819439781125`, `us-east-1`, VPC `vpc-011cc35a43403f9ef`), publish it at `clone.windyword.ai`, and fix the three JWKS drift blockers caught in `docs/STATIC_AUDIT_2026-04-19.md` in the same PR that ships the deploy. Modeled on `windy-cloud/docs/WAVE13_PHASE3_RUNBOOK.md` (Phase 3).

**Position in the phase series:** this is conceptually Phase 4 of the Wave 13 AWS buildout — Clone sits alongside Pro (Phase 1), Eternitas (Phase 2), and Cloud (Phase 3) in the same VPC, sharing the same JWKS/HMAC fabric.

**Why gated FIRE:** parity with Phase 3. Grant is asleep the night this is prepared, so the actual apply happens with him awake and saying "proceed"; this doc is the playbook.

---

## 1. Target state

| | Value |
|---|---|
| AWS account | `819439781125` (TheWindstorm personal) |
| Region | `us-east-1` |
| VPC | `vpc-011cc35a43403f9ef` (shared — Phases 1-3 already live here) |
| AZ | `us-east-1b` (splits load with Phase 1/3 in `-1a` and Phase 2 in `-1b`) |
| API host | EC2 on EIP, or Fargate behind ALB (§3 picks) |
| DB | RDS Postgres 16 (`clone-db`), db.t3.micro single-AZ for launch, Multi-AZ in a follow-up wave |
| DNS | `clone.windyword.ai` A-record → EIP, Cloudflare zone `86085f0869c360f79fef22db2b4b9b60`, `proxied=false` |
| TLS | certbot on the host (matching Phase 3); `/etc/letsencrypt/live/clone.windyword.ai/` |
| CORS origins | `https://windyclone.ai,https://www.windyclone.ai,https://clone.windyword.ai` |
| Boot guard-passing env | `ENVIRONMENT=production`, `DEV_MODE=false`, Pro/Eternitas URLs pointing at live phases, `ELEVENLABS_API_KEY` set |

**Note on public dashboard vs API host:** `clone.windyword.ai` is the API endpoint. The consumer-facing dashboard domain `windyclone.ai` stays on Cloudflare Pages (currently pre-launch gated); its React app calls `https://clone.windyword.ai/api/v1/...` through CORS. This decouples the agent-friendly API from the Pages-hosted marketing/dashboard layer, same pattern as `cloud.windyword.ai` vs public Cloud pages.

## 2. Cost estimate

At steady state (first 90 days, <100 orders/day):

| Resource | Monthly |
|---|---|
| EC2 `t3.small` (2 vCPU / 2 GB, on-demand, us-east-1) | ~$15 |
| EBS 30 GB gp3 | ~$2.40 |
| Elastic IP (attached) | $0 |
| RDS `db.t3.micro` Postgres, 20 GB gp3, single-AZ | ~$16 |
| RDS backups (7 d retention) | ~$1 |
| CloudWatch Logs (~2 GB/mo) | ~$1 |
| Secrets Manager (6 secrets × $0.40) | ~$2.40 |
| Route 53 / Cloudflare DNS | $0 (already paid) |
| Cloudflare R2 (soul-file cold storage, <1 GB month one) | ~$0 (free tier) |
| **Total** | **~$38/mo** |

Wave 14 scales up only on real traffic. If daily orders pass ~100 the bottleneck is the BackgroundTask path pinning API workers (see `deploy/aws/CLONE_DEPLOYMENT.md` §Provider job queue scaling) — that's a Wave 15 follow-up to split out an SQS worker service.

**Fargate alt (not recommended for launch):** same topology but ECS Fargate 1 vCPU/2 GB × 2 tasks + ALB ≈ **~$80/mo**. Higher cost, no meaningful reliability win at single-instance throughput, and Phase 3 demonstrated EC2+certbot works. Revisit when we need > 2 tasks.

## 3. Architecture decision — EC2+certbot, not Fargate+ALB

Phase 3 ran EC2+EIP+nginx+certbot despite having a Terraform module for ECS+ALB. Reasons to copy that choice for Clone:

- Phase 3 proved `docker compose --env-file .env -d` + local certbot on t3.small is reliable. Sticking with the same recipe halves the runbook.
- ALB adds ~$20/mo and a second set of SGs/listeners with zero user-visible win at one task.
- Rollback is simpler: one box, one `docker compose down`, one DNS change.
- The existing `deploy/aws/CLONE_DEPLOYMENT.md` that targets ECS+Fargate stays on as the Wave 15+ scale-out path, not the Wave 14 go-live path. Don't delete it.

If Grant pushes back and wants Fargate at launch, flip to `deploy/aws/CLONE_DEPLOYMENT.md` as the canonical runbook and this doc becomes the cost/blocker cross-reference.

## 4. Prerequisites (Gate 0)

All must be green before firing:

| # | Check | Proof |
|---|---|---|
| 1 | Phase 1 (Pro) JWKS live | `curl https://api.windyword.ai/.well-known/jwks.json` → 200, kid `37e8955762d43189` RS256 ✓ (confirmed 2026-04-19) |
| 2 | Phase 2 (Eternitas) keys live | `curl https://eternitas.windyword.ai/.well-known/eternitas-keys` → 200, kid `prGDpGg9PPbXK1op5j3nQWTkQlRkfkDsWaAyErz5MZc` ES256 |
| 3 | Phase 3 (Cloud) reachable | `curl https://cloud.windyword.ai/health` → 200 (deployed at EIP `32.193.70.195`) |
| 4 | `aws sts get-caller-identity` returns `windy-ecosystem-admin` in `819439781125` |
| 5 | `HMAC_WINDY_CLONE` retrievable from `~/.eternitas-phase2-state` on the deploy machine (value pre-minted when Eternitas subscribed Clone) |
| 6 | Cloudflare API token with edit on zone `86085f0869c360f79fef22db2b4b9b60` (CLI or dashboard) |
| 7 | JWKS drift fixes (D-1/D-2/D-3 in `STATIC_AUDIT_2026-04-19.md`) merged to `main` before EC2 rollout — otherwise first real user 401s |
| 8 | `ELEVENLABS_API_KEY` available (pulled from Grant's ElevenLabs dashboard; not in the ecosystem lockbox yet — Wave 14 prep task) |
| 9 | Local `docker build -t clone-api:wave14 .` clean — same bug-pattern preflight Phase 3 ran (see §8 below) |

**Do not fire until every row has a proof column.** Phase 3 spent 20 minutes debugging AppleDouble files because the local build wasn't run cleanly; don't repeat that.

## 5. Secrets to mint fresh vs reuse

| Secret | Source | Notes |
|---|---|---|
| `ETERNITAS_WEBHOOK_SECRET` | **reuse** from `~/.eternitas-phase2-state` (`HMAC_WINDY_CLONE`) | Phase 2 issued one HMAC per subscriber at boot; minting fresh here silently breaks every inbound `trust.changed`. |
| `WINDY_PRO_WEBHOOK_SECRET` | **mint fresh** `openssl rand -hex 32`, then hand to Pro for its subscribers table | Pro's `/webhooks/identity/created` is signed with HMAC-SHA256 matching this value. |
| `WINDY_SERVICE_TOKEN` | **mint fresh** `openssl rand -hex 32` | Cross-service bearer; share with Mail / Fly as they come online and consume soul-file exports. |
| `SOUL_SIGNING_KEY_PEM` | **mint fresh once**, then rotate on the dual-key overlap schedule | `openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out soul_signing.pem && openssl pkcs8 -topk8 -nocrypt -in soul_signing.pem -out soul_signing_pkcs8.pem`. Public half published at `/.well-known/soul-signing-keys.json`. |
| `ELEVENLABS_API_KEY` | **reuse** Grant's existing ElevenLabs account key | Do not mint a new ElevenLabs account for Clone — preserves affiliate attribution history. |
| `DATABASE_URL` | **mint fresh** at RDS provision time (master pw + app-user pw both via `openssl rand -base64 32`) | App connects as `clone_app`, never master. |
| `ETERNITAS_API_KEY` | **reuse** if Phase 2 issued Clone one; otherwise mint via Eternitas admin API | Check `~/.eternitas-phase2-state` first. |

**Lockbox update required:** after Gate 4, append the new values to `/tmp/kit-army-config/ACCESS_LOCKBOX.md` in the Clone section. Do not commit to git.

## 6. DNS plan

**Target record:**

```
clone.windyword.ai.  300  IN  A  <EIP minted at Gate 2>
```

- Zone: `86085f0869c360f79fef22db2b4b9b60` (`windyword.ai`, Cloudflare)
- Proxy: **off** (`proxied=false`) — matching Phase 3. Proxy-on would re-terminate TLS at CF edge and our certbot→nginx chain stops making sense.
- TTL: 300 s for Gate 3, bump to 3600 once smoke passes and DNS is confirmed cached.
- `www.clone.windyword.ai` — **not created**. The API is a single host; no www alias.

**CORS origin list for the API's env:**

```
CORS_ORIGINS=https://windyclone.ai,https://www.windyclone.ai,https://clone.windyword.ai
```

Include `clone.windyword.ai` because operators hitting the API directly from browser devtools need it; include the two consumer dashboard origins because that's where real traffic comes from.

**Legacy `.com` handling:** `windyclone.com` does not currently resolve (audit finding A-1 flavor). The `DEPLOY.md` §5.2 page-rule plan assumed the zone still existed; verify in Cloudflare dashboard at Gate 3 and either re-add the zone (if we still want the 302) or delete the page-rule docs from DEPLOY.md. Grant's call — default to delete unless he says otherwise, since `.com` was a legacy brand artifact.

## 7. JWKS drift fix — the code half of this PR

Summary of `docs/STATIC_AUDIT_2026-04-19.md` §2d:

- **D-1** — drop `sub` from `required` in `api/app/auth/jwks.py`.
- **D-2** — read identity from `windyIdentityId` → `windy_identity_id` → `sub` in that order.
- **D-3** — read passport from `eternitas_passport` → `passport` in that order.

Tests to add:

- `api/tests/test_auth_jwks_drift.py` (new): three cases, one per finding. Each mints a local RS256 token with the Pro-shaped payload (no `sub`, `windyIdentityId` set, `eternitas_passport` set for the agent case), monkeypatches the JWKS client to return the local pubkey, and asserts `get_current_user` returns the right `CurrentUser`.
- No existing test should need to change — current tests use the mock dev-user path or mint tokens with `sub`/`windy_identity_id` set, so relaxing the decoder is backward-compatible.

**Order of operations in the PR:**

1. Fix D-1/D-2/D-3 and add tests — small diff, entirely in `api/app/auth/`.
2. Update `CHANGELOG.md` (if present) or reference this plan.
3. Do **not** roll the Wave 14 deploy changes (§8-§11) in the same commit. Separate commits on the same branch, so the drift fix can land and be smoke-tested against Phase 1 Pro tokens independently before we aim it at AWS.

## 8. Bug-pattern preflight (replay of Phase 3's)

| # | Pattern | Applies to Clone? | Mitigation |
|---|---|---|---|
| 1 | `uv sync` needs README + src/ before install | **No** | Dockerfile uses `uv pip install --system -e ".[dev]"` with pyproject.toml only — package source isn't required at install time, and Clone's Dockerfile already tested clean. |
| 2 | compose overlays `!override` / `!reset` | **No** | No overlays. Wave 14 writes a new `docker-compose.prod.yml` at deploy time. |
| 3 | `${VAR:-default}` expands from shell, not env_file | **Yes** | `docker-compose.yml` uses `${ELEVENLABS_API_KEY:-}` etc. Wave 14 prod compose drops the `:-` defaults and pulls from `env_file: .env` exclusively (mirrors Phase 3 §Step 5). |
| 4 | nginx site file must exist before certbot | **Yes** | Runbook §Step 7 writes `/etc/nginx/sites-available/clone.windyword.ai` + symlink into `sites-enabled/` and runs `nginx -t && systemctl reload` **before** `certbot --nginx`. |
| 5 | private repo clone needs `GITHUB_CLONE_TOKEN` | **Yes** | `sneakyfree/Windy-Clone` is private. Skip the `user_data curl` path; scp deploy artifacts directly from the operator machine (Phase 3's fix). |
| 6 | `depends_on: service_healthy` + scale-to-0 deadlock | **No** | Single `api` service, no scale-to-0. |
| 7 | admin bootstrap via entrypoint env vars not wired | **No** | No admin-user bootstrap — identity comes from Pro JWTs. |
| 8 | AppleDouble `._*` files from macOS tar | **Yes** | Use `COPYFILE_DISABLE=1 tar ...` when bundling on the Mac deploy machine. |

## 9. Gated FIRE sequence

### Gate 1 — RDS

```bash
aws rds create-db-subnet-group \
    --db-subnet-group-name windy-prod-private \
    --db-subnet-group-description "shared private subnets" \
    --subnet-ids <private-subnet-a> <private-subnet-b>   # reuse Phase 3 subnet group if it exists

aws rds create-db-instance \
    --db-instance-identifier clone-db \
    --db-instance-class db.t3.micro \
    --engine postgres --engine-version 16.4 \
    --allocated-storage 20 --storage-type gp3 \
    --master-username clone_master \
    --master-user-password "$(openssl rand -base64 32)" \
    --vpc-security-group-ids <clone-db-sg> \
    --db-subnet-group-name windy-prod-private \
    --backup-retention-period 7 \
    --no-publicly-accessible
```

Expected outputs:
- `Endpoint: clone-db.<hash>.us-east-1.rds.amazonaws.com:5432`

Then connect as master once, `CREATE USER clone_app WITH PASSWORD '...'; GRANT ALL ON DATABASE ... TO clone_app;`. App uses only `clone_app`.

### Gate 2 — EC2 + EIP + IAM

```bash
aws ec2 run-instances \
    --image-id ami-009d9173b44d0482b \         # same Ubuntu 22.04 LTS Phase 3 used
    --instance-type t3.small \
    --key-name windy-prod-key \
    --security-group-ids <clone-api-sg> \
    --subnet-id <public-subnet-1b> \
    --iam-instance-profile Name=windy-clone-api \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=windy-clone-api},{Key=Product,Value=windy-clone}]'

aws ec2 allocate-address --domain vpc
aws ec2 associate-address --instance-id <id> --allocation-id <alloc>
```

IAM role `windy-clone-api` gets:
- `secretsmanager:GetSecretValue` scoped to ARNs listed in §5
- `logs:CreateLogStream`, `logs:PutLogEvents` on `/ecs/clone-api` (or just rely on docker CloudWatch driver)
- `s3:*Object` on the R2 bucket via Cloudflare endpoint (R2 IAM is at the CF token layer, not AWS)

### Gate 3 — DNS

```bash
curl -X POST "https://api.cloudflare.com/client/v4/zones/86085f0869c360f79fef22db2b4b9b60/dns_records" \
    -H "Authorization: Bearer $CF_TOKEN" -H "Content-Type: application/json" \
    -d '{"type":"A","name":"clone.windyword.ai","content":"<EIP>","ttl":300,"proxied":false}'
```

Verify: `dig +short clone.windyword.ai` returns the EIP within 60 s.

### Gate 4 — Deploy + TLS + smoke

```bash
# From operator machine:
COPYFILE_DISABLE=1 tar czf clone-bundle.tgz \
    --exclude node_modules --exclude .venv --exclude data \
    Dockerfile pyproject.toml api web uv.lock
scp -i ~/windy-prod-key.pem clone-bundle.tgz ubuntu@<EIP>:/tmp/

# On the EC2 host:
sudo mkdir -p /opt/windy-clone && cd /opt/windy-clone
sudo tar xzf /tmp/clone-bundle.tgz
sudo nano .env   # populate from §5 + .env.production.example template
docker build -t clone-api:wave14 .
docker compose -f docker-compose.prod.yml --env-file .env up -d

# Nginx site + certbot:
sudo nano /etc/nginx/sites-available/clone.windyword.ai   # proxy :443 → 127.0.0.1:8400
sudo ln -s /etc/nginx/sites-available/clone.windyword.ai /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d clone.windyword.ai --non-interactive --agree-tos --email grant@windypro.com
```

**Smoke battery (Gate 4 pass criteria):**

| Probe | Expected |
|---|---|
| `curl https://clone.windyword.ai/health` | 200 `{"status":"healthy"}` |
| `curl -H "Authorization: Bearer <real Pro JWT>" https://clone.windyword.ai/api/v1/preferences` | 200 with `identity_id` matching the JWT's `windyIdentityId` — **regression probe for the JWKS drift fix** |
| `curl https://clone.windyword.ai/api/v1/providers` (unauth'd) | 200 (public endpoint) |
| `POST /api/v1/webhooks/identity/created` with a valid HMAC | 200 or 204 (depends on whether Pro has already subscribed us) |
| `docker logs windy-clone | grep "DEV_MODE"` | no `DEV_MODE is ON` warning — boot guard passed |
| `docker logs windy-clone | grep "UnsafeBootConfig"` | no lines — boot guard passed |

If any row fails, stop. Do **not** update Eternitas subscriber URL (§10) until smoke is green.

## 10. Post-deploy hand-off

- [ ] Update Eternitas subscribers table — `windyclone` → `https://clone.windyword.ai/api/v1/webhooks/eternitas` (currently points at the 404 Cloudflare Pages placeholder `api.windyclone.com/webhooks/eternitas` per prior session notes).
- [ ] Update Pro (`windy-pro/account-server`) subscribers to share `WINDY_PRO_WEBHOOK_SECRET` from §5.
- [ ] Append new values to `/tmp/kit-army-config/ACCESS_LOCKBOX.md` under the Clone section.
- [ ] `memory/reference_windy_clone_repo.md` — bump to note prod host = `https://clone.windyword.ai`.
- [ ] Cloudflare Pages gate on `windyclone.ai` — decide: keep pre-launch Access, or strip it so first external users can hit the dashboard. (Until stripped, real traffic can't reach our origin via the dashboard.)

## 11. Rollback

**DNS-level (fastest, ~60 s):**
```bash
curl -X DELETE "https://api.cloudflare.com/client/v4/zones/.../dns_records/<id>" -H "Authorization: Bearer $CF_TOKEN"
```
Removes the `clone.windyword.ai` record. The dashboard at `windyclone.ai` keeps working because it's on Cloudflare Pages; only the API disappears. Clients see CORS/DNS failures which surface as "API unavailable" banners — preferable to data corruption.

**Container-level (if deploy was bad but infra is fine):**
```bash
docker compose -f docker-compose.prod.yml down
# Revert bundle, rebuild from previous SHA, bring back up.
```

**Data-level (RDS regression):**
- RDS point-in-time restore to a new instance, update `DATABASE_URL` in `.env`, `docker compose restart api`. RTO ~20 min. Budget this if a migration goes wrong.

**Full teardown (unlikely, only if we picked the wrong AZ or SG):**
```bash
aws ec2 terminate-instances --instance-ids <id>
aws ec2 release-address --allocation-id <alloc>
aws rds delete-db-instance --db-instance-identifier clone-db --skip-final-snapshot  # only if data is throwaway
```
Cloudflare DNS record — delete as above. Lockbox — purge the Clone section's Wave 14 values so they're not reused.

## 12. Known gaps carried forward (not Wave 14 blockers)

Same pattern as Phase 3's `Known gaps carried forward` list:

- **Mobile consumer surface** — no mobile app wiring yet. Same as every Wave 13 phase; mobile is post-launch polish.
- **Alembic migrations not bolted on** — Clone uses `create_all` at boot. Wave 15 item: generate the initial Alembic revision and run `alembic upgrade head` as a pre-deploy step.
- **SQS worker split for `run_elevenlabs_pipeline`** — current `BackgroundTask` path pins an API worker for each training job. Fine at <100 orders/day; Wave 15 item.
- **Stripe / payment wiring** — Clone is affiliate-only today. When/if Clone starts charging a markup, add a Stripe handler under `routes/webhooks.py` and provision `clone/prod/stripe` in Secrets Manager.
- **`/health/full` deep probe** — current `/health` is a simple 200. Steal Cloud Phase 3's pattern (DB + Pro JWKS + Eternitas reachability) in a follow-up.
- **CSP / Referrer-Policy / Permissions-Policy headers** — nginx has the four standard headers but not these. Post-launch header polish wave.
- **Pre-launch Cloudflare Access gate on `windyclone.ai`** — left in place during bake-in per §10 decision point.
