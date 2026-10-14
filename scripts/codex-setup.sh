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

    su postgres -c "psql -v ON_ERROR_STOP=1 -q" <<SQL
DO \$\$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${PG_USER}') THEN
        CREATE ROLE "${PG_USER}" LOGIN SUPERUSER PASSWORD '${PG_PASSWORD}';
    END IF;
END \$\$;
SQL
    su postgres -c "psql -tAc \"SELECT 1 FROM pg_database WHERE datname = '${PG_DB}'\"" | grep -q 1 \
        || su postgres -c "createdb -O '${PG_USER}' '${PG_DB}'"

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
# what `task test:coverage` / `task run:test` expect.
DJANGO_CONFIGURATION=Staging PYTHONPATH="$REPO_ROOT" \
    ./scripts/with_doppler.sh .venv/bin/python3 run/manage.py migrate --no-input
