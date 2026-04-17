## Summary

<!-- What changed and why. One to three bullets. -->

## Test plan

<!-- Mark each box you've actually run. -->

- [ ] `pytest api/tests -q` — unit suite green
- [ ] `ETERNITAS_LIVE_URL=http://localhost:8500 pytest api/tests/integration -v` — live trust tests green (if trust/gating touched)
- [ ] Manual smoke in the dashboard (if UI touched)

## Security-sensitive touchpoints

<!-- Tick every box that applies. Leave a note if any are ticked. -->

- [ ] Trust gate matrix (`_GATE_REQUIREMENTS` or `enforce_gate` call sites)
- [ ] Soul-file signing path (`app/auth/signing.py`, `app/services/soul_file.py`)
- [ ] Webhook signature verification
- [ ] Secrets — new env vars, new Secrets Manager entries, rotation procedure
- [ ] None of the above

## Notes for the reviewer

<!-- Anything non-obvious: design tradeoffs, deliberate scope cuts, follow-up work. -->
