#!/bin/bash
# Runs once, after 01_schema_and_data.sql, when the data volume is first created.
# Creates the account the agent connects with: SELECT only, never the admin user.
set -e

: "${READONLY_USER:?READONLY_USER is required}"
: "${READONLY_PASSWORD:?READONLY_PASSWORD is required}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<EOSQL
CREATE ROLE ${READONLY_USER} LOGIN PASSWORD '${READONLY_PASSWORD}';
-- Belt and braces: every session of this role starts read-only.
ALTER ROLE ${READONLY_USER} SET default_transaction_read_only = on;

GRANT CONNECT ON DATABASE ${POSTGRES_DB} TO ${READONLY_USER};
GRANT USAGE ON SCHEMA public TO ${READONLY_USER};
GRANT SELECT ON ALL TABLES IN SCHEMA public TO ${READONLY_USER};
-- Tables created later by the admin user are readable too.
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO ${READONLY_USER};
EOSQL
