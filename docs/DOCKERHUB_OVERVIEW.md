# The Dozens API

A REST and GraphQL API for "yo momma" jokes (called *insults* in the API), built with **Django 5**, **Django REST Framework** and **Gunicorn** on **Python 3.14**.

[![CI Pipeline](https://github.com/Terry-BrooksJr/the-dozens-django/actions/workflows/commit_check.yaml/badge.svg)](https://github.com/Terry-BrooksJr/the-dozens-django/actions/workflows/commit_check.yaml)
[![Codacy Grade](https://app.codacy.com/project/badge/Grade/70f7aef1a778458f8553b024aa0f80fe)](https://app.codacy.com/gh/Terry-BrooksJr/the-dozens-django/dashboard)

- **Source:** https://github.com/Terry-BrooksJr/the-dozens-django
- **Issues:** https://github.com/Terry-BrooksJr/the-dozens-django/issues
- **License:** MIT

---

## Tags

| Tag | Description |
|-----|-------------|
| `latest` | The latest successful build of `master`. |
| `sha-<commit>` | An immutable build of a single commit, such as `sha-711d113`. Pin to one of these in production. |

Images are built and pushed by GitHub Actions only after lint, tests and the security scan pass on `master`. Every image ships with an **SBOM** and **SLSA provenance** attestation:

```bash
docker buildx imagetools inspect terrybrooks/the-dozens:latest --format '{{ json .SBOM }}'
```

## What's in the image

- `python:3.14-slim-bookworm` multi-stage build, with only the runtime libraries kept (`libpq5`, `libmagic1`)
- Runs as the non-root user **`api`**
- **Gunicorn** (`gthread`, 4 workers × 4 threads) listening on **port 9555**
- A built-in `HEALTHCHECK` against `GET /api/health/`
- The **Doppler CLI**, so secrets can be injected at runtime (see [Using Doppler](#using-doppler))
- Prometheus metrics aggregated across all Gunicorn workers (multiprocess mode)

## Quick start

The container needs **PostgreSQL**, a **Redis-compatible cache** (Redis or Dragonfly) and **S3-compatible object storage** for static files. Put your configuration in an env file (see [Environment variables](#environment-variables)), then run:

```bash
docker run -d --name dozens \
  -p 9555:9555 \
  --env-file ./dozens.env \
  terrybrooks/the-dozens:latest
```

Apply the database migrations once, and again after each upgrade:

```bash
docker exec dozens python run/manage.py migrate
```

Check that it's up:

```bash
curl http://localhost:9555/api/health/
```

```bash
curl 'http://localhost:9555/api/v2.0.0/insults/random/?nsfw=false'
```

### Docker Compose

```yaml
services:
  api:
    image: terrybrooks/the-dozens:latest
    ports:
      - "9555:9555"
    env_file: ./dozens.env
    environment:
      PG_DATABASE_HOST: db
      PG_DATABASE_PORT: "5432"
      REDIS_CACHE_TOKEN: redis://cache:6379/0
    depends_on:
      - db
      - cache

  db:
    image: postgres:17
    environment:
      POSTGRES_DB: dozens
      POSTGRES_USER: dozens
      POSTGRES_PASSWORD: change-me
    volumes:
      - pgdata:/var/lib/postgresql/data

  cache:
    image: redis:7-alpine

volumes:
  pgdata:
```

## Environment variables

The image defaults to the `Production` configuration (`DJANGO_CONFIGURATION=Production`). Set every variable marked **required**. Some are secrets that stop Django from starting if they're missing. The rest have no defaults, so leaving them out breaks the feature that uses them.

### Core

| Variable | Required | Description |
|----------|:--------:|-------------|
| `SECRET_KEY` | ✅ | Django secret key. |
| `ALLOWED_HOSTS` | ✅ | Comma-separated hostnames, such as `api.example.com,localhost`. |
| `ALLOWED_ORIGINS` | | Origins trusted for CSRF (`CSRF_TRUSTED_ORIGINS`). Set this to your public `https://` origins, or admin POSTs return 403. |
| `SITE_ID` | ✅ | Django sites framework ID (usually `1`). |
| `DJANGO_CONFIGURATION` | | `Production` (default), `Staging`, `Development` or `Offline`. |
| `API_VERSION` | | The version shown in the OpenAPI schema. |

### Database (PostgreSQL)

| Variable | Required | Description |
|----------|:--------:|-------------|
| `POSTGRES_DB` | ✅ | Database name. |
| `PG_DATABASE_USER` | ✅ | Database user. |
| `PG_DATABASE_PASSWORD` | ✅ | Database password. |
| `PG_DATABASE_HOST` | ✅ | Database host. |
| `PG_DATABASE_PORT` | ✅ | Database port (usually `5432`). |

### Cache

| Variable | Required | Description |
|----------|:--------:|-------------|
| `REDIS_CACHE_TOKEN` | ✅* | Redis/Dragonfly connection URL, such as `redis://cache:6379/0`. |
| `USE_REDIS_CACHE` | | Set to `false` to use the in-process memory cache instead (*then `REDIS_CACHE_TOKEN` isn't needed*). |
| `CACHE_KEY_PREFIX` | | A prefix for every cache key. |
| `CACHE_TTL` | ✅ | View cache TTL in seconds, such as `600`. The service won't start without it. |

### Object storage (S3-compatible)

Static files are served from object storage in production, so run `collectstatic` against your bucket before going live.

| Variable | Required | Description |
|----------|:--------:|-------------|
| `S3_OBJECT_STORAGE_KEY` | ✅ | Access key ID. |
| `S3_OBJECT_STORAGE_SECRET` | ✅ | Secret access key. |
| `S3_OBJECT_STORAGE_BUCKET_NAME` | ✅ | Bucket name. |
| `S3_ENDPOINT_URL` | ✅ | Endpoint URL (AWS, Backblaze B2, DigitalOcean Spaces, MinIO and so on). |
| `S3_REGION_NAME` | ✅ | Region. |

### Integrations

| Variable | Required | Description |
|----------|:--------:|-------------|
| `GITHUB_ACCESS_TOKEN` | ✅ | Opens GitHub issues for reported insults. |
| `RECAPTCHA_PUBLIC_KEY` | ✅ | reCAPTCHA site key. |
| `RECAPTCHA_PRIVATE_KEY` | ✅ | reCAPTCHA secret key. |
| `EMAIL_SERVER` | ✅ | SMTP host. |
| `EMAIL_TSL_PORT` | ✅ | SMTP TLS port. |
| `NOTIFICATION_SENDER_EMAIL` | ✅ | The "From" address for notifications. |
| `EMAIL_ACCT_PASSWORD` | ✅ | SMTP password. |
| `MAILER_EMPTY_QUEUE_SLEEP` | ✅ | Seconds the mail queue worker waits between polls when the queue is empty, such as `30`. |
| `EMAIL_ASSET_BASE_URL` | | Public base URL for images in emails. |

### Observability

| Variable | Required | Description |
|----------|:--------:|-------------|
| `METRICS_SCRAPE_TOKEN` | | Bearer token Prometheus must send to scrape `/metrics`. When it's unset, `/metrics` denies every request. |
| `LOKI_URL` / `LOKI_PASSWORD` | | Ship structured logs to Grafana Loki. |
| `LAUNCHDARKLY_ENABLED` | | `true` to turn on LaunchDarkly feature flags. |
| `LAUNCHDARKLY_SDK_KEY` | | LaunchDarkly server-side SDK key. |
| `LAUNCHDARKLY_OBSERVABILITY_ENABLED` | | `true` to forward logs to LaunchDarkly Observability. |
| `LAUNCHDARKLY_SERVICE_NAME` / `LAUNCHDARKLY_SERVICE_VERSION` | | Service name and version tags for shipped telemetry. |

Logs always go to stdout, so `docker logs dozens` works with no extra setup.

## Using Doppler

The Doppler CLI is installed in the image. Instead of an env file, you can pass a service token and wrap the default command:

```bash
docker run -d -p 9555:9555 \
  -e DOPPLER_TOKEN=dp.st.xxxx \
  terrybrooks/the-dozens:latest \
  doppler run -- gunicorn -c .deploy/gunicorn.conf.py core.wsgi:application
```

## Endpoints

| Path | Description |
|------|-------------|
| `/api/v2.0.0/insults/` | List, filter (`category`, `nsfw`) and create insults |
| `/api/v2.0.0/insults/random/` | A random insult |
| `/api/v2.0.0/insults/<reference_id>/` | Retrieve, update or delete one insult |
| `/api/v2.0.0/categories/` | Available categories |
| `/api/v2.0.0/reports/` | Report an insult for moderation |
| `/graphql/` | GraphQL API with the GraphiQL playground |
| `/api/swagger/`, `/api/redoc/`, `/api/schema/` | OpenAPI 3 docs and schema |
| `/api/health/`, `/api/ping/` | Health and liveness probes |
| `/metrics` | Prometheus metrics (requires the bearer token) |
| `/auth/` | Token auth: sign-up, login and logout (djoser) |

Reads are public. Creating, updating and deleting insults requires `Authorization: Token <token>`, and you can only change insults you own. Anonymous requests are limited to 4 per minute and authenticated requests to 12 per minute.

## Running behind a reverse proxy

The `Production` configuration expects TLS to end at a reverse proxy (such as Traefik or nginx) and trusts `X-Forwarded-Proto` and `X-Forwarded-Host`. Don't expose port 9555 directly to the internet. Put it behind a proxy that sets these headers.

## Management commands

```bash
docker exec -it dozens python run/manage.py createsuperuser
```

```bash
docker exec dozens python run/manage.py collectstatic --noinput
```

The Django admin is at `/ops-gateway/`.

---

**Have fun, and be kind**, even when you're roasting like a pro. 😄
