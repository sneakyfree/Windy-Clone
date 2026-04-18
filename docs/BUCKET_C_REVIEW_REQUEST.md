# Bucket C — Review Request

Four PRs in the Wave-7 queue touch auth, crypto, or webhook signatures. They passed their own test suites and are structurally sound, but the blast radius on a bug is large enough that green CI alone isn't enough. Grant (or an equivalent second set of eyes) to review the diff before merge.

All four PRs are rebased on top of the post-Bucket-B `main` and mergeable cleanly as of 2026-04-17.

---

## PR [#5](https://github.com/sneakyfree/Windy-Clone/pull/5) — P0 #7: Signing key from env + refuse auto-gen in prod

**Why it's high-risk.** Changes how the ES256 soul-file signing key is loaded. A bug here means consumers (Mail, Fly, Eternitas, future external platforms) stop trusting Clone-signed soul files — or, worse, trust a forged one if the load path picks up an attacker-controlled PEM. This PR is how the fleet's signing identity becomes singular across replicas instead of per-task-forked.

**What specifically needs eyes.**
- `api/app/auth/signing.py:_load_or_create` — resolution order is `SOUL_SIGNING_KEY_PEM` env → `SOUL_SIGNING_KEY_PATH` file → dev-only auto-gen. Verify an operator who accidentally sets *both* doesn't end up in a confused state (current behaviour: env wins, silently).
- The `dev_mode=False` refusal path raises `MissingSigningKey`. Confirm the exception surfaces cleanly on boot — it should, because signing is lazy and only invoked on first soul-file export, but that means a broken config only surfaces the first time a user clicks "export".
- `.env.example` adds the new var but not its preferred value (intentional — prod gets it from Secrets Manager).

**Smoke test post-merge.**
1. Boot with `DEV_MODE=true`, no env var, no PEM on disk → first `/export-soul-file` call auto-generates and succeeds.
2. Boot with `DEV_MODE=false` + `SOUL_SIGNING_KEY_PEM` set to a valid PEM → export succeeds; inspect the ZIP's `signature.json.fingerprint_sha256` matches `sha256(DER(public_key))`.
3. Boot with `DEV_MODE=false` and neither env nor file → first export returns 500 with `MissingSigningKey`. Fix by setting the env.
4. Run the existing soul-file ES256 verification test (`test_build_soul_file_structure_and_signature`) to confirm signatures still verify against the published public key.

---

## PR [#12](https://github.com/sneakyfree/Windy-Clone/pull/12) — P1 #4: `EXPORT_SOUL_FILE_HUMAN` bypasses the trust cache

**Why it's high-risk.** Changes the gate-enforcement path for the single most sensitive action in the service (exporting a portable, signed copy of human voice/avatar data). A bug that makes the bypass *fail to fire* silently re-opens the stale-cache privilege-elevation window. A bug that makes it *over-fire* adds cold Eternitas load but doesn't hurt correctness — still worth noticing.

**What specifically needs eyes.**
- `_CACHE_BYPASS_ACTIONS = {EXPORT_SOUL_FILE_HUMAN}` in `trust_client.py`. If a future gate should join the set, the change is one line; review whether the rationale is clearly enforced.
- `enforce_gate` now calls `get_agent_trust(passport, bypass_cache=True)` for the bypass set. Confirm the underlying `invalidate(passport)` + fresh fetch is atomic — there's a small window where a concurrent webhook could flip state between the invalidate and the fetch. Trust API is idempotent so this is fine, but flag if the review disagrees.
- `test_stale_cache_doesnt_let_revoked_passport_export` is the critical test — it pins the failure mode this PR exists to prevent.

**Smoke test post-merge.**
1. With live Eternitas at `localhost:8500` and seeded passports: an agent with `ET26-TEST-EXCP` passes `/export-soul-file`. Immediately revoke the passport in Eternitas (or point at `ET26-TEST-REVD`), retry — must 403 within one request, not after 5 min.
2. Repeat for `SUBMIT_CLONE_ORDER` (non-bypass gate) — cached state should still be honoured for ~5 min.

