# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

**The Dozens Django** is a RESTful roast/insult API (like "Yo Mama" jokes) converted from Flask RestX to Django REST Framework. The API provides both REST endpoints and GraphQL queries for retrieving categorized insults, with built-in content moderation, user authentication, and comprehensive monitoring.

## Quick Start

1. **Environment Setup**: Ensure you have Doppler CLI installed and configured with project tokens
2. **Installation**: `task install` (installs Poetry dependencies)
3. **Database**: `task db_sync` (runs migrations)  
4. **Development Server**: `task run:dev -- 8000` (starts on port 8000)

## Essential Commands

| Command | Purpose | Notes |
|---------|---------|-------|
| `task install` | Install dependencies via Poetry | Creates venv, installs packages |
| `task run:dev -- <port>` | Start development server | Default uses gunicorn with reload |
| `task run:prod -- <port>` | Start production server | Includes install, migrate, serve |
| `task db_sync` | Make and run migrations | Requires DOPPLER_TOKEN, PATH_TO_DB_ROOT_CERT |
| `task run:test` | Run test suite | Runs Django tests for applications.API |
| `task lint:lint` | Run all linting checks | Black, ruff, pylint, mypy, bandit, djlint |
| `task lint:fix` | Auto-fix linting issues | Runs autoflake, isort, black, ruff --fix |
| `task collect` | Collect static files | For production deployment |
| `task schema` | Generate OpenAPI schema | Creates timestamped schema.yaml |
| `task build-image` | Build multi-arch Docker image | Requires DOPPLER_TOKEN |
| `task django -- <cmd>` | Django management commands | Wrapper for `python run/manage.py <cmd>` |

**Single Test Example**: `task django -- test applications.API.tests.test_endpoints.TestInsultEndpoint.test_random_insult`

## Architecture Overview

The project follows Django's app-based architecture with three main applications:

- **`applications/API`**: Django REST Framework endpoints for insult CRUD operations, filtering, and random selection
- **`applications/graphQL`**: GraphQL schema using Graphene-Django for alternative query interface  
- **`applications/frontend`**: Template-based views, GitHub issue reporting, and home page

**Core Infrastructure**:
- **`core/`**: Django settings (multi-environment via django-configurations), URL routing, WSGI/ASGI setup
- **`common/`**: Shared utilities including GenericDataCacheManager for Redis caching, Prometheus metrics facade
- **`run/`**: Management commands entry point with coverage integration

**Data Flow**: Requests → Django middleware → DRF/GraphQL → Models (Insult, InsultCategory, InsultReview) → PostgreSQL/Redis → Response with Prometheus metrics

## Environment Configurations

The project uses **django-configurations** with four environment classes:

- **Production**: Full security, Highlight.io logging, rate limiting (4/min anon, 12/min user)
- **Development**: Debug toolbar, relaxed CORS, lower rate limits (1/min anon, 6/min user)  
- **Offline**: Same as Development but for fully disconnected environments
- **Testing**: Minimal configuration for test runs

**Key Environment Variables** (managed via Doppler):
- `SECRET_KEY`, `SITE_ID`, `CACHE_TTL`
- `POSTGRES_DB`, `PG_DATABASE_USER`, `PG_DATABASE_PASSWORD`, `PG_DATABASE_HOST`, `PG_DATABASE_PORT`
- `REDIS_CACHE_TOKEN`, `PATH_TO_DB_ROOT_CERT`
- `DO_SPACES_KEY`, `DO_SPACES_SECRET`, `DO_SPACES_BUCKET` (DigitalOcean Spaces for static files)
- `ALLOWED_HOSTS`, `ALLOWED_ORIGINS` (production domains)
- `TEMP_STATIC_DIR` (local static collection directory)

## Dependencies & Tooling

**Package Management**: Poetry for dependency resolution, with `task freeze` to export requirements.txt files

**Secret Management**: Doppler CLI injects environment variables into all task commands

**Database**: PostgreSQL primary, django-cockroachdb for CockroachDB compatibility

**Caching**: Redis with django-redis backend, prometheus metrics on cache operations

**Web Server**: Gunicorn with configurable workers/threads for production

**Linting/Formatting Pipeline**:
- **black**: Code formatting
- **ruff**: Fast linting with auto-fix capability  
- **mypy**: Static type checking with django-stubs
- **pylint**: Comprehensive linting with pylint-django plugin
- **bandit**: Security vulnerability scanning
- **djlint**: Django template linting and formatting
- **autoflake**: Remove unused imports/variables

**Pre-commit Hooks**: Configured in `.configs/.pre-commit-config.yaml` for automated formatting

## Testing & QA Workflow

**Test Framework**: Django's built-in test runner with pytest-django compatibility

**Coverage**: Automatic coverage reporting during test runs (via `run/manage.py`)

**Test Execution**:
```bash
task run:test                    # Full API test suite
task django -- test <path>      # Specific test path
task django -- test --keepdb    # Preserve test DB between runs
```

**QA Checklist**:
1. `task lint:fix` - Auto-fix formatting issues
2. `task lint:lint` - Verify all linting passes  
3. `task run:test` - Ensure tests pass
4. `task schema` - Validate OpenAPI schema compliance

## Copilot/Codacy Integration Rules

**CRITICAL: After ANY file edit**, you MUST run `codacy_cli_analyze` tool with:
- `rootPath`: workspace path
- `file`: path of edited file  
- If issues found, propose and apply fixes immediately

**After dependency changes** (npm install, pip install, etc.), you MUST run `codacy_cli_analyze` with:
- `rootPath`: workspace path
- `tool`: "trivy"
- Stop other work if vulnerabilities found until resolved

**General Guidelines**:
- Never manually install Codacy CLI (use MCP Server tool)
- Don't analyze for code complexity or coverage changes
- If 404 error, offer to run `codacy_setup_repository` tool
- Use non-URL-encoded file paths for `rootPath` parameter

## Deployment

**Docker Build**: Multi-architecture image build with BuildKit
```bash
task build-image  # Builds for linux/amd64 and linux/arm64
```

**Production Deployment Flow**:
1. `task run:prod` - Install deps, run migrations, start server
2. Static files collected to DigitalOcean Spaces via `STATICFILES_STORAGE`
3. Gunicorn serves on a configurable port (default 8080)
4. Prometheus metrics exposed on `/metrics` endpoint

**Infrastructure Requirements**:
- PostgreSQL database with connection pooling
- Redis instance for caching and sessions
- DigitalOcean Spaces (S3-compatible) for static/media files
- Doppler project configured with production secrets
- SSL termination (proxy/load balancer handles HTTPS)

**Health Checks**: 
- Django admin at `/admin/`
- API documentation at `/api/swagger/` and `/api/redoc/`
- Prometheus metrics at `/metrics`
- Debug toolbar (development only) at `/__debug__/`

## Architecture Notes

**Insult Management**: Core `Insult` model with status workflow (PENDING → ACTIVE/REJECTED/FLAGGED), automatic reference ID generation, and NSFW categorization

**Caching Strategy**: Multi-level caching with module-level + Redis via `GenericDataCacheManager`, automatic invalidation on model changes

**API Design**: RESTful endpoints with filtering, pagination, random selection, and comprehensive OpenAPI documentation via drf-spectacular

**Security**: Token authentication, rate limiting, CSRF protection, content validation, and security scanning via bandit

This Django project emphasizes developer productivity with comprehensive tooling, multi-environment support, and production-ready infrastructure patterns.
