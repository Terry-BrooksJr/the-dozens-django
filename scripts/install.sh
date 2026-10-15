#!/usr/bin/env bash
# Bootstrap a local development environment for The Dozens API.
#
# Mirrors what CI (.github/workflows/commit_check.yaml +
# .github/actions/setup-python-env) and the dev container
# (.devcontainer/devcontainer.json) do, so a fresh clone can run every
# Taskfile task:
#
#   1. System packages      libpq, libmagic, curl, git (+ psql/redis-cli clients)
#   2. Tooling              uv, Task (go-task), Doppler CLI, direnv (optional)
#   3. Python 3.14 + deps   `uv sync --locked --group test --group dev` (= `task install`)
#   4. pre-commit hook      config lives in .configs/, so it must be pointed at explicitly
#   5. Environment          writes .envrc (Doppler) and checks every variable settings.py reads
#   6. Local services       optional Postgres 15 + Redis 7 containers, same as CI's `test` job
#   7. Database             optional `migrate`
#   8. GitHub Actions       optional: set the repo secrets/variables the workflow needs via `gh`
#
# Usage:
#   scripts/install.sh [options]
#
# Options:
#   --skip-system          Don't install OS packages (no sudo / brew)
#   --with-services        Start Postgres + Redis containers via Docker
#   --migrate              Run Django migrations after install
#   --github-secrets       Prompt for and set GitHub Actions secrets/variables with `gh`
#   --doppler-project P    Doppler project  (default: yo-momma)
#   --doppler-config C     Doppler config   (default: dev)
#   --configuration NAME   DJANGO_CONFIGURATION for .envrc (default: Development)
#   --force-envrc          Overwrite an existing .envrc
#   -y, --yes              Answer "yes" to every confirmation
#   --no-interactive       Never prompt; take the safe default everywhere (see below)
#   -h, --help             Show this help
#
# --no-interactive (also enabled automatically when stdin is not a terminal):
#   * every confirmation answers "no" unless --yes is also given
#   * sudo is used only if it needs no password; otherwise OS packages are skipped
#   * no `doppler login` — use DOPPLER_TOKEN or log in beforehand
#   * --github-secrets reads values from same-named environment variables,
#     skips anything unset, and never replaces an existing secret/variable
#     unless --yes is also given
#   * an existing .envrc is kept (unless --force-envrc)
#
# Re-running is safe: every step checks before it changes anything.
set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────
PYTHON_VERSION="3.14"              # pyproject.toml: requires-python >=3.14,<3.15
DOPPLER_PROJECT_DEFAULT="yo-momma"
DOPPLER_CONFIG_DEFAULT="dev"
DJANGO_CONFIGURATION_DEFAULT="Development"
PG_IMAGE="postgres:15"
REDIS_IMAGE="redis:7-alpine"
PG_CONTAINER="dozens-postgres"
REDIS_CONTAINER="dozens-redis"

SKIP_SYSTEM=0
WITH_SERVICES=0
RUN_MIGRATE=0
GITHUB_SECRETS=0
FORCE_ENVRC=0
ASSUME_YES=0
NON_INTERACTIVE=0
DOPPLER_PROJECT_ARG="${DOPPLER_PROJECT:-$DOPPLER_PROJECT_DEFAULT}"
DOPPLER_CONFIG_ARG="${DOPPLER_CONFIG:-$DOPPLER_CONFIG_DEFAULT}"
DJANGO_CONFIGURATION_ARG="$DJANGO_CONFIGURATION_DEFAULT"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL_BIN="$HOME/.local/bin"

