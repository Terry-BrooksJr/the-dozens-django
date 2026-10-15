#!/usr/bin/env bash
# Setup script for a Codex cloud environment.
#
# Codex runs this as root, non-interactively, with internet access, before
# the agent starts. There is no Docker daemon, so Postgres and Redis are
# installed from apt and run in-process instead of as containers.
#
# Usage (paste into Codex → Environment → Setup script):
#   bash scripts/codex-setup.sh
#
# Maintenance script / before running tests, if the services are down:
#   bash scripts/codex-setup.sh --services-only
#
# Codex secrets are only visible during setup, so the agent's test runs
# can't reach Doppler. Set the variables settings.py requires as plain Codex
# environment variables (dummy values are fine for the Staging test config).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Same credentials as CI's `test` job and the Staging settings' defaults.
PG_USER="${PG_DATABASE_USER:-root}"
PG_PASSWORD="${PG_DATABASE_PASSWORD:-postgres}"
PG_DB="${POSTGRES_DB:-test_db}"

# Role and database names must be plain identifiers. Neither they nor the
# password are ever spliced into shell or SQL text: they reach psql as
# variables, and SQL quotes them itself (format %I / %L).
for ident in "$PG_USER" "$PG_DB"; do
    if [[ ! "$ident" =~ ^[A-Za-z_][A-Za-z0-9_]{0,62}$ ]]; then
        echo "Invalid Postgres identifier '$ident' (PG_DATABASE_USER / POSTGRES_DB):" \
            "use letters, digits and underscores only" >&2
        exit 1
    fi
done

# Run a command as the postgres OS user with its arguments passed as argv,
# never re-parsed by a shell.
as_postgres() {
    if command -v runuser >/dev/null 2>&1; then
        runuser -u postgres -- "$@"
    else
        su postgres -s /bin/sh -c 'exec "$0" "$@"' "$@"
    fi
}

install_services() {
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y --no-install-recommends postgresql redis-server
}

start_services() {
    service postgresql start >/dev/null
    for _ in $(seq 1 30); do
        pg_isready -q && break
        sleep 1
    done
    pg_isready -q || { echo "Postgres did not start" >&2; exit 1; }

    # Idempotent and self-reconciling: on every run the role gets the
    # requested password/privileges and the database the requested owner, so
    # a rerun after the credentials change doesn't leave the old ones behind.
    # The heredoc is quoted ('SQL'), so the shell expands nothing inside it.
    as_postgres psql -X -q -v ON_ERROR_STOP=1 \
        -v "role=${PG_USER}" -v "password=${PG_PASSWORD}" -v "db=${PG_DB}" <<'SQL'
SELECT format('CREATE ROLE %I', :'role')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'role') \gexec
SELECT format('ALTER ROLE %I WITH LOGIN SUPERUSER PASSWORD %L', :'role', :'password') \gexec
SELECT format('CREATE DATABASE %I OWNER %I', :'db', :'role')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'db') \gexec
SELECT format('ALTER DATABASE %I OWNER TO %I', :'db', :'role') \gexec
SQL

    redis-cli ping >/dev/null 2>&1 || redis-server --daemonize yes >/dev/null
    echo "Postgres (${PG_USER}@localhost:5432/${PG_DB}) and Redis (localhost:6379) are up"
}

if [ "${1:-}" = "--services-only" ]; then
    start_services
    exit 0
fi

# Tooling, Python 3.14, uv sync, pre-commit and the env check. Doppler is
# used only if DOPPLER_TOKEN is set as a Codex secret (setup phase only).
./scripts/install.sh --no-interactive

install_services
start_services

# Apply migrations with the CI test configuration, so the database matches
# what `task test:coverage` / `task run:test` expect. The local database's
# settings are exported and preserved through Doppler, so a Doppler config
# that names another database can't redirect this migrate to it.
export PG_DATABASE_HOST=localhost PG_DATABASE_PORT=5432 \
    PG_DATABASE_USER="$PG_USER" PG_DATABASE_PASSWORD="$PG_PASSWORD" POSTGRES_DB="$PG_DB"
DJANGO_CONFIGURATION=Staging PYTHONPATH="$REPO_ROOT" \
    DOPPLER_PRESERVE_EXTRA="PG_DATABASE_HOST,PG_DATABASE_PORT,PG_DATABASE_USER,PG_DATABASE_PASSWORD,POSTGRES_DB" \
    ./scripts/with_doppler.sh .venv/bin/python3 run/manage.py migrate --no-input
