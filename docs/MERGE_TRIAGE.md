# Wave-7 PR Merge Triage — Windy Clone

**Generated:** 2026-04-17 · **Queue size:** 15 open PRs (#2–#16) · **Total diff:** +2,812 / −295 (3,107 lines touched, 2,517 net).

Buckets below classify by blast radius, not by severity of the original bug. A P0 fix can still be bucket A if the code path is tiny and reversible.

---

## Bucket A — MERGE NOW (4 PRs, +980/−19)

Pure-fix or docs. No user-visible behavior change for honest callers. Safe to land without a smoke test beyond CI.

- **[#2](https://github.com/sneakyfree/Windy-Clone/pull/2) — GAP ANALYSIS + audit artefacts** (+644/−0). Documentation only. Lands `docs/GAP_ANALYSIS.md`, `docs/audit/*`. Zero code.
- **[#8](https://github.com/sneakyfree/Windy-Clone/pull/8) — P1 #3 upstream JSON tolerance** (+86/−4). Single line per file: widen `except httpx.HTTPError` → `(httpx.HTTPError, ValueError)`. Three service files. Degrades instead of crashing — strictly better.
- **[#14](https://github.com/sneakyfree/Windy-Clone/pull/14) — P2+P3 housekeeping bundle** (+89/−208). Dead code deletion, `/preview`+`/download` → 501 (previously returned 200 with `"scaffolded"` placeholders that no frontend consumed), `/docs` gated to dev_mode, CORS localhost dropped, `DASHBOARD_URL` into `.env.example`. Net negative lines.
- **[#16](https://github.com/sneakyfree/Windy-Clone/pull/16) — P2+P3 final bundle** (+161/−11). Cache-race upsert retry, `INTEGRATION_GUIDE` ownership labels, `ETERNITAS_USE_MOCK=true` startup WARN. No behavior change for the happy path.

## Bucket B — SAFE-MERGE-WITH-SMOKE (7 PRs, +1,191/−25)

Real behavior change but well-tested, reversible via env var or straightforward revert, no secret/identity material touched. Smoke check the named happy paths post-merge.

- **[#3](https://github.com/sneakyfree/Windy-Clone/pull/3) — P0 #1–4 DEV_MODE + boot guards** (+162/−4). Flips `DEV_MODE` default to `False`. Local dev keeps working because `.env.example` sets it to `true` explicitly. Smoke: boot with `ENVIRONMENT=production` unset-`DEV_MODE` → confirms it refuses boot; then set env correctly → confirms it boots.
- **[#4](https://github.com/sneakyfree/Windy-Clone/pull/4) — P0 #6 reject scaffolded providers** (+55/−7). HeyGen/PlayHT/ResembleAI/Synthesia/D-ID/Tavus orders return 501 instead of stuck `pending`. Smoke: submit an ElevenLabs order (still 200) and a HeyGen order (501).
- **[#6](https://github.com/sneakyfree/Windy-Clone/pull/6) — P0 #8 `AWAITING_UPSTREAM` status** (+171/−7). New `OrderStatus` enum value; existing consumers receive a string value (additive, not breaking). Smoke: verify `GET /api/v1/orders/{id}` still returns the expected shape.
- **[#7](https://github.com/sneakyfree/Windy-Clone/pull/7) — P0 #5 503 handler + pipeline retry** (+197/−4). Adds exception handler for `OperationalError`, adds retry loop to pipeline. No change for non-contended requests. Smoke: 503 path is covered by test; the happy path is unchanged.
- **[#9](https://github.com/sneakyfree/Windy-Clone/pull/9) — P1 #6 request body cap** (+87/−0). 64 KB default ceiling, configurable. Smoke: normal POST works; 10 MB POST → 413.
- **[#10](https://github.com/sneakyfree/Windy-Clone/pull/10) — P1 #5 order reaper** (+181/−0). Startup-only sweep that un-parks orphaned `UPLOADING`/`TRAINING` orders. Zero impact on request path. Smoke: boot and verify startup log line.
- **[#11](https://github.com/sneakyfree/Windy-Clone/pull/11) — P1 #1 rate limits** (+243/−0). Per-IP middleware. Default caps are generous for honest traffic (10 rpm orders, 120 rpm general). Smoke: confirm normal UI usage doesn't 429; a 20-req burst on `/api/v1/orders` should 429 on the 11th.

## Bucket C — HIGH-RISK-NEEDS-EYES (4 PRs, +736/−50)

Touches auth, crypto, or webhook signatures. Review the diff end-to-end; don't trust green CI alone.

- **[#5](https://github.com/sneakyfree/Windy-Clone/pull/5) — P0 #7 signing key from env** (+171/−27). Changes how the soul-file ES256 key is loaded. Critical: a bug here means consumers stop trusting Clone's signatures. Verify: env var source wins over file, dev auto-gen still works, prod refuses auto-gen.
- **[#12](https://github.com/sneakyfree/Windy-Clone/pull/12) — P1 #4 trust cache bypass for TOP_SECRET gate** (+155/−8). Changes gate-enforcement code path. Bug here = either silent privilege elevation (if bypass fails to fire) or extra Eternitas load (if it over-fires). Verify the `_CACHE_BYPASS_ACTIONS` set.
- **[#13](https://github.com/sneakyfree/Windy-Clone/pull/13) — P1 #2 JWT aud/iss verification** (+145/−9). Ships off by default (`JWT_AUDIENCE=""`), so landing is safe. The actual behavior flip happens when prod sets `JWT_AUDIENCE=windy-clone`. Verify the decode-kwargs plumbing is right before Pro ships the matching `aud` claim.
- **[#15](https://github.com/sneakyfree/Windy-Clone/pull/15) — P1 #8 timestamped webhook HMAC** (+265/−6). Changes webhook signature verification. Backward-compatible by default (legacy body-only HMAC still accepted). `WEBHOOK_REQUIRE_TIMESTAMP=true` is the strict flip — coordinate with Pro/Eternitas before enabling. Review the `_verify_hmac` + `_check_timestamp_freshness_or_403` pair; freshness window is symmetric (abs(now−ts) ≤ 300s).

## Bucket D — BLOCKED-ON-DECISION (0 PRs)

None. Every PR in the queue merges as-is without a Grant decision. The follow-on operational flips are captured in each PR's notes:

- #3 — deploy must set `ENVIRONMENT=production`, `DEV_MODE=false`, and real `WINDY_PRO_*` / `ETERNITAS_URL` values (already in `deploy/aws/CLONE_DEPLOYMENT.md`).
- #5 — deploy must inject `SOUL_SIGNING_KEY_PEM` from Secrets Manager.
- #13 — Pro must mint `aud` before Clone sets `JWT_AUDIENCE`.
- #15 — Pro + Eternitas must ship timestamp headers before Clone sets `WEBHOOK_REQUIRE_TIMESTAMP=true`.

## Bucket E — DEFER (0 PRs)

Nothing in the queue is pure P3 polish. The P2/P3 housekeeping items are bundled into #14 and #16 alongside more material fixes — worth landing them together rather than deferring the whole bundle.

---

## TOP 3 MUST-MERGE BEFORE LAUNCH

1. **[#3](https://github.com/sneakyfree/Windy-Clone/pull/3) — DEV_MODE default + boot guards (P0 #1–4).** Without this, a prod deploy that forgets `DEV_MODE=false` silently accepts any bogus Bearer token as the dev mock user. Live-proved in the audit: `curl -H "Authorization: Bearer junk.junk.junk"` returns 200. Every endpoint behind `get_current_user` is wide open until this lands.

2. **[#5](https://github.com/sneakyfree/Windy-Clone/pull/5) — Signing key from env (P0 #7).** Without this, every ECS task generates its own ES256 keypair on first soul-file export. The deploy doc mandates ≥2 tasks for HA — consumers verifying a soul file against `/.well-known/soul-signing-keys.json` will see one fingerprint or the other depending on which task served them, and verification will fail for everyone ~half the time. Breaks the core soul-file trust story.

3. **[#11](https://github.com/sneakyfree/Windy-Clone/pull/11) — Rate limits (P1 #1).** Without this, a single unauthenticated attacker can force SHA-256 HMAC on every `/webhooks/*` request indefinitely, and unbounded order submission is free. Live-proved: 100 parallel `POST /api/v1/orders` handled in 3.7s with zero back-pressure. First public URL = first abuse vector.

Runner-up: [#4](https://github.com/sneakyfree/Windy-Clone/pull/4) — without it, users who pick HeyGen / PlayHT / ResembleAI / Synthesia / D-ID / Tavus in `/studio` get orders accepted and silently stuck in `pending` forever. High user-pain but only affects non-default providers; ElevenLabs still works without it.

---

## Suggested merge sequence

Optimises for minimum rebase pain given the overlapping file touches:

1. #2 (docs only, no conflicts)
2. #3 (biggest base — `config.py` + `main.py` + `conftest.py`)
3. #8 (three services, no overlap)
4. #12 (trust_client.py alone)
5. #5 (config.py + signing.py)
6. #9 (config.py + main.py)
7. #11 (main.py + new `middleware/`)
8. #10 (main.py + new `order_reaper`)
9. #7 (main.py exception handler + clone_pipeline.py)
10. #6 (clone_pipeline.py — trivial merge with #7)
11. #4 (orders.py + registry)
12. #14 (cross-file housekeeping)
13. #15 (webhooks.py + config.py)
14. #13 (jwks.py + config.py + .env.example)
15. #16 (INTEGRATION_GUIDE + main.py + data_fetcher.py)

After #3 and #5 land, items #4, #6, #10, #11 can parallelise.