# ── Environment variable inventory (from core/settings.py + Taskfile.yml) ─────
# Required by every configuration: values.SecretValue / values.Value with no
# default, so Django refuses to start without them.
REQUIRED_VARS="
SECRET_KEY
SITE_ID
GITHUB_ACCESS_TOKEN
CACHE_TTL
RECAPTCHA_PRIVATE_KEY
RECAPTCHA_PUBLIC_KEY
S3_OBJECT_STORAGE_KEY
S3_OBJECT_STORAGE_SECRET
S3_OBJECT_STORAGE_BUCKET_NAME
S3_ENDPOINT_URL
S3_REGION_NAME
EMAIL_SERVER
EMAIL_TSL_PORT
NOTIFICATION_SENDER_EMAIL
EMAIL_ACCT_PASSWORD
MAILER_EMPTY_QUEUE_SLEEP
"
# Database: Development/Production read these with no default; Staging
# (task run:test / test:coverage) falls back to root:postgres@localhost:5432/test_db.
DATABASE_VARS="
POSTGRES_DB
PG_DATABASE_USER
PG_DATABASE_PASSWORD
PG_DATABASE_HOST
PG_DATABASE_PORT
"
# Production only (task run:prod, Docker image).
PRODUCTION_VARS="
ALLOWED_HOSTS
ALLOWED_ORIGINS
"
# Optional: features degrade gracefully or fall back to a default when unset.
OPTIONAL_VARS="
USE_REDIS_CACHE
REDIS_CACHE_TOKEN
CACHE_KEY_PREFIX
METRICS_SCRAPE_TOKEN
EMAIL_ASSET_BASE_URL
LAUNCHDARKLY_ENABLED
LAUNCHDARKLY_SDK_KEY
LAUNCHDARKLY_OBSERVABILITY_ENABLED
LAUNCHDARKLY_SERVICE_NAME
LAUNCHDARKLY_SERVICE_VERSION
LOKI_URL
LOKI_PASSWORD
LOG_FILE_DIRECTORY
API_VERSION
GRAFANA_DASHBOARD_URL
CODACY_PROJECT_TOKEN
TEMP_STATIC_DIR
"

# GitHub Actions inputs used by .github/workflows/commit_check.yaml.
GH_SECRETS="DOPPLER_TOKEN CODACY_PROJECT_TOKEN SAFETY_API_KEY DOCKERHUB_TOKEN"
GH_VARIABLES="DOPPLER_PROJECT DOPPLER_CONFIG DOCKERHUB_USERNAME"

# ── Output helpers ────────────────────────────────────────────────────────────
if [ -t 1 ]; then
    C_BLUE=$'\033[1;34m'; C_GREEN=$'\033[1;32m'; C_YELLOW=$'\033[1;33m'
    C_RED=$'\033[1;31m'; C_DIM=$'\033[2m'; C_RESET=$'\033[0m'
else
    C_BLUE=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_DIM=""; C_RESET=""
fi
step() { printf '\n%s==> %s%s\n' "$C_BLUE" "$*" "$C_RESET"; }
ok()   { printf '  %s✔%s %s\n' "$C_GREEN" "$C_RESET" "$*"; }
warn() { printf '  %s!%s %s\n' "$C_YELLOW" "$C_RESET" "$*"; }
fail() { printf '%s✘ %s%s\n' "$C_RED" "$*" "$C_RESET" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }
doppler_logged_in() { have doppler && [ -n "$(doppler configure get token --plain 2>/dev/null)" ]; }

confirm() {
    [ "$ASSUME_YES" -eq 1 ] && return 0
    [ "$NON_INTERACTIVE" -eq 1 ] && return 1
    local reply
    read -r -p "  $1 [y/N] " reply
    case "$reply" in [yY]|[yY][eE][sS]) return 0 ;; *) return 1 ;; esac
}

usage() { sed -n '2,/^set -euo/p' "${BASH_SOURCE[0]}" | sed '$d' | sed 's/^# \{0,1\}//'; }

# ── Argument parsing ──────────────────────────────────────────────────────────
while [ $# -gt 0 ]; do
    case "$1" in
        --skip-system)      SKIP_SYSTEM=1 ;;
        --with-services)    WITH_SERVICES=1 ;;
        --migrate)          RUN_MIGRATE=1 ;;
        --github-secrets)   GITHUB_SECRETS=1 ;;
        --doppler-project)  DOPPLER_PROJECT_ARG="${2:?missing value}"; shift ;;
        --doppler-config)   DOPPLER_CONFIG_ARG="${2:?missing value}"; shift ;;
        --configuration)    DJANGO_CONFIGURATION_ARG="${2:?missing value}"; shift ;;
        --force-envrc)      FORCE_ENVRC=1 ;;
        -y|--yes)           ASSUME_YES=1 ;;
        --no-interactive)   NON_INTERACTIVE=1 ;;
        -h|--help)          usage; exit 0 ;;
        *)                  fail "Unknown option: $1 (see --help)" ;;
    esac
    shift
done

