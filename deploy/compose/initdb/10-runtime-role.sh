#!/bin/sh
# Runs once, when the Postgres data directory is created (docker-entrypoint-initdb.d).
#
# POSTGRES_USER owns the schema and runs migrations. The application connects as APP_DB_USER, a
# role that can read and write rows but owns nothing, so a compromised web process cannot drop
# a table, rewrite the audit trail, or disable its trigger (see docs/en/security/audit-integrity).
# Objects the owner creates later (every migration) grant the runtime role its row privileges
# through default privileges; the audit migration then takes UPDATE/DELETE/TRUNCATE on the trail
# away again for the role named in AUDIT_RUNTIME_ROLE.
set -eu

: "${APP_DB_USER:?set APP_DB_USER}"
: "${APP_DB_PASSWORD:?set APP_DB_PASSWORD}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v runtime_user="$APP_DB_USER" -v runtime_pw="$APP_DB_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION',
              :'runtime_user', :'runtime_pw') \gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), :'runtime_user') \gexec
SELECT format('GRANT USAGE ON SCHEMA public TO %I', :'runtime_user') \gexec
SELECT format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public
               GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO %I',
              current_user, :'runtime_user') \gexec
SELECT format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public
               GRANT USAGE, SELECT ON SEQUENCES TO %I',
              current_user, :'runtime_user') \gexec
SQL
