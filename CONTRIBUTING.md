# Contributing to Windy Clone

## Branching & review

- **`main` is deployable.** Never push to it directly. Every change lands via PR.
- **Feature branches.** Create a branch for each wave / feature / fix. Naming: `wave-N-<slug>` for wave work (e.g. `wave-6-deploy-prep`), `fix-<slug>` for bug fixes, `chore-<slug>` for housekeeping.
- **One PR per wave.** Keep PRs focused. A Wave-6 PR covers Wave-6 work; unrelated cleanup goes in its own branch.
- **Tests must pass** before merge. Both the unit suite (`pytest api/tests`) and — when Eternitas is reachable — the live integration suite (`ETERNITAS_LIVE_URL=... pytest api/tests/integration`).
- **Review by Grant.** Do not self-merge. Wait for review and explicit approval, even on small PRs.

## Exceptions

Direct pushes to `main` are acceptable only for:

1. The very first commit that creates `main`.
2. One-line fixes Grant inline-approves (typo in a doc, env var rename).

When in doubt, branch.

## Commit message style

See `git log` for precedent. One-sentence subject (imperative mood), followed by an optional paragraph or bullet list describing *why*. Co-author Claude when Claude wrote substantive code:

```
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

## Running the suite locally

```bash
# Unit
.venv/bin/python -m pytest api/tests -q

# Live integration (requires Eternitas at localhost:8500 with seeded passports)
ETERNITAS_LIVE_URL=http://localhost:8500 .venv/bin/python -m pytest api/tests/integration -v
```

## Getting a review

Open the PR with `gh pr create`. The template will prompt for summary, test plan, and any security-sensitive touchpoints. Tag Grant as reviewer.
