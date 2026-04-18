# Wave 11 — windy-clone Adversarial Hardening Report

**Date:** 2026-04-18
**Branch:** `wave11/hardening`
**Repo:** `/Users/thewindstorm/windy-clone`
**Tester:** Claude Opus 4.7 (agent session)

---

## TL;DR

Ten adversarial probes were run against a freshly booted windy-clone stack
(API on :8400, Vite on :5173, DEV_MODE=true, no provider API keys, no
Eternitas). One **HIGH** severity regression was found — the Wave-8
`?wc=` deep-link entry point is broken for its primary landing path.
One **MEDIUM** — ElevenLabs orders silently stay `pending` forever in
dev mode. Everything else that I could exercise without real provider
credentials or a live Eternitas passed cleanly.

### Findings by severity

| ID   | Severity | Area                            | Status   |
| ---- | -------- | ------------------------------- | -------- |
| H-1  | **HIGH** | Deep-link gateway (`?wc=` on `/`) | Confirmed |
| M-1  | MEDIUM   | Pipeline dev-mode silent drop   | Confirmed |
| L-1  | LOW      | Soul-file sample.wav stub       | Cosmetic |
| B-1  | BLOCKED  | ElevenLabs real order           | Missing key |
| B-2  | BLOCKED  | Eternitas passport mint (live)  | Service not up |
| B-3  | BLOCKED  | OS-level `open windyclone://`   | No GUI session |

### What passed (8/10 probes)

- Auth — DEV_MODE mock-user fallback works as documented.
- Deep-link resolver API — 4/4 valid URLs → 200 with correct route, 7/7 malicious → 400.
- Deep-link gateway from non-`/` landings — `/legacy?wc=…` and `/discover?wc=…` route correctly.
- Stubbed providers (HeyGen, PlayHT, Resemble AI) — each returns 501 with a user-legible message; no 500s.
- Concurrent-order stress — 5 simultaneous POSTs all accepted with unique UUIDs, persisted, surfaced in the list endpoint.
- Pro data-fetch failure modes — 5/5 failure scenarios (connect error, 401, 500, malformed body, timeout) produce `unavailable=True` envelope, no crash.
- Soul-file export — produces a real ES256-signed ZIP with 6 members (manifest, voice model, sample.wav, transcripts.ndjson, birth_certificate.pdf, signature.json).
- UI render — all 6 pages (Legacy, Discover, Studio, MyClones, Settings, root redirect) render cleanly under headless Chromium.

### Environment constraints

Testing was performed in an automated shell session. The following checks could not be run directly and are marked as **BLOCKED** rather than **PASS/FAIL**:

- No real ElevenLabs / HeyGen / PlayHT / Resemble AI API keys were present in `.env` — all provider key env vars are empty strings. A live end-to-end training order against any provider is therefore not exercisable. What *was* exercised: the stubbed-provider 501 path and the dev-mode short-circuit.
- The local Eternitas service (`/Users/thewindstorm/eternitas`) requires a Postgres + Redis docker stack (`scripts/dev-start.sh`) and was not brought up. The adversarial-informative scenario *Eternitas is unreachable* was exercised indirectly via unit tests (`test_upstream_non_json.py` / `test_pipeline_awaiting_upstream.py`), which cover `EternitasHatchError` → graceful passport-less Clone persistence.
- The OS-level `open windyclone://discover` probe in the prompt needs a GUI-attached browser. The functionally equivalent code path — the web-side `?wc=<url>` gateway — was exercised via headless Chromium (screenshots 07–11), and separately via the backend resolver API.
- Playwright was installed fresh as part of this session (no chromium on the host at start); this is part of why the browser walkthrough runs headless only.

---

## Stack state during the run

```
windy-pro (account-server, node)  :8098   ✓ healthy, JWKS serving
windy-clone (uvicorn)             :8400   ✓ booted via `nohup .venv/bin/uvicorn …`
windy-clone (vite)                :5173   ✓ booted via `cd web && npm run dev`
eternitas                          —      ✗ not up (postgres+redis stack not started)
```

`.env` settings: `DEV_MODE=true`, `ENVIRONMENT=development`,
`WINDY_PRO_JWKS_URL=https://windypro.thewindstorm.uk/.well-known/jwks.json`
(remote placeholder, not local :8098), `ETERNITAS_URL=http://localhost:8500`
(unreachable), every `*_API_KEY` blank.

