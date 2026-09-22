#!/bin/bash
# Runs once, after 01_schema_and_data.sql, when the data volume is first created.
# Creates the account the agent connects with: SELECT only, never root.
set -e

: "${READONLY_USER:?READONLY_USER is required}"
: "${READONLY_PASSWORD:?READONLY_PASSWORD is required}"

mysql -uroot -p"${MYSQL_ROOT_PASSWORD}" <<EOSQL
CREATE USER '${READONLY_USER}'@'%' IDENTIFIED BY '${READONLY_PASSWORD}';
GRANT SELECT ON \`${MYSQL_DATABASE}\`.* TO '${READONLY_USER}'@'%';
FLUSH PRIVILEGES;
EOSQL