# These end up as assignments in the generated .envrc, which direnv / `source`
# executes, so reject anything that isn't a plain name (they're also written
# with shell quoting - see write_envrc).
[[ "$DJANGO_CONFIGURATION_ARG" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] \
    || fail "--configuration must be a settings class name, e.g. Development (got: $DJANGO_CONFIGURATION_ARG)"
for _doppler_name in "$DOPPLER_PROJECT_ARG" "$DOPPLER_CONFIG_ARG"; do
    [[ "$_doppler_name" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*$ ]] \
        || fail "Invalid Doppler project/config name: $_doppler_name"
done

[ -t 0 ] || NON_INTERACTIVE=1
if [ "$NON_INTERACTIVE" -eq 1 ]; then
    # Keep package managers from stopping to ask questions.
    export DEBIAN_FRONTEND=noninteractive NONINTERACTIVE=1 HOMEBREW_NO_AUTO_UPDATE=1
fi

cd "$REPO_ROOT"
mkdir -p "$LOCAL_BIN"
case ":$PATH:" in *":$LOCAL_BIN:"*) ;; *) export PATH="$LOCAL_BIN:$PATH" ;; esac

OS="$(uname -s)"
# SUDO is "" when running as root, a sudo command when one is usable, and
# NO_SUDO when privileged installs are impossible (not root and no sudo, or
# sudo would need a password under --no-interactive).
SUDO=""
if [ "$(id -u)" -ne 0 ]; then
    if ! have sudo; then
        SUDO="NO_SUDO"
    elif [ "$NON_INTERACTIVE" -eq 1 ]; then
        # Non-interactive: never block on a password prompt.
        if sudo -n true 2>/dev/null; then SUDO="sudo -n"; else SUDO="NO_SUDO"; fi
    else
        SUDO="sudo"
    fi
fi

# ── 1. System packages ────────────────────────────────────────────────────────
install_system_packages() {
    step "System packages"
    if [ "$SKIP_SYSTEM" -eq 1 ]; then
        warn "Skipped (--skip-system). Needed: libpq, libmagic, curl, git."
        return
    fi
    if [ "$OS" = "Linux" ] && [ "$SUDO" = "NO_SUDO" ]; then
        warn "Skipped: not root and no usable sudo (missing, or needs a password under --no-interactive). Needed: libpq, libmagic, curl, git."
        return
    fi
    case "$OS" in
        Darwin)
            have brew || fail "Homebrew is required on macOS: https://brew.sh"
            brew install libpq libmagic git curl
            ok "brew: libpq libmagic git curl"
            ;;
        Linux)
            if have apt-get; then
                $SUDO apt-get update -qq
                $SUDO apt-get install -y --no-install-recommends \
                    libpq5 libmagic1 curl ca-certificates gnupg git \
                    postgresql-client redis-tools
                ok "apt: libpq5 libmagic1 curl git postgresql-client redis-tools"
            elif have dnf; then
                $SUDO dnf install -y libpq file-libs curl ca-certificates git postgresql redis
                ok "dnf: libpq file-libs curl git postgresql redis"
            elif have pacman; then
                $SUDO pacman -S --needed --noconfirm postgresql-libs file curl git redis
                ok "pacman: postgresql-libs file curl git redis"
            else
                warn "Unknown package manager — install libpq, libmagic, curl and git yourself."
            fi
            ;;
        *) warn "Unsupported OS '$OS' — install libpq, libmagic, curl and git yourself." ;;
    esac
}

# ── 2. Tooling ────────────────────────────────────────────────────────────────
install_uv() {
    if have uv; then ok "uv $(uv --version | awk '{print $2}')"; return; fi
    curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    have uv || fail "uv install failed"
    ok "uv installed"
}

install_task() {
    if have task; then ok "task $(task --version 2>/dev/null | awk '{print $NF}')"; return; fi
    if [ "$OS" = "Darwin" ] && have brew; then
        brew install go-task
    else
        sh -c "$(curl --location --silent https://taskfile.dev/install.sh)" -- -d -b "$LOCAL_BIN"
    fi
    have task || fail "Task install failed"
    ok "task installed"
}