Post-relocation actions before testing:

```bash
rm -rf .venv && uv venv && uv pip install -e ".[dev]"
```

One side effect surfaced on first API boot attempt: a silent `uvicorn` exit
code 0 with zero log output. Root cause was a stale uvicorn already bound
to :8400 from the previous Wave-10 session; `ERROR: [Errno 48] error while
attempting to bind on address ('127.0.0.1', 8400): address already in use`
only showed after I piped through `nohup`+`disown`. Not a defect, but worth
noting for anyone reproducing the walkthrough.

---

## H-1 (HIGH) — `?wc=` deep-link broken at `/` landing

### Symptom

All three `?wc=…` probes that landed on `/` ended up on `/legacy` regardless of the deep link target.

```
/?wc=windyclone://discover              → /legacy   ✗ (expected /discover)
/?wc=windyclone://order/abc-123         → /legacy   ✗ (expected /order/abc-123)
/?wc=windyclone://studio/../../etc/passwd → /legacy   ✓ (traversal correctly dropped)
```

Screenshots: `docs/hardening/screenshots/07-deeplink-discover.png`,
`08-deeplink-order.png`, `09-deeplink-traversal-dropped.png` — all three
show the Legacy hero, not the intended target page.

Manifest: `docs/hardening/screenshots/_manifest.json` records `finalUrl` for each.

### Proof it's path-specific, not a gateway bug

Two follow-up probes hit landings that aren't the redirect:

```
/legacy?wc=windyclone://discover        → /discover  ✓
/discover?wc=windyclone://order/ord_42  → /order/ord_42 ✓
```

Screenshots 10-deeplink-from-legacy.png and 11-deeplink-from-discover.png
confirm the gateway itself works — the failure is scoped to one route.

### Root cause

`web/src/App.tsx`:

```tsx
<DeepLinkGateway />
<Routes>
  <Route path="/" element={<Navigate to="/legacy" replace />} />
  …
</Routes>
```

The `<Navigate>` element executes synchronously during render when the user lands on `/`, before `DeepLinkGateway`'s `useEffect` runs. React Router's `Navigate` with a bare `to="/legacy"` does not preserve the source location's `search`, so by the time the gateway inspects `window.location.search` on mount the query string is already gone.

### Why this matters

This is the *primary documented entry point* for the Wave-8 deep-link scheme:

- Recommended in `DEPLOY.md` for the Electron shell and the agent.
- The protocol-handler registration installed by `DeepLinkGateway` itself (`navigator.registerProtocolHandler('web+windyclone', …)`) points at `${origin}/?wc=%s` — i.e. always lands on `/`.

Every caller that follows the documented contract is silently dropped on Legacy with no indication their deep link was discarded.

### Suggested fix (not part of this PR)

Three viable approaches, least invasive first:

1. **Preserve the search in `<Navigate>`** — replace the root redirect with one that includes `search: window.location.search`. The gateway's existing mount-time logic then kicks in at `/legacy` and navigates onward. One-line change.
2. **Run the gateway synchronously at module load** — capture `?wc=` before React mounts, stash it in a module-level var, and have `DeepLinkGateway` read from that instead of `window.location.search`. Avoids any router-ordering assumptions.
3. **Move the `?wc=` unwrap into the `/` route element** — render a tiny `<RootDeepLinkUnwrap />` that does the same work as the current gateway, and fall back to `<Navigate to="/legacy" replace />` if no `?wc=`.

Option 1 is the smallest diff and also the most defensible — it keeps the behaviour "query params are carried through the root redirect" which is closer to what a user would expect from an HTTP-style redirect anyway.

---

## M-1 (MEDIUM) — ElevenLabs orders silently pend forever in dev mode

### Symptom

All 5 concurrent-stress ElevenLabs voice orders were accepted with 200 + unique UUIDs, persisted, and appear in `/api/v1/orders` with `status: "pending"`. They *never advance* — no `uploading`, no `awaiting_upstream`, no `failed`, no `error_message`. Screenshot `05-my-clones.png` shows the UI result: four ElevenLabs voice-twin rows, all "Pending 0%", no status copy about why.

### Root cause

