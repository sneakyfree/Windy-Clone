# Agent Trust Gates

Windy Clone protects sensitive actions behind clearance gates. Humans bypass all gates — they own their own data. **Agents** — callers whose JWT carries an Eternitas `passport` claim — are checked against the matrix below on every gated request.

## Clearance ladder

| Level | Integer | Source signal (Eternitas `trust_score`) |
| ----- | ------- | --------------------------------------- |
| `UNVERIFIED` | 0 | `< 50`, or passport status ≠ `active`, or `valid == false` |
| `VERIFIED`   | 1 | `50–69` |
| `CLEARED`    | 2 | `70–89` |
| `TOP_SECRET` | 3 | `≥ 90` |

Levels are a total order. "≥ X" in the gate matrix means `actual.value >= required.value`.

## Gate matrix

| Action                                | Gate constant                  | Required clearance |
| ------------------------------------- | ------------------------------ | ------------------ |
| Submit any clone order                | `SUBMIT_CLONE_ORDER`           | `VERIFIED` |
| Clone a human (target ≠ the bot's own identity) | `CLONE_HUMAN`        | `CLEARED` |
| Export a soul file containing human voice/avatar | `EXPORT_SOUL_FILE_HUMAN` | `TOP_SECRET` |

**Single source of truth:** `_GATE_REQUIREMENTS` in `api/app/services/trust_client.py`. Docs drift is prevented by the test suite pinning `required_level(...)` against these values.

## Trust lookup

```
GET {ETERNITAS_URL}/api/v1/registry/verify/{passport}
→ {"passport", "status", "trust_score", "valid"}
```

Results are cached in-process for `ETERNITAS_TRUST_CACHE_TTL` (default 300 s). Network or parse failure degrades the caller to `UNVERIFIED` — we under-trust rather than fail open.

## What counts as "human" content

A **clone represents an agent** iff its DB row has a non-null `passport` — this is set during order fulfilment when Eternitas auto-hatches the trained voice. A clone with a null passport was trained from a human's recordings and is subject to `EXPORT_SOUL_FILE_HUMAN` when an agent attempts to export it.

For the `CLONE_HUMAN` gate at order-submission time: the request body may carry `target_identity_id`. When that field is present and differs from the caller's own `identity_id`, the caller is attempting to clone someone else — gated at `CLEARED`.

## Why these thresholds

- `VERIFIED` (50+) — the minimum bar below which an agent cannot commit resources or incur cost. Consistent with the public trust badge turning yellow at 50.
- `CLEARED` (70+) — matches the green-badge threshold. Cloning a third party is a privacy-sensitive operation; at 70+ the agent has sustained good behaviour.
- `TOP_SECRET` (90+) — soul-file export is the most dangerous operation: it hands a portable, signed copy of someone else's voice/avatar to the caller. Reserved for a small set of well-tenured operators.

## Enforcement points

| Endpoint | Gate(s) |
| -------- | ------- |
| `POST /api/v1/orders` | `SUBMIT_CLONE_ORDER`, plus `CLONE_HUMAN` when `target_identity_id` ≠ self |
| `POST /api/v1/clones/{id}/export-soul-file` | `EXPORT_SOUL_FILE_HUMAN` when the clone has no passport |

## Failure behaviour

Gates raise `TrustGateError`, surfaced by routes as `403 Forbidden` with a message of the form:

```
submit_clone_order requires clearance VERIFIED; passport holder is UNVERIFIED
```

This message is stable — integrations may parse it, though the structured fields on the exception (`required`, `actual`, `action`) are preferred.

## Human bypass

Humans never hit these gates. `enforce_gate` returns immediately when `user.is_agent` is false. This is by design: the gates exist to check whether an agent should be allowed to act on someone else's or on resource-consuming flows, not to limit a human's control over their own identity.
