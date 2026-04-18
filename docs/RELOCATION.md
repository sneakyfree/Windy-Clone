# Repo relocation — `~/Desktop/Grant's Folder/Windy-Clone` → `~/windy-clone`

**Status:** Wave-8 prep. Filesystem move pending — Grant will do the `mv`.
This document is the single source of truth for the target path and for
anything that breaks when the working copy is somewhere else.

## Why

Every other repo in the Windy ecosystem lives at `/Users/thewindstorm/<repo>`
(see `reference_repo_locations.md` in auto-memory). `Windy-Clone` is the
odd one out under `Desktop/Grant's Folder`. A non-standard path:

- Breaks tab-completion muscle memory when switching between repos.
- Confuses ecosystem-level scripts that glob `/Users/thewindstorm/windy-*`.
- Leaks a personal folder name (`Grant's Folder`) into any shell history
  or screenshot that references the path.
- Makes agent prompts longer (the current path has a space + apostrophe
  that has to be escaped in every `cd`).

## What changes inside the repo

**Nothing.** We've audited the tree (`git grep "Desktop\|Grant's Folder"`)
and there are no hardcoded absolute paths inside the repo:

- `scripts/dev.sh` uses `SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"` — path-agnostic.
- `Dockerfile` uses `/app` only.
- `docker-compose.yml` uses relative volumes (`./web`).
- `.github/workflows/*` uses `${{ github.workspace }}`.
- Docs link to GitHub URLs (`github.com/sneakyfree/Windy-Clone`), not local paths.

The only references to "Desktop" in the tree are prose about the Windy
Pro *Desktop* (Electron) app — unrelated to filesystem layout.

## What Grant needs to do

1. Close any editors / terminals holding the current path.
2. Run:
   ```bash
   mv "/Users/thewindstorm/Desktop/Grant's Folder/Windy-Clone" /Users/thewindstorm/windy-clone
   ```
3. Update `reference_repo_locations.md` in auto-memory to list `windy-clone`
   at `/Users/thewindstorm/windy-clone`.
4. Re-run `./scripts/dev.sh` from the new path to confirm nothing broke.
5. (Optional) Re-create the `.venv` from the new path — virtualenvs store
   absolute paths in their shebangs and will stop working after a `mv`.
   ```bash
   rm -rf .venv
   uv venv && uv pip install -e ".[dev]"
   ```

## After the move

- Delete this file in a follow-up commit — it's only useful during the
  transition.
- Remove the "Canonical path" note from `CLAUDE.md`.