install_doppler() {
    if have doppler; then ok "doppler $(doppler --version)"; return; fi
    if [ "$OS" = "Darwin" ] && have brew; then
        brew install gnupg dopplerhq/cli/doppler
    elif { [ -n "$SUDO" ] && [ "$SUDO" != "NO_SUDO" ]; } || [ "$(id -u)" -eq 0 ]; then
        curl -Ls --tlsv1.2 --proto "=https" --retry 3 https://cli.doppler.com/install.sh | $SUDO sh
    else
        curl -Ls --tlsv1.2 --proto "=https" --retry 3 https://cli.doppler.com/install.sh \
            | sh -s -- --install-path "$LOCAL_BIN"
    fi
    have doppler || fail "Doppler CLI install failed"
    ok "doppler installed"
}

install_direnv() {
    if have direnv; then ok "direnv $(direnv version)"; return; fi
    # Package managers only when allowed (no --skip-system) and privileged
    # installs are possible; otherwise a user-local binary in ~/.local/bin.
    if [ "$SKIP_SYSTEM" -ne 1 ] && [ "$OS" = "Darwin" ] && have brew; then
        brew install direnv
    elif [ "$SKIP_SYSTEM" -ne 1 ] && have apt-get && [ "$SUDO" != "NO_SUDO" ]; then
        $SUDO apt-get install -y --no-install-recommends direnv
    else
        curl -sfL https://direnv.net/install.sh | env bin_path="$LOCAL_BIN" bash
    fi
    have direnv && ok "direnv installed — add 'eval \"\$(direnv hook bash)\"' (or zsh) to your shell rc" \
                || warn "direnv not installed (optional)"
}

install_tooling() {
    step "Tooling (uv, Task, Doppler, direnv)"
    install_uv
    install_task
    install_doppler
    install_direnv
}

# ── 3. Python + dependencies ──────────────────────────────────────────────────
install_python_deps() {
    step "Python $PYTHON_VERSION and project dependencies"
    uv python install "$PYTHON_VERSION"
    ok "Python $PYTHON_VERSION available"
    if [ ! -d .venv ]; then
        uv venv --python "$PYTHON_VERSION" --prompt="ACTIVE_VENV_DJANGO_DOZENS"
    fi
    # Same as `task install` and the CI composite action; --locked fails fast
    # if uv.lock is out of date instead of silently re-resolving.
    uv sync --locked --python "$PYTHON_VERSION" --group test --group dev
    ok "uv sync (test + dev groups) complete"
}

# ── 4. pre-commit ─────────────────────────────────────────────────────────────
install_precommit() {
    step "pre-commit hook"
    if [ ! -f .configs/.pre-commit-config.yaml ]; then
        warn ".configs/.pre-commit-config.yaml not found — skipping"
        return
    fi
    if [ -n "$(git config --get core.hooksPath 2>/dev/null || true)" ]; then
        warn "core.hooksPath is set ($(git config --get core.hooksPath)); installing there"
        .venv/bin/pre-commit install -f -c .configs/.pre-commit-config.yaml
    else
        .venv/bin/pre-commit install -f -c .configs/.pre-commit-config.yaml
    fi
    ok "pre-commit installed (config: .configs/.pre-commit-config.yaml)"
}

