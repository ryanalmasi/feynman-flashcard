#!/usr/bin/env bash
# Creates least-privilege roles and databases. Runs once on first init of the data volume.
# Honours PGHOST/PGPASSWORD so CI can run it standalone.
set -euo pipefail
: "${MIGRATOR_PASSWORD:?}" "${APP_PASSWORD:?}"

PSQL=(psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER:-postgres}" -v mig_pw="$MIGRATOR_PASSWORD" -v app_pw="$APP_PASSWORD")

"${PSQL[@]}" --dbname postgres <<'SQL'
CREATE ROLE feynman_migrator LOGIN PASSWORD :'mig_pw';
CREATE ROLE feynman_app LOGIN PASSWORD :'app_pw' NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
CREATE DATABASE feynman OWNER feynman_migrator;
CREATE DATABASE feynman_test OWNER feynman_migrator;
SQL

for db in feynman feynman_test; do
  "${PSQL[@]}" --dbname "$db" -v db="$db" <<'SQL'
REVOKE ALL ON DATABASE :"db" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"db" TO feynman_app;
ALTER SCHEMA public OWNER TO feynman_migrator;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO feynman_app;
ALTER DEFAULT PRIVILEGES FOR ROLE feynman_migrator IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO feynman_app;
ALTER DEFAULT PRIVILEGES FOR ROLE feynman_migrator IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO feynman_app;
SQL
done
