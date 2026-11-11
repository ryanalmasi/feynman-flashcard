#!/usr/bin/env bash
# Generates infra/.env, api/.env, web/.env if missing. Never overwrites existing files.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
gen() { python3 -c 'import secrets; print(secrets.token_urlsafe(24))'; }

INFRA="$ROOT/infra/.env"
API="$ROOT/api/.env"
WEB="$ROOT/web/.env"

if [[ ! -f "$INFRA" ]]; then
  (
    umask 077
    printf 'POSTGRES_PASSWORD=%s\nMIGRATOR_PASSWORD=%s\nAPP_PASSWORD=%s\n' "$(gen)" "$(gen)" "$(gen)" > "$INFRA"
  )
  echo "created infra/.env"
  if [[ -f "$API" ]]; then
    echo "WARNING: created infra/.env but api/.env already exists; its passwords will not match. Delete api/.env and run make env again." >&2
  fi
fi

if [[ ! -f "$API" ]]; then
  # Derive from infra/.env (parsed, not sourced).
  MIG="$(grep -E '^MIGRATOR_PASSWORD=' "$INFRA" | head -1 | cut -d= -f2-)"
  APP="$(grep -E '^APP_PASSWORD=' "$INFRA" | head -1 | cut -d= -f2-)"
  mkdir -p "$ROOT/api"
  H="127.0.0.1:5432"
  (
    umask 077
    {
      echo "DATABASE_URL=postgresql+asyncpg://feynman_app:${APP}@${H}/feynman"
      echo "MIGRATION_DATABASE_URL=postgresql+asyncpg://feynman_migrator:${MIG}@${H}/feynman"
      echo "TEST_DATABASE_URL=postgresql+asyncpg://feynman_app:${APP}@${H}/feynman_test"
      echo "TEST_MIGRATION_DATABASE_URL=postgresql+asyncpg://feynman_migrator:${MIG}@${H}/feynman_test"
      echo 'CORS_ORIGINS=["http://localhost:5173"]'
      echo "LOG_LEVEL=INFO"
      echo "SESSION_COOKIE_SECURE=false"
      echo "LLM_ENABLED=false"
      echo "ANTHROPIC_API_KEY="
    } > "$API"
  )
  echo "created api/.env"
else
  if ! grep -qE '^SESSION_COOKIE_SECURE=' "$API"; then
    printf 'SESSION_COOKIE_SECURE=false\n' >> "$API"
    echo "added SESSION_COOKIE_SECURE=false to api/.env"
  fi
  if ! grep -qE '^LLM_ENABLED=' "$API"; then
    printf 'LLM_ENABLED=false\nANTHROPIC_API_KEY=\n' >> "$API"
    echo "added LLM settings to api/.env"
  fi
fi

if [[ ! -f "$WEB" ]]; then
  mkdir -p "$ROOT/web"
  echo 'VITE_API_BASE_URL=http://localhost:8000' > "$WEB"
  echo "created web/.env"
fi