# ── 5. Environment (.envrc + Doppler + validation) ────────────────────────────
write_envrc() {
    step "Environment file (.envrc)"
    if [ -f .envrc ] && [ "$FORCE_ENVRC" -ne 1 ]; then
        ok ".envrc already exists — left untouched (use --force-envrc to regenerate)"
        return
    fi
    # .envrc is gitignored. It never stores DOPPLER_TOKEN: the CLI's own
    # login (`doppler login` + `doppler setup`) scopes access to this
    # directory, so no secret ends up on disk in the repo.
    # Values are validated at startup and written %q-quoted on top of that.
    local q_configuration q_project q_config
    q_configuration="$(printf '%q' "$DJANGO_CONFIGURATION_ARG")"
    q_project="$(printf '%q' "$DOPPLER_PROJECT_ARG")"
    q_config="$(printf '%q' "$DOPPLER_CONFIG_ARG")"
    cat > .envrc <<EOF
# Generated by scripts/install.sh — gitignored, safe to edit.
export DJANGO_CONFIGURATION=${q_configuration}
export DJANGO_SETTINGS_MODULE="core.settings"
export PYTHONPATH="\$PWD"
export PYTHONUNBUFFERED=1
export PATH="\$PWD/.venv/bin:\$HOME/.local/bin:\$PATH"

export DOPPLER_PROJECT=${q_project}
export DOPPLER_CONFIG=${q_config}

# Local Postgres/Redis (scripts/install.sh --with-services). Doppler values
# override these unless you run it with --preserve-env, as CI does.
export PG_DATABASE_HOST="\${PG_DATABASE_HOST:-localhost}"
export PG_DATABASE_PORT="\${PG_DATABASE_PORT:-5432}"
export PG_DATABASE_USER="\${PG_DATABASE_USER:-root}"
export PG_DATABASE_PASSWORD="\${PG_DATABASE_PASSWORD:-postgres}"
export POSTGRES_DB="\${POSTGRES_DB:-test_db}"
export USE_REDIS_CACHE="\${USE_REDIS_CACHE:-true}"
export REDIS_CACHE_TOKEN="\${REDIS_CACHE_TOKEN:-redis://localhost:6379/0}"

# Pull secrets from Doppler: with DOPPLER_TOKEN when it's set (a service
# token, as scripts/with_doppler.sh and CI use), otherwise when the CLI is
# logged in for this directory.
if command -v doppler >/dev/null 2>&1; then
    if [ -n "\${DOPPLER_TOKEN:-}" ]; then
        eval "\$(doppler secrets download --no-file --format env --token "\$DOPPLER_TOKEN")"
    elif [ -n "\$(doppler configure get token --plain 2>/dev/null)" ]; then
        eval "\$(doppler secrets download --no-file --format env \\
            --project "\$DOPPLER_PROJECT" --config "\$DOPPLER_CONFIG")"
    fi
fi
EOF
    ok "Wrote .envrc (DJANGO_CONFIGURATION=$DJANGO_CONFIGURATION_ARG, Doppler $DOPPLER_PROJECT_ARG/$DOPPLER_CONFIG_ARG)"
    if have direnv; then direnv allow . >/dev/null 2>&1 && ok "direnv allow ."; fi
}

setup_doppler() {
    step "Doppler ($DOPPLER_PROJECT_ARG / $DOPPLER_CONFIG_ARG)"
    if [ -n "${DOPPLER_TOKEN:-}" ]; then
        ok "DOPPLER_TOKEN is set in the environment (scripts/with_doppler.sh will use it)"
        return
    fi
    if doppler_logged_in; then
        ok "Doppler CLI is logged in"
    elif [ "$NON_INTERACTIVE" -eq 0 ] && confirm "Doppler is not logged in. Run 'doppler login' now?"; then
        doppler login
    else
        warn "Not logged in. Run: doppler login && doppler setup -p $DOPPLER_PROJECT_ARG -c $DOPPLER_CONFIG_ARG"
        return
    fi
    doppler setup --no-interactive --project "$DOPPLER_PROJECT_ARG" --config "$DOPPLER_CONFIG_ARG" >/dev/null \
        && ok "doppler setup scoped to $REPO_ROOT" \
        || warn "doppler setup failed — check that you have access to $DOPPLER_PROJECT_ARG/$DOPPLER_CONFIG_ARG"
}

# Names of secrets available from Doppler (empty if not configured).
doppler_secret_names() {
    have doppler || return 0
    local token_args=""
    [ -n "${DOPPLER_TOKEN:-}" ] && token_args="--token $DOPPLER_TOKEN"
    # shellcheck disable=SC2086
    doppler secrets download --no-file --format env $token_args \
        --project "$DOPPLER_PROJECT_ARG" --config "$DOPPLER_CONFIG_ARG" 2>/dev/null \
        | sed -n 's/^\([A-Z_][A-Z0-9_]*\)=.*/\1/p' || true
}

check_group() {
    local label="$1" vars="$2" level="$3" names="$4" missing=""
    local v
    for v in $vars; do
        if [ -n "${!v:-}" ] || printf '%s\n' "$names" | grep -qx "$v"; then :; else
            missing="$missing $v"
        fi
    done
    if [ -z "$missing" ]; then
        ok "$label: all set"
    elif [ "$level" = "required" ]; then
        warn "$label — MISSING:$missing"
        MISSING_REQUIRED=1
    else
        printf '  %s· %s — unset:%s%s\n' "$C_DIM" "$label" "$missing" "$C_RESET"
    fi
}

