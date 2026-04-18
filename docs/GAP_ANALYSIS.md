# GAP ANALYSIS — what's actually broken before launch

**Audit date:** 2026-04-16 · **Audited commit:** `492a781` (+ audit branch `wave-7-gap-analysis`) · **Auditor:** Claude (self-adversarial)

> Phases run: endpoint inventory + curl matrix (1), cross-service probes (2), config/secrets (3), chaos/E2E (4 + 4.5), coverage (5), security posture (6), concurrency torture (7), doc drift (8).

---

## Top 5 things that will surprise Grant most

1. **Auth is effectively disabled by default.** `DEV_MODE=True` is the shipped default. In that mode, `get_current_user` swallows **any** JWT validation failure — including completely bogus tokens — and silently returns the dev mock user. A live-probe confirmed: `Authorization: Bearer junk.junk.junk` → `200 OK`. If a prod deploy forgets to set `DEV_MODE=false`, authentication is a suggestion, not a requirement. (P0 #1)

2. **Three of the four "provider defaults" point at unreachable URLs.** The config defaults for Windy Pro API (`https://api.windypro.com`), the Pro JWKS (`https://windypro.thewindstorm.uk/.well-known/jwks.json` → HTTP 404), and Eternitas prod (`https://eternitas.thewindstorm.uk` → HTTP 000) were probed live — none resolve to a working endpoint. Deploying with defaults means zero auth, zero trust gating, zero data fetch. (P0 #2–#4)

3. **Order creation corrupts state under light concurrency.** 100 parallel `POST /api/v1/orders` → **80% returned 500**, with SQLite `"attempt to write a readonly database"` errors in the log. Worse, some surviving orders triggered the pipeline's race: `"pipeline: order X vanished before training"` — the background task runs before the API's commit has flushed. PostgreSQL will hide the SQLite symptom; the commit/read race will persist. (P0 #5)

4. **Three of five provider adapters are scaffolded stubs.** `HeyGen`, `PlayHT`, `ResembleAI` all return placeholder job IDs (`"hg-job-placeholder"` etc.) from `upload()`. Yet `POST /api/v1/orders` accepts them, creates a DB row, and returns `"Training will begin shortly"`. Users pay (eventually) for orders that silently never run. (P0 #6)

5. **Every upstream client crashes on non-JSON responses.** `data_fetcher`, `trust_client`, and `eternitas.auto_hatch` all do `resp.json()` inside `try: except httpx.HTTPError:`. `json.JSONDecodeError` isn't an `httpx` exception — it escapes, the request 500s. Confirmed live by feeding each client an `<html>not json</html>` body. (P1 #3)

---

## P0 — Ship-blockers

### #1 DEV_MODE default bypass auth silently

**What's broken:** `api/app/config.py:57` — `dev_mode: bool = True`. `api/app/auth/dependencies.py:61` — on any `validate_token` exception, `if settings.dev_mode: return _DEV_USER`. No warning, no log, no header. A bogus or expired token becomes the dev user.

**Repro:**
```bash
curl -H "Authorization: Bearer junk.junk.junk" http://127.0.0.1:18400/api/v1/providers
# → 200 OK, same as an unauthenticated caller
```

**Suggested fix:** default `dev_mode=False`. Require explicit opt-in. Refuse to boot in dev_mode when `ENVIRONMENT=production`. Add a startup log line `"🚨 DEV_MODE is ON — auth is bypassed"` at WARN.

**Code ref:** `api/app/config.py:57`, `api/app/auth/dependencies.py:60–62`

**Estimated effort:** 30 min + deploy-checklist update.

---

### #2 `WINDY_PRO_JWKS_URL` default returns 404

**What's broken:** default `https://windypro.thewindstorm.uk/.well-known/jwks.json` — probed live, returns HTTP 404. `PyJWKClient(...).get_signing_key_from_jwt(token)` will raise `PyJWKClientError` on every validation. Combined with #1, this means the **only** authenticated flow is via the silent dev-user fallback.

**Repro:**
```bash
curl -o /dev/null -w "%{http_code}\n" https://windypro.thewindstorm.uk/.well-known/jwks.json
# → 404
```

**Suggested fix:** either (a) fix the JWKS host, or (b) change the default to an obviously-invalid value like `""` and fail boot if DEV_MODE is false.

**Code ref:** `api/app/config.py:16`

**Estimated effort:** 15 min config change; the underlying Pro JWKS endpoint needs to actually exist.

---

### #3 `WINDY_PRO_API_URL` default unreachable

**What's broken:** default `https://api.windypro.com`. Probed → HTTP 000 (connection refused / no DNS). `data_fetcher` will fall through to the cache, then to `unavailable=True`. No live stats/bundles will ever be fetched in prod unless the env is overridden.

**Repro:** same as #2 — live probe in `docs/audit/curl-matrix.txt`.

**Suggested fix:** same pattern — fail boot when DEV_MODE is off and the URL isn't reachable on startup.

**Code ref:** `api/app/config.py:17`

**Estimated effort:** 15 min.

---

### #4 `ETERNITAS_URL` default points at `http://localhost:8500`

**What's broken:** works in dev against the local seeded instance (confirmed — Wave-5 live tests passed). In prod with the default unchanged, every gated request hits a dead loopback URL and degrades to `UNVERIFIED` → every agent denied. Not corruption — but every agent action blocked.

**Mitigation that exists:** `trust_client` fails closed, so this manifests as `403 TrustGateError` rather than crashes. Still ship-blocker because the intended gating becomes useless.

**Suggested fix:** boot-time sanity ping of `GET {ETERNITAS_URL}/health`. Refuse boot in `ENVIRONMENT=production` when the URL is still `localhost`.

**Code ref:** `api/app/config.py:24`

**Estimated effort:** 30 min.

---

### #5 `POST /api/v1/orders` loses 80% of requests under concurrency

**What's broken:** 100 concurrent calls → 80× `500` + 20× `200`. Root cause: SQLite "attempt to write a readonly database" under lock contention. PostgreSQL in prod will avoid the SQLite-specific symptom, but the secondary bug is real on any backend: the BackgroundTask-spawned `run_elevenlabs_pipeline` races `await db.commit()` and can lose the order row (`pipeline: order ... vanished before training`).

**Repro:** `docs/audit/concurrency-results.md` — `POST /api/v1/orders × 100 → 200:20, 500:80`. Logs show:
```
sqlite3.OperationalError: attempt to write a readonly database
  [SQL: INSERT INTO orders ...]
pipeline: order 02893eb4-... vanished before training
```

**Suggested fix:**
1. On DB write conflicts, return `503 Retry-After: 1` instead of 500.
2. In `run_elevenlabs_pipeline`, sleep briefly or use `SELECT ... FOR UPDATE` semantics before reading the order — the commit may not yet be visible.
3. In staging, run with PostgreSQL to validate that only the race (not the lock contention) remains.

**Code ref:** `api/app/routes/orders.py:48`, `api/app/services/clone_pipeline.py:46`

**Estimated effort:** 2–3 h (includes PG test run and retry middleware).

---

### #6 HeyGen / PlayHT / ResembleAI orders silently never run

**What's broken:** `POST /api/v1/orders` creates a row for any registered provider and returns `"Training will begin shortly"`. Only `provider_id == "elevenlabs"` schedules the pipeline (`routes/orders.py:66`). Orders for other providers sit in `pending` forever.

**Adapter status:**

| Provider | `upload()` | `get_training_status()` | Hooked into orders? |
|---|---|---|---|
| ElevenLabs | real HTTP | real HTTP | ✅ |
| HeyGen | scaffold (returns `"hg-job-placeholder"`) | — | ❌ |
| PlayHT | scaffold (returns `"ph-job-placeholder"`) | — | ❌ |
| ResembleAI | scaffold | — | ❌ |
| Synthesia, D-ID, Tavus | in registry only | — | ❌ |

Coverage report: `heygen.py`, `playht.py`, `resembleai.py` → **0%**. Dead code that the UI advertises as live.

**Repro:**
```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"provider_id":"heygen","clone_type":"avatar"}' \
  http://127.0.0.1:18400/api/v1/orders
# → 200, status=pending, never leaves pending
```

**Suggested fix:** either (a) reject non-ElevenLabs orders with `501 Not Implemented` and set `coming_soon=True` on the provider in the registry, or (b) ship the adapters. Current state — accepting orders you cannot fulfill — is the worst option.

**Code ref:** `api/app/routes/orders.py:66`, `api/app/providers/heygen.py`, `playht.py`, `resembleai.py`

**Estimated effort:** 30 min for option (a); 1–2 days each for option (b).

---

### #7 Soul-file signing key is per-process in a multi-task deploy

**What's broken:** `api/app/auth/signing.py:_load_or_create` generates a brand-new P-256 keypair when the PEM file doesn't exist, then caches it in the process. In ECS Fargate with ≥ 2 tasks (the default for HA per `deploy/aws/CLONE_DEPLOYMENT.md`), each task generates **its own** key on first run. Consumers fetching `/.well-known/soul-signing-keys.json` get whichever task's key, verify against whichever key signed, and fail cross-task.

**Repro:** not reproducible locally (single process) but guaranteed in a multi-task deploy. The deployment doc already calls for the signing key to live in Secrets Manager — the code doesn't load from Secrets Manager yet.

**Suggested fix:** load the PEM from `SOUL_SIGNING_KEY_PATH` but, in prod, mount the Secrets Manager value at that path (ECS `secrets` directive with file-volume mount) or add a `SOUL_SIGNING_KEY_PEM` env var the module reads directly. Refuse boot if neither is set in prod.

**Code ref:** `api/app/auth/signing.py:22–42`

**Estimated effort:** 1 h + deploy-integration.

---

### #8 Pipeline hardcoded to fail every real training request

**What's broken:** `api/app/services/clone_pipeline.py:74–75`:

```python
raise RuntimeError(
    "Windy Pro has not yet exposed bundle audio — submit_training needs real bytes"
)
```

When called from the live path (non-dev, ElevenLabs key set) without explicit `audio_files`, the pipeline raises immediately. The only code path that doesn't raise is the test path that injects `audio_files=[...]`. In prod, every ElevenLabs order will mark `Order.status=FAILED` with this exact string in `error_message`.

**Suggested fix:** wire up a bundle-audio fetch against Windy Pro (or Cloud / R2), or gate the entire `elevenlabs` adapter behind `coming_soon=True` until Pro exposes audio bytes.

**Code ref:** `api/app/services/clone_pipeline.py:66–75`

**Estimated effort:** needs cross-repo (Pro) work — unknowable from Clone alone.

---

## P1 — Fix this week

### #1 No rate limits anywhere

Every endpoint is unbounded from a single IP. `slowapi` not installed, no `Limiter`, no middleware. Impact: webhook endpoints force SHA-256 HMAC on every unsigned request; a single attacker can burn CPU indefinitely. Order creation can be spammed. Trust-API lookups can be chained (each miss → cold Eternitas call).

**Fix:** add `slowapi`, decorate high-risk routes (webhooks: 30 rpm; orders: 10 rpm/user; legacy/stats: 60 rpm/user).

**Code ref:** all of `api/app/routes/`

**Effort:** 2 h.

---

### #2 JWT validation doesn't check `aud` or `iss`

`api/app/auth/jwks.py:43` — `options={"require": ["exp", "sub"]}`. A JWT minted by Windy Pro for any sibling service is silently accepted. If any sibling issues lower-security tokens (e.g., anonymous-ish tokens for a marketing site), Clone inherits them.

**Fix:** add `"verify_aud": True`, `"require": ["exp", "sub", "aud"]`, and pass `audience="windy-clone"`. Coordinate with Pro to include the audience claim.

**Code ref:** `api/app/auth/jwks.py:43`

**Effort:** 1 h Clone-side + Pro-side coordination.

---

### #3 Upstream clients crash on non-JSON responses

Confirmed live — all three upstream-consuming services raise an uncaught `JSONDecodeError` when upstream returns `text/html`:

```
data_fetcher.fetch_recording_stats: CRASH JSONDecodeError: Expecting value...
trust_client.get_agent_trust:       CRASH JSONDecodeError: Expecting value...
eternitas.auto_hatch:               CRASH JSONDecodeError: Expecting value...
```

Cause: `resp.json()` throws `json.JSONDecodeError`, which is not an `httpx.HTTPError` subclass.

**Fix:** broaden the `except` to `(httpx.HTTPError, json.JSONDecodeError)` (or `ValueError`) in all three files.

**Code ref:** `api/app/services/data_fetcher.py:175, 210`, `api/app/services/trust_client.py:185`, `api/app/services/eternitas.py:60`

**Effort:** 15 min + test cases.

---

### #4 `trust.changed` only invalidates one process's cache

`trust_client._cache` is in-process. ECS with 2+ tasks → invalidation hits only the task that receives the webhook; the others keep stale state for up to 5 min. For a band flip from `good → critical`, stale task can still authorize export for that window.

**Fix:** two options — (a) Redis-backed shared cache, (b) fan out the webhook delivery to all tasks via an internal pub/sub, or (c) accept the staleness window and shorten cache TTL to 60 s for `EXPORT_SOUL_FILE_HUMAN` gate.

**Code ref:** `api/app/services/trust_client.py:68–97`

**Effort:** 3 h (Redis) or 30 min (TTL tightening).

---

### #5 BackgroundTask pipeline dies with the task

`run_elevenlabs_pipeline` runs inside the API task's event loop. On graceful shutdown the FastAPI task runs for `stop_timeout=120s`, but a SIGKILL, OOM, or Fargate replacement loses any in-flight pipeline. Orders stay `UPLOADING`/`TRAINING` forever.

**Fix:** add the migrate-and-reap ECS one-off already mentioned in the deployment doc; or move to SQS (Tier-2 of the deploy doc).

**Code ref:** `api/app/routes/orders.py:67`

**Effort:** 4 h (reaper) or 1 day (SQS).

---

### #6 No request size limit

`POST /api/v1/orders` accepts a **10 MB** JSON body in 111 ms. FastAPI default is no limit. An attacker can `POST` arbitrary-size bodies; Uvicorn buffers them.

**Fix:** add `Content-Length` ceiling middleware (4 KB for orders/preferences, 64 KB for webhooks).

**Code ref:** `api/app/main.py`

**Effort:** 45 min.

---

### #7 Soul file is fully built in memory

`services/soul_file.build_soul_file` holds the entire ZIP in `io.BytesIO` and returns bytes. For a clone with dozens of sample WAVs or an included `birth_certificate.pdf`, this will OOM the task.

**Fix:** stream the ZIP via `StreamingResponse`, or off-load to R2 as planned (Wave-7 task in deployment doc).

**Code ref:** `api/app/services/soul_file.py:148–213`

**Effort:** 4 h.

---

### #8 Webhook signatures don't include a timestamp

Any captured valid webhook body can be replayed indefinitely. Impact today is low (handlers are idempotent), but any non-idempotent future handler inherits the hole.

**Fix:** include `X-Windy-Timestamp` + `X-Eternitas-Timestamp` headers in the signed payload; reject > 5 min old. Requires coordination with Pro and Eternitas.

**Code ref:** `api/app/routes/webhooks.py:27–35`

**Effort:** 1 h Clone-side + 2–4 h across senders.

---

## P2 — Polish

### #1 Dead code: `job_tracker.py` + `packager.py`

Neither file is imported anywhere. Both have 0% coverage. They pull in `HeyGenProvider`, `PlayHTProvider`, `ResembleAIProvider` — which themselves have 0% coverage.

**Fix:** delete both files, or finish wiring them.

**Code ref:** `api/app/services/job_tracker.py`, `api/app/services/packager.py`

**Effort:** 30 min to delete; days to finish.

---

### #2 `/api/v1/clones/{id}/preview` returns a fake response

`routes/clones.py:118` — returns `{"status":"preview_generation_scaffolded","message":"Preview generation will be available once provider adapters are fully wired."}`. Visible to users, advertised by the OpenAPI schema.

**Fix:** either implement, or return `501 Not Implemented`.

**Code ref:** `api/app/routes/clones.py:97–117`

**Effort:** 30 min for 501; 1 day to implement properly.

---

### #3 `/api/v1/clones/{id}/download` returns a fake response

Same pattern — scaffolded placeholder.

**Code ref:** `api/app/routes/clones.py:119–140`

---

### #4 `DASHBOARD_URL` used but missing from `.env.example`

`config.py:21` reads `dashboard_url`. The `.env.example` template doesn't list it. New deploys default to `https://windyclone.com` without operators realising.

**Fix:** add `DASHBOARD_URL=` to `.env.example` with a comment pointing to where it's consumed.

**Effort:** 2 min.

---

### #5 CORS default includes `http://localhost:5173`

`config.py:48` — `cors_origins: str = "https://windyclone.com,http://localhost:5173"`. Development origin in the prod default. Combined with `allow_credentials=True`, a phished user running a local dev server could send credentialed requests.

**Fix:** separate `CORS_ORIGINS_DEV` / `CORS_ORIGINS_PROD`, or drop localhost from the default and require explicit env override.

**Code ref:** `api/app/config.py:48`

**Effort:** 30 min.

---

### #6 Inter-replica trust-cache drift

Two ECS tasks will reach different gate decisions on the same passport for up to 5 minutes. Covered by P1 #4.

---

### #7 `GET /api/v1/legacy/stats` p95 = 1.2 s in dev

Even with `dev_mode=True` (no HTTP), the legacy/stats handler takes > 1 s under 100 parallel requests. Root cause likely `get_db` creating a fresh engine connection and pyjwt key-load overhead.

**Fix:** profile; likely need connection pooling tuned.

**Code ref:** `api/app/routes/legacy.py`, `api/app/db/engine.py`

**Effort:** 3 h.

---

### #8 Write-through cache race

`services/data_fetcher._write_cache` does `SELECT → INSERT/UPDATE`. Two concurrent fetches for the same `identity_id` with no cache row race the check-then-act. The second one hits `UNIQUE` constraint → propagates up to the caller.

**Fix:** `INSERT … ON CONFLICT DO UPDATE` (PG) or upsert semantics via SQLAlchemy dialect-specific construct.

**Code ref:** `api/app/services/data_fetcher.py:135–152`

**Effort:** 45 min.

---

## P3 — Nice-to-have

### #1 `/docs`, `/openapi.json`, `/redoc` exposed in prod

Public by default. Reveals full schema + operation IDs + internal structure to anyone.

**Fix:** gate behind `DEV_MODE` or a service token.

**Effort:** 15 min.

---

### #2 Deployment doc references unimplemented `/.well-known/soul-signing-keys.json`

Flagged in the PR as "Wave-7 work, not yet built". If not built soon, the rotation runbook can't execute.

**Effort:** 2 h.

---

### #3 `INTEGRATION_GUIDE.md` mixes Clone-own and Clone-consumes endpoints

Paths like `/api/v1/compute/clone-training` and `/api/v1/storage/files/{model_id}` aren't Clone-owned — they're speculative upstream contracts. A reader skimming might mistake them for Clone endpoints.

**Fix:** label each section with the owning service.

**Effort:** 20 min.

---

### #4 `ETERNITAS_USE_MOCK=true` would silently treat all agents as `TOP_SECRET`

Default is `false` so this is dormant, but an operator who flips it for debugging and forgets ends up with a wide-open gate. Add a startup WARN log that includes the mock state.

**Effort:** 5 min.

---

### #5 Unit-test DB pollution

Tests use a shared SQLite file and rely on UUIDs for isolation. One bad fixture and we get cascading failures. Future deterministic testing would prefer in-memory `sqlite://` per test.

**Effort:** 1 h.

---

## Counts

| Severity | Count |
|---|---|
| P0 | 8 |
| P1 | 8 |
| P2 | 8 |
| P3 | 5 |
| **Total** | **29** |

---

## What I didn't test / where I'm NOT confident

- **The web/ frontend.** I probed the API only. The Studio marketplace UI, every provider card, every detail page, every filter — un-tested. The CLAUDE.md says "Build the frontend first with mock data, then wire to the existing API" so a separate frontend audit is warranted before launch.
- **Auth against a real Windy Pro JWT.** I verified the dev-mode bypass live; I did NOT exercise the RS256 path against a valid signed token because the JWKS URL 404s. Everything behind a live-Pro JWT (audience, custom claims, expiry edge cases) is un-tested.
- **TLS, WAF, load balancer behaviour in prod.** Local probes only.
- **Actual ElevenLabs API behaviour.** Every test mocks `httpx`. The real `/v1/voices/add` could reject our multipart shape; untested against the real API.
- **Dependency chain.** No `pip-audit` / `safety` run. If `pyjwt` / `cryptography` / `httpx` have known CVEs at pinned versions, I don't see them.
- **Long-running pipeline under real ElevenLabs timings.** My mocks return instantly; the pipeline in prod will hold a task for 5–15 min per ElevenLabs completion poll.
- **Load over sustained traffic.** 100 parallel is a spike; a sustained 10 rps for 30 min would reveal connection-pool exhaustion, DB vacuum pressure, httpx client reuse issues — untested.

---

## Reproduction artefacts

- `docs/audit/endpoint-inventory.txt` — 20 routes with method, path, handler, auth deps.
- `docs/audit/curl-matrix.txt` — 20 probe scenarios, response codes, latencies.
- `docs/audit/concurrency-results.md` — 100× storm at 3 endpoints, p50/p95/p99.
- `docs/audit/security-posture.md` — CORS, rate limits, JWT, SQLi, XSS, SSRF, redirect, webhook replay.

---

_No P0 fix was landed in this PR — per the phase-10 instruction I prioritised coverage of issues over patching. Follow-up PRs per the branching policy._