`api/app/services/clone_pipeline.py:80-82`:

```python
if settings.dev_mode or not settings.elevenlabs_api_key:
    logger.info("pipeline: skipping live training for order %s (dev or missing key)", order_id)
    return
```

The pipeline short-circuits *without* updating the order row. The order stays at `status=pending, progress=0, error_message=None` for the rest of time (or until the order_reaper sweeps).

### Why this is a finding

- Adversarial user in dev mode submits an order → it looks accepted → the UI shows it "Pending" forever → user assumes the service is broken. There's no "this is dev mode" hint, no `awaiting_upstream` fallback, no failure state.
- In prod with `DEV_MODE=false` but a missing `ELEVENLABS_API_KEY`, the exact same silent pend happens. Prod environments where ops forgets to wire the secret get the *same* silent-hang behaviour. The boot guards in `api/app/main.py:_enforce_boot_guards` don't catch this — they only guard the Pro/Eternitas URLs, not provider keys.

### Suggested fix (not part of this PR)

Set the order row to a dedicated status *or* `awaiting_upstream` with a clear `error_message` before returning. Something like:

```python
if settings.dev_mode:
    order.status = OrderStatus.AWAITING_UPSTREAM.value
    order.error_message = "Dev mode — training skipped. Set DEV_MODE=false + a real ELEVENLABS_API_KEY to run training."
    await db.commit()
    return
if not settings.elevenlabs_api_key:
    order.status = OrderStatus.FAILED.value
    order.error_message = "ELEVENLABS_API_KEY is not configured on this Windy Clone deployment."
    await db.commit()
    return
```

Optionally, tighten the boot guards in prod to refuse boot when `ENVIRONMENT=production` and no provider API key is set for any provider whose `coming_soon=false`.

---

## L-1 (LOW, cosmetic) — Soul-file sample.wav is a 46-byte stub

The export endpoint returns a real, signed ZIP — that part is fine. But the `voice/sample.wav` member is 46 bytes, which is a bare WAV header with no audio. The seeded test Clone had no provider-returned audio bytes, so this is almost certainly expected behaviour of `services/soul_file.build_soul_file` when called on a clone row that wasn't produced by a live pipeline.