validate_env() {
    step "Environment variable check"
    local names
    names="$(doppler_secret_names)"
    if [ -n "$names" ]; then
        ok "Checking shell env + Doppler $DOPPLER_PROJECT_ARG/$DOPPLER_CONFIG_ARG"
    else
        warn "Doppler not reachable — checking the current shell environment only"
    fi
    MISSING_REQUIRED=0
    check_group "Required (all configurations)" "$REQUIRED_VARS"   required "$names"
    check_group "Database (Development/Production)" "$DATABASE_VARS" required "$names"
    check_group "Production only"               "$PRODUCTION_VARS" optional "$names"
    check_group "Optional"                      "$OPTIONAL_VARS"   optional "$names"
    if [ "$MISSING_REQUIRED" -eq 1 ]; then
        warn "Add the missing values to Doppler ($DOPPLER_PROJECT_ARG/$DOPPLER_CONFIG_ARG) or export them in .envrc."
    fi
}

# ── 6. Local services ─────────────────────────────────────────────────────────
# Ports are published on 127.0.0.1 only: the fixed root/postgres credentials
# match CI and the Staging defaults, so the database must not be reachable
# from other hosts. Containers created by older versions of this script
# published on every interface; docker can't change that in place.
warn_if_exposed() {
    local container="$1" port="$2" binding
    while read -r binding; do
        case "$binding" in
            127.0.0.1:*|"") ;;
            *) warn "$container publishes $port on $binding (all interfaces). Recreate it: docker rm -f $container && scripts/install.sh --with-services"
               return ;;
        esac
    done < <(docker port "$container" "$port/tcp" 2>/dev/null || true)
}

start_services() {
    step "Local Postgres + Redis"
    if [ "$WITH_SERVICES" -ne 1 ]; then
        warn "Skipped (use --with-services, or open the dev container)."
        return
    fi
    have docker || fail "Docker is required for --with-services"
    if docker ps -a --format '{{.Names}}' | grep -qx "$PG_CONTAINER"; then
        docker start "$PG_CONTAINER" >/dev/null
    else
        docker run -d --name "$PG_CONTAINER" --restart unless-stopped \
            -e POSTGRES_USER=root -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=test_db \
            -p 127.0.0.1:5432:5432 -v dozens-pgdata:/var/lib/postgresql/data "$PG_IMAGE" >/dev/null
    fi
    warn_if_exposed "$PG_CONTAINER" 5432
    ok "$PG_CONTAINER ($PG_IMAGE) on 127.0.0.1:5432 — root/postgres, db test_db"
    if docker ps -a --format '{{.Names}}' | grep -qx "$REDIS_CONTAINER"; then
        docker start "$REDIS_CONTAINER" >/dev/null
    else
        docker run -d --name "$REDIS_CONTAINER" --restart unless-stopped \
            -p 127.0.0.1:6379:6379 "$REDIS_IMAGE" >/dev/null
    fi
    warn_if_exposed "$REDIS_CONTAINER" 6379
    ok "$REDIS_CONTAINER ($REDIS_IMAGE) on 127.0.0.1:6379"

    printf '  waiting for Postgres'
    local i
    for i in $(seq 1 30); do
        if docker exec "$PG_CONTAINER" pg_isready -U root -d test_db >/dev/null 2>&1; then
            printf ' ready\n'; return
        fi
        printf '.'; sleep 1
    done
    printf '\n'; warn "Postgres did not become ready within 30s"
}

# ── 7. Database ───────────────────────────────────────────────────────────────
run_migrations() {
    step "Database migrations"
    if [ "$RUN_MIGRATE" -ne 1 ]; then
        warn "Skipped (use --migrate, or run: task django -- migrate)"
        return
    fi
    # Same entrypoint as `task db_sync`, minus makemigrations — an installer
    # should apply committed migrations, not generate new ones.
    if [ "$WITH_SERVICES" -eq 1 ]; then
        # Target the container started above, and keep a Doppler config that
        # names another database from redirecting this migrate to it.
        PG_DATABASE_HOST=localhost PG_DATABASE_PORT=5432 PG_DATABASE_USER=root \
            PG_DATABASE_PASSWORD=postgres POSTGRES_DB=test_db \
            DOPPLER_PRESERVE_EXTRA="PG_DATABASE_HOST,PG_DATABASE_PORT,PG_DATABASE_USER,PG_DATABASE_PASSWORD,POSTGRES_DB" \
            DJANGO_CONFIGURATION="$DJANGO_CONFIGURATION_ARG" PYTHONPATH="$REPO_ROOT" \
            ./scripts/with_doppler.sh .venv/bin/python3 run/manage.py migrate
        ok "migrate complete (local database localhost:5432/test_db)"
    else
        warn "No --with-services: migrating the database from the environment/Doppler ($DOPPLER_PROJECT_ARG/$DOPPLER_CONFIG_ARG)"
        DJANGO_CONFIGURATION="$DJANGO_CONFIGURATION_ARG" PYTHONPATH="$REPO_ROOT" \
            ./scripts/with_doppler.sh .venv/bin/python3 run/manage.py migrate
        ok "migrate complete"
    fi
}