---

## PR [#13](https://github.com/sneakyfree/Windy-Clone/pull/13) — P1 #2: Optional JWT audience / issuer verification

**Why it's high-risk.** Changes `validate_token`, the central auth primitive. Ships off by default (`JWT_AUDIENCE=""`) so landing is safe today, but the behavioural flip happens when prod sets `JWT_AUDIENCE=windy-clone`. A bug in the kwargs plumbing would either silently accept cross-service tokens even when `JWT_AUDIENCE` is set (fail-open) or reject every real Pro-minted JWT (fail-closed, total lockout).

**What specifically needs eyes.**
- `api/app/auth/jwks.py:validate_token` — the `decode_kwargs` dict is conditionally populated with `audience` / `issuer`. Verify the `options.require` list correctly adds `aud` / `iss` in lockstep so PyJWT complains loudly on a missing claim (not just a wrong one).
- Confirm the test suite's `_FakeClient` correctly exercises the audience path — tests use PyJWT's own `InvalidAudienceError` / `MissingRequiredClaimError` which means the library is making the decision, not our wrapper.

**Smoke test post-merge.**
- Landing this PR with `JWT_AUDIENCE=""` changes nothing user-visible. The smoke that matters happens when Pro ships the `aud` claim:
  1. Pro mints a token with `aud: "windy-clone"` — Clone with `JWT_AUDIENCE=windy-clone` accepts it.
  2. A Mail-audience token (`aud: "windy-mail"`) hitting Clone's endpoint → 401.
- Until then, existing tokens keep working.

---

## PR [#15](https://github.com/sneakyfree/Windy-Clone/pull/15) — P1 #8: Timestamped webhook HMAC with backward-compatible rollout

**Why it's high-risk.** Changes webhook signature verification — the boundary where Pro and Eternitas trust us and we trust them. Backward-compatible by default (legacy body-only HMAC still accepted) so landing is safe, but the strict flip (`WEBHOOK_REQUIRE_TIMESTAMP=true`) only makes sense once every sender has adopted the new scheme. A bug in the verifier means either legitimate webhooks start failing or replay attacks still succeed.

**What specifically needs eyes.**
- `_verify_hmac` in `routes/webhooks.py` — tries timestamped HMAC first when the header is present, falls back to legacy body-only. Verify the fallback is gated by `webhook_require_timestamp`.
- `_check_timestamp_freshness_or_403` — freshness window is symmetric (`abs(now - ts) ≤ max_age`). Future-dated timestamps are rejected too; confirm we're OK with failing a sender whose clock skews by more than 5 minutes (intentional; clock-skew alarms should handle that).
- Both `/identity/created` and `/trust/changed` handlers updated — confirm the header names (`X-Windy-Pro-Timestamp` / `X-Eternitas-Timestamp`) match what Pro and Eternitas intend to send.

**Smoke test post-merge.**
1. Existing behaviour: send an `identity.created` webhook with just `X-Windy-Pro-Signature: <body-hmac>` — accepts (legacy path).
2. Timestamped path: send with `X-Windy-Pro-Timestamp: <now>` and `X-Windy-Pro-Signature: hmac("{ts}.{body}")` — accepts.
3. Replay attempt: take yesterday's valid delivery and resend verbatim → 403 (freshness check catches it).
4. After Pro + Eternitas both ship the timestamp header, flip `WEBHOOK_REQUIRE_TIMESTAMP=true` in prod and re-run the smoke. Legacy-only senders now 403 — confirm nobody's still on the old scheme before flipping.

---

## Merge order (once reviewed)

They're all rebased onto current `main` and mutually non-conflicting. Suggested sequence for clean diff trails:

1. #12 — smallest, trust_client.py only
2. #13 — jwks.py + config.py, independent
3. #5 — auth/signing.py + config.py, independent of trust and JWT
4. #15 — webhooks.py + config.py, independent of the above

All four can land on the same day after review. No staging dependency on the rest of the Wave-7 queue (those already merged in Buckets A+B).