Noting here so no-one re-discovers it: *if* a real ElevenLabs result-fetch ever wires the audio bytes in (and the seeding tests don't follow), the stub sample.wav in production would be a real bug. For now it's just a seed-fixture artifact.

Screenshot / artifact: `docs/hardening/artifacts/soul_file_export.txt`.

---

## Probe-by-probe results

### 1. Auth

`GET /api/v1/preferences` with no `Authorization` header in `DEV_MODE=true` → `200 { identity_id: "dev-mock-user-001", … }`.

`api/app/auth/dependencies.py:51` branch takes the dev fallback only when the header is missing. Supplying a garbage Bearer token would go down the JWKS validation path. Not re-exercised against the live Pro JWKS in this session because the `.env` points at `windypro.thewindstorm.uk` which is a placeholder; DNS + TLS status there is out of scope for Clone-side hardening.

**Verdict:** PASS (dev fallback) / NOT TESTED (live JWKS).

### 2. Legacy page render

Screenshot `02-legacy.png`: hero copy, 4-card stats grid, readiness gauges section all render. Stats values reflect the `_MOCK_STATS` in `api/app/services/data_fetcher.py:66` — this is expected in DEV_MODE (the service short-circuits the Pro fetch and returns mock). Numbers visible in the screenshot (720,199 words etc.) differ from the raw mock (847,293) because `StatCard` animates from 0 to the target and the screenshot was captured mid-animation.

**Verdict:** PASS.

### 3. Discover page render

Screenshot `03-discover.png`. Discover renders *experience* cards (Voice Twin / Digital Avatar / Soul File), not provider cards. Provider cards live on `/studio` (screenshot `04-studio.png`, which shows Windy Clone Native, ElevenLabs, HeyGen, PlayHT, Resemble AI, Synthesia — six tiles, four of which have `coming_soon=true` per `/api/v1/providers` — artifact `providers.json`).

`coming_soon` flags match the adapter registry:

| Provider         | UI says       | Registry `coming_soon` | Order POST status |
| ---------------- | ------------- | ---------------------- | ----------------- |
| Windy Clone Native | Coming Soon | true                   | (not tested — not in prompt)  |
| ElevenLabs       | wired         | false                  | 200 (pipeline dev-short-circuits — see M-1) |
| HeyGen           | Coming Soon  | true                   | 501 ✓             |
| PlayHT           | Coming Soon  | true                   | 501 ✓             |
| Resemble AI      | Coming Soon  | true                   | 501 ✓             |
| Synthesia        | Coming Soon  | (not probed)           | (not tested — not in prompt)  |

**Verdict:** PASS. Stubbed providers do exactly the thing the Wave-7 P0 #6 fix was supposed to guarantee: 501 instead of silent acceptance.

### 4. Studio upload flow

Partial walkthrough only — the flow requires clicking into a provider card, selecting audio files, and watching the pipeline. The API-level equivalent (POST /api/v1/orders for ElevenLabs) was driven 5x in parallel during the concurrent-order probe and succeeded at the DB / order-row level. Live ElevenLabs training is blocked by the missing API key — see B-1.

**Verdict:** PASS (order-create path) / BLOCKED (live training).

### 5. MyClones page render

Screenshot `05-my-clones.png`. Lists all 4 of the concurrent-stress ElevenLabs orders under "Currently Training", each showing "Pending 0%" with no error message. This is the UI-visible face of finding M-1.

**Verdict:** PASS (rendering) / M-1 (underlying data).

### 6. Concurrent-order stress

Submitted 5 `POST /api/v1/orders` for ElevenLabs voice in parallel:

```
200 200 200 200 200
order_1: 075a9ca4-a068-4a13-8b2d-a941445995d3
order_2: 8217e3c7-dd26-45f2-9d9a-9f6eec246f04
order_3: 3f154529-7ae1-4a35-bd24-f838f37e99bf
order_4: ab1153ea-949a-473f-b362-107daaf958f8
order_5: 5060bd1b-93f9-46ca-a2f1-f500b589804d
```

All 5 got unique UUIDs. None were deduped, none collided on the INSERT (the DB has no uniqueness on provider_id + identity_id, which is the right call — a user should be able to queue multiple clones). All 5 surface in `/api/v1/orders` for the mock user.

No rate-limit 429s despite `/api/v1/orders` having a 10 rpm cap in `api/app/middleware/rate_limit.py`. This is expected — 5 requests is under the cap.

**Verdict:** PASS.

Artifacts: `concurrent_order_sample.json`, `orders_after_stress.json`.

### 7. Pro data-fetch failure modes

Forced dev mode off and replaced `httpx.AsyncClient.get` with scripted failures. Full log in `docs/hardening/artifacts/pro_failure_modes.txt`:

```
[Pro down (ConnectError)] stale=False unavailable=True total_words=0
[Pro 401]                 stale=False unavailable=True total_words=0
[Pro 500]                 stale=False unavailable=True total_words=0
[Pro malformed body]      stale=False unavailable=True total_words=0
[Pro timeout]             stale=False unavailable=True total_words=0
```

Every scenario returns a `StatsResult` envelope with `unavailable=True` and zeroed stats. No exceptions propagate. This is what the frontend needs to render the amber "data may be stale" / "we can't reach Windy Pro" banner.

Note: all five scenarios returned `unavailable=True` rather than `stale=True` because the test identity had no prior cached snapshot. A real user with a populated `CachedRecordingStats` row would get `stale=True` on the same failures. The `stale` path is covered by `api/tests/test_data_fetcher.py`.

**Verdict:** PASS.

### 8. Deep-link resolver API

```
windyclone://dashboard                       → 200 { route:/legacy }
windyclone://discover                        → 200 { route:/discover }
windyclone://studio/abc-123_DEF              → 200 { route:/studio/clone/abc-123_DEF, params:{cloneId:abc-123_DEF} }
windyclone://order/ord_42                    → 200 { route:/order/ord_42, params:{orderId:ord_42} }

windyclone://studio/../../etc/passwd         → 400
windyclone://order/a/b                       → 400
windyclone://studio/a%2Fb                    → 400
windyclone://bogus                           → 400
windyword://dashboard                        → 400
windyclone://order/(200×'a')                 → 400
windyclone://order/bad space                 → 400
```

4/4 valid → correct resolution. 7/7 malformed → 400 with `{detail:"Invalid or unsupported windyclone:// URL"}`.

**Verdict:** PASS.

### 9. Soul-file export

Seeded a `Clone(id=…, passport=ET26-INSP-0001, provider_id=elevenlabs, clone_type=voice)` row, called `POST /api/v1/clones/{id}/export-soul-file`. Response: `HTTP 200`, `Content-Type: application/zip`, 2235 bytes.

ZIP contains 6 members:

- `manifest.json` — clone_id, content_summary, files, owner_email, passport, signing_key{alg,fingerprint_sha256,…}
- `voice/voice_model.json` — real model_id + provider reference
- `voice/sample.wav` — 46 bytes (stub; see L-1)
- `transcripts/transcripts.ndjson` — 115 bytes
- `birth_certificate.pdf` — 897 bytes binary
- `signature.json` — `alg=ES256`, `fingerprint_sha256`, full `public_key_pem`, `signature_b64` over `manifest.json`

Signature verification is not re-exercised here (covered by `api/tests/test_soul_file_export.py`). The structure is real, signed, and non-placeholder — no `"status":"scaffolded"` token anywhere.

**Verdict:** PASS.

Artifact: `docs/hardening/artifacts/soul_file_export.txt`.

### 10. Unit suite sanity

```
143 passed in 15.00s
```

All existing unit tests still pass on the hardening branch. Artifact: `docs/hardening/artifacts/pytest_summary.txt`.

---

## Screenshots index

| File                                   | What it shows                                        |
| -------------------------------------- | ---------------------------------------------------- |
| `01-root-redirects-to-legacy.png`      | `/` → `/legacy` Navigate redirect.                   |
| `02-legacy.png`                        | Legacy hero + stats cards with mock data.            |
| `03-discover.png`                      | Discover experience-type cards (Voice/Avatar/Soul).  |
| `04-studio.png`                        | Provider marketplace, 6 tiles w/ coming-soon flags.  |
| `05-my-clones.png`                     | 4 stuck-pending ElevenLabs orders (M-1 visible).     |
| `06-settings.png`                      | Settings page render.                                |
| `07-deeplink-discover.png`             | `?wc=windyclone://discover` at `/` → Legacy (H-1).   |
| `08-deeplink-order.png`                | `?wc=windyclone://order/abc-123` at `/` → Legacy.    |
| `09-deeplink-traversal-dropped.png`    | Traversal correctly dropped at `/`.                  |
| `10-deeplink-from-legacy.png`          | `/legacy?wc=discover` → `/discover` ✓ (contrast H-1) |
| `11-deeplink-from-discover.png`        | `/discover?wc=order/ord_42` → `/order/ord_42` ✓.     |
| `_manifest.json` / `_manifest2.json`   | Captured URLs + final routing result per run.        |

All screenshots are fullPage captures at 1400×900 from headless Chromium 130 via Playwright 1.48.2.

---

## Recommended Wave-12 follow-ups

In descending priority:

1. **Fix H-1** (`?wc=` deep-link at `/`). One-line change to preserve the `?wc=` search string through the `/` → `/legacy` redirect, or move the unwrap logic out of `useEffect`. Without this the documented entry point is dead.
2. **Fix M-1** (silent dev-mode pipeline drop). Update the order row to `awaiting_upstream` or `failed` with a clear `error_message` before returning. Bonus: extend `_enforce_boot_guards` in prod to refuse boot with no provider key wired.
3. **Wire real Eternitas for staging.** The auto-hatch path is covered by unit tests but hasn't been exercised end-to-end in any wave. A staging deploy of Eternitas + a smoke run that verifies `/registry/verify/{passport}` is the last missing link in the Clone→Eternitas contract.
4. **Add a dev-mode banner on the frontend.** If the `/api/v1/health` (or any existing endpoint) returned `dev_mode=true`, the UI could surface a one-time "dev mode — orders don't actually train" notice. Solves the worst of M-1's UX footprint without touching the pipeline.
5. **Replace the Playwright walkthrough with a committed script**. `docs/hardening/screenshot.mjs` currently lives at the repo root and has to be copied into `web/` for `node` to resolve `playwright`. Move it into `web/` with its own npm script and it becomes a repeatable pre-release check.
