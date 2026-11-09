# 0006. Config and secrets

- **Status:** Accepted (owner, 2026-11-08). The owner's added requirement: no env files or secret keys may ever be committed to GitHub.

## Decision
- **API:** a typed `Settings` class (`pydantic-settings`) read from environment variables, or from a gitignored `api/.env` in dev. A missing required setting fails at startup with a clear error. Secrets use `SecretStr`, so they never appear in logs or reprs.
- **Web:** exactly one build-time variable, `VITE_API_BASE_URL`, read in a single API client module. There are no hard-coded URLs anywhere else, and no secrets in the web app at all (anything `VITE_*` is public).
- **Committed examples only:** `api/.env.example`, `web/.env.example`, and `infra/.env.example` list every key with placeholder values.
- **DB credentials:** the app and migrator roles have separate variables (`DATABASE_URL` for `feynman_app`, `MIGRATION_DATABASE_URL` for `feynman_migrator`).

## Secret-leak defences (three layers)
1. **Root `.gitignore`** blocks `.env` and `.env.*` (except `!.env.example`) in every folder, plus key and cert files (`*.pem`, `*.key`).
2. **gitleaks** runs as a `pre-commit` hook locally **and** as a CI job. A detected secret fails the commit or build.
3. **GitHub secret scanning + push protection.** *Deferred by the owner (2026-11-09):* the repo is public and has a single contributor, so layers 1–2 are enough for now. It's free for public repos and can be enabled later in Settings → Code security. This is not a prerequisite for any run.

A check on 2026-11-08 found that the git history contains no `.env` file or literal secret.
