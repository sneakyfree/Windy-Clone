#!/usr/bin/env bash
# ==============================================================================
#  Windy Clone — production smoke test
# ==============================================================================
#
#  Run this against a freshly deployed Clone instance BEFORE pointing DNS
#  at it. It exercises the four load-bearing paths:
#
#    1. Auth — JWKS validation of a real Windy Pro JWT.
#    2. Pro pull — /api/v1/legacy/stats pulls recording data through Pro.
#    3. Order — create a voice-clone preview order (ElevenLabs).
#    4. Auto-hatch — poll until the order completes + verify a clone row
#       lands in /api/v1/clones, then (optionally) ask Eternitas to verify
#       the passport was minted.
#
#  Usage:
#    WINDY_CLONE_URL=https://windyclone.com \
#    WINDY_CLONE_SMOKE_JWT=$(cat ./smoke-jwt.txt) \
#    ETERNITAS_URL=https://eternitas.example.com \
#    WINDY_CLONE_SMOKE_PASSPORT=ET26-AAAA-0001 \   # optional, for §4 verify
#    ./scripts/smoke-test.sh
#
#  Exits 0 on full pass, non-zero on the first failing step.
# ------------------------------------------------------------------------------

set -euo pipefail

BASE="${WINDY_CLONE_URL:-http://localhost:8400}"
JWT="${WINDY_CLONE_SMOKE_JWT:-}"
ETERNITAS="${ETERNITAS_URL:-}"
PASSPORT_HINT="${WINDY_CLONE_SMOKE_PASSPORT:-}"
POLL_TIMEOUT="${SMOKE_POLL_TIMEOUT_SECONDS:-180}"
POLL_INTERVAL="${SMOKE_POLL_INTERVAL_SECONDS:-5}"

red()    { printf "\033[31m%s\033[0m\n" "$*" >&2; }
green()  { printf "\033[32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }

require() {
  local name=$1
  local value=$2
  if [[ -z "$value" ]]; then
    red "✗ $name is required."
    exit 2
  fi
}

require "WINDY_CLONE_SMOKE_JWT (a real Pro-issued JWT for a test identity)" "$JWT"

command -v curl >/dev/null || { red "✗ curl is required"; exit 2; }
command -v jq   >/dev/null || { red "✗ jq is required"; exit 2; }

AUTH_HEADER="Authorization: Bearer $JWT"

# --- 0. Reachability ----------------------------------------------------------
green "→ [0/4] Reachability: $BASE/health"
if ! curl -fsS "$BASE/health" | jq -e '.status == "healthy"' >/dev/null; then
  red "✗ /health did not return healthy. Is the API up?"
  exit 1
fi
green "  ok"

# --- 1. Auth — JWKS validation ------------------------------------------------
green "→ [1/4] Auth: GET /api/v1/preferences (requires JWT)"
HTTP_CODE=$(curl -s -o /tmp/smoke_prefs.json -w "%{http_code}" -H "$AUTH_HEADER" "$BASE/api/v1/preferences")
if [[ "$HTTP_CODE" != "200" ]]; then
  red "✗ Auth failed — expected 200, got $HTTP_CODE. Body:"
  cat /tmp/smoke_prefs.json >&2
  red "  Common causes: JWT expired, JWKS URL wrong, JWT_AUDIENCE mismatch."
  exit 1
fi
IDENTITY_ID=$(jq -r '.identity_id' /tmp/smoke_prefs.json)
[[ -n "$IDENTITY_ID" && "$IDENTITY_ID" != "null" ]] || { red "✗ response missing identity_id"; exit 1; }
green "  ok — identity_id=$IDENTITY_ID"

# --- 2. Pro pull — recording stats --------------------------------------------
green "→ [2/4] Pro data pull: GET /api/v1/legacy/stats"
curl -fsS -H "$AUTH_HEADER" "$BASE/api/v1/legacy/stats" >/tmp/smoke_stats.json
if jq -e '.banner.severity == "warning"' /tmp/smoke_stats.json >/dev/null; then
  red "✗ Pro is unreachable from Clone (stats banner=warning). Check WINDY_PRO_API_URL."
  exit 1
fi
if jq -e '.banner.severity == "info"' /tmp/smoke_stats.json >/dev/null; then
  yellow "  warn — serving stale cached stats. Pro is reachable but returning errors."
fi
TOTAL_WORDS=$(jq -r '.stats.total_words' /tmp/smoke_stats.json)
green "  ok — total_words=$TOTAL_WORDS"

# --- 3. Order — create a preview ElevenLabs order -----------------------------
green "→ [3/4] Order: POST /api/v1/orders (voice / ElevenLabs)"
ORDER_BODY='{"provider_id":"elevenlabs","clone_type":"voice"}'
HTTP_CODE=$(curl -s -o /tmp/smoke_order.json -w "%{http_code}" \
  -H "$AUTH_HEADER" -H "Content-Type: application/json" \
  -d "$ORDER_BODY" "$BASE/api/v1/orders")
if [[ "$HTTP_CODE" != "200" && "$HTTP_CODE" != "201" ]]; then
  red "✗ Order creation failed — HTTP $HTTP_CODE. Body:"
  cat /tmp/smoke_order.json >&2
  if [[ "$HTTP_CODE" == "501" ]]; then
    red "  501 = ElevenLabs adapter not wired. Check ELEVENLABS_API_KEY."
  fi
  exit 1
fi
ORDER_ID=$(jq -r '.id // .order_id // .order.id // empty' /tmp/smoke_order.json)
[[ -n "$ORDER_ID" ]] || { red "✗ order response missing id. Body:"; cat /tmp/smoke_order.json >&2; exit 1; }
green "  ok — order_id=$ORDER_ID"

# --- 4. Completion + auto-hatch ----------------------------------------------
green "→ [4/4] Poll /api/v1/orders/$ORDER_ID until completed (timeout ${POLL_TIMEOUT}s)"
DEADLINE=$(( $(date +%s) + POLL_TIMEOUT ))
STATUS="pending"
while [[ $(date +%s) -lt $DEADLINE ]]; do
  curl -fsS -H "$AUTH_HEADER" "$BASE/api/v1/orders/$ORDER_ID" >/tmp/smoke_order_status.json
  STATUS=$(jq -r '.status' /tmp/smoke_order_status.json)
  case "$STATUS" in
    completed)       green "  order completed"; break ;;
    failed)          red "✗ order failed. Body:"; cat /tmp/smoke_order_status.json >&2; exit 1 ;;
    cancelled)       red "✗ order was cancelled mid-flight"; exit 1 ;;
    awaiting_upstream)
      yellow "  awaiting_upstream (provider still training) — continuing to poll"
      ;;
    *)
      printf "  status=%s…\n" "$STATUS"
      ;;
  esac
  sleep "$POLL_INTERVAL"