# ── 8. GitHub Actions secrets / variables ─────────────────────────────────────
setup_github() {
    step "GitHub Actions secrets and variables"
    if [ "$GITHUB_SECRETS" -ne 1 ]; then
        printf '  %sThe CI workflow needs (set with --github-secrets or in repo Settings → Secrets and variables → Actions):%s\n' "$C_DIM" "$C_RESET"
        printf '    secrets:   %s\n' "$GH_SECRETS"
        printf '    variables: %s\n' "$GH_VARIABLES"
        printf '    (GITHUB_TOKEN is provided by Actions automatically)\n'
        return
    fi
    have gh || fail "GitHub CLI (gh) is required for --github-secrets"
    gh auth status >/dev/null 2>&1 || fail "Run 'gh auth login' first"
    local repo name value existing
    repo="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
    if [ "$NON_INTERACTIVE" -eq 1 ]; then
        # Passing --github-secrets is the opt-in; values come from the environment.
        ok "Non-interactive: reading values from environment variables for $repo"
    else
        confirm "Set Actions secrets/variables on $repo?" || { warn "Skipped"; return; }
    fi

    existing="$(gh secret list --repo "$repo" --json name -q '.[].name' 2>/dev/null || true)"
    for name in $GH_SECRETS; do
        if printf '%s\n' "$existing" | grep -qx "$name"; then
            confirm "Secret $name already exists. Replace it?" || { ok "$name kept"; continue; }
        fi
        if [ "$NON_INTERACTIVE" -eq 1 ]; then
            value="${!name:-}"
        else
            read -r -s -p "  $name (blank to skip): " value; printf '\n'
        fi
        [ -z "$value" ] && { warn "$name skipped"; continue; }
        printf '%s' "$value" | gh secret set "$name" --repo "$repo" --body - >/dev/null
        ok "secret $name set"
    done

    existing="$(gh variable list --repo "$repo" --json name -q '.[].name' 2>/dev/null || true)"
    for name in $GH_VARIABLES; do
        local default=""
        case "$name" in
            DOPPLER_PROJECT) default="$DOPPLER_PROJECT_ARG" ;;
            DOPPLER_CONFIG)  default="$DOPPLER_CONFIG_ARG" ;;
            *)               default="${!name:-}" ;;
        esac
        if printf '%s\n' "$existing" | grep -qx "$name"; then
            confirm "Variable $name already exists. Replace it?" || { ok "$name kept"; continue; }
        fi
        if [ "$NON_INTERACTIVE" -eq 1 ]; then
            value="$default"
        else
            read -r -p "  $name [${default}]: " value
            value="${value:-$default}"
        fi
        [ -z "$value" ] && { warn "$name skipped"; continue; }
        gh variable set "$name" --repo "$repo" --body "$value" >/dev/null
        ok "variable $name=$value"
    done
}

# ── Summary ───────────────────────────────────────────────────────────────────
summary() {
    step "Done"
    cat <<EOF
  Next steps:
    direnv allow .                 # or: source .envrc
    task run:dev                   # gunicorn --reload on 127.0.0.1:8000
    task test:coverage             # pytest against Postgres (Staging config)
    task lint:lint                 # same linters as CI
    task django -- createsuperuser

  To run tests exactly like CI (local Postgres/Redis, Doppler secrets):
    doppler run --preserve-env -- task test:coverage
EOF
}

main() {
    printf '%sThe Dozens API — local install%s (%s)\n' "$C_BLUE" "$C_RESET" "$REPO_ROOT"
    install_system_packages
    install_tooling
    install_python_deps
    install_precommit
    write_envrc
    setup_doppler
    validate_env
    start_services
    run_migrations
    setup_github
    summary
}

main