done

if [[ "$STATUS" != "completed" ]]; then
  red "✗ Order did not complete within ${POLL_TIMEOUT}s (last status: $STATUS)"
  red "  In a freshly deployed env this is often expected — provider training"
  red "  can take longer than the smoke-test budget. Re-run with a larger"
  red "  SMOKE_POLL_TIMEOUT_SECONDS if so."
  exit 1
fi

# Clone row should now exist under this identity.
green "→ Verify: GET /api/v1/clones includes a row for this order"
curl -fsS -H "$AUTH_HEADER" "$BASE/api/v1/clones" >/tmp/smoke_clones.json
if ! jq -e --arg pid "elevenlabs" '.clones | map(select(.provider_id == $pid)) | length > 0' /tmp/smoke_clones.json >/dev/null; then
  red "✗ No ElevenLabs clone row under this identity. Body:"
  cat /tmp/smoke_clones.json >&2
  exit 1
fi
green "  ok — clone row present"

# Optional: if Eternitas is reachable and the operator passed a passport
# hint, ask Eternitas to verify. We deliberately do NOT derive the
# passport from Clone — the passport field isn't exposed on the public
# clones API, so this step is opt-in for operators who can look it up
# (via Eternitas admin or DB) and pass it in.
if [[ -n "$ETERNITAS" && -n "$PASSPORT_HINT" ]]; then
  green "→ Eternitas: GET $ETERNITAS/registry/verify/$PASSPORT_HINT"
  if curl -fsS "$ETERNITAS/registry/verify/$PASSPORT_HINT" | jq -e '.verified == true or .status == "active"' >/dev/null; then
    green "  ok — passport verified at Eternitas"
  else
    red "✗ Eternitas could not verify $PASSPORT_HINT"
    exit 1
  fi
else
  yellow "→ Skipping Eternitas passport verification."
  yellow "  Set ETERNITAS_URL + WINDY_CLONE_SMOKE_PASSPORT to enable."
fi

echo
green "✓ All smoke checks passed for $BASE"
