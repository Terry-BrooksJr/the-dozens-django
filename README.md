# The Dozens — Django/DRF API

A playful, production‑ready REST API for “yo momma” style jokes (aka *Insults*), built with **Django 5** and **Django REST Framework**. It ships with token auth, robust filtering, schema‑first API docs (OpenAPI 3 via **drf‑spectacular**), caching, pagination, linting/type‑checking, and a container‑friendly runtime. 

> TL;DR: Run `task install && task db_sync && task run:dev 8888` and hit `http://127.0.0.1:8888/api/insults/`.

---

## Table of Contents

- [The Dozens — Django/DRF API](#the-dozens--djangodrf-api)
  - [Table of Contents](#table-of-contents)
  - [Demo \& Status](#demo--status)
  - [Features](#features)
  - [Architecture](#architecture)
  - [Tech Stack](#tech-stack)
  - [Getting Started](#getting-started)
    - [Prerequisites](#prerequisites)
    - [Environment](#environment)
    - [Install \& Run](#install--run)
  - [Task Runner (Taskfile.yml)](#task-runner-taskfileyml)
  - [Configuration](#configuration)
  - [API Overview](#api-overview)
    - [List insults''](#list-insults)
    - [List insults by category](#list-insults-by-category)
    - [Retrieve / Update / Delete](#retrieve--update--delete)
    - [Random insult'](#random-insult)
    - [List categories](#list-categories)
    - [Authentication](#authentication)
  - [Schema \& Docs](#schema--docs)
  - [Caching \& Performance](#caching--performance)
  - [Testing \& Linting](#testing--linting)
  - [Deployment](#deployment)
  - [Project Layout](#project-layout)
  - [Troubleshooting](#troubleshooting)
  - [Contributing](#contributing)
  - [License](#license)

---

## Demo & Status

- **Local dev**: `http://127.0.0.1:8888/`
- **OpenAPI/Swagger**: served by **drf‑spectacular** (see [Schema & Docs](#schema--docs))

This is an actively developed project; expect frequent improvements.

## Features

- **Insults domain**: CRUD for jokes, categories, NSFW flagging, ownership, and reporting relationships.
- **Typed & documented**: Serializer and view docstrings with fully described OpenAPI responses and examples.
- **Pagination & filtering**: DRF pagination + `django-filter` (NSFW, category, status, user‑specific views).
- **Token auth**: Owner‑only mutating operations; read endpoints are public by default.
- **Caching**: Bulk list caching and model‑aware cache invalidation. Redis/Dragonfly compatible.
- **Schema‑first**: Validated OpenAPI 3 docs via **drf‑spectacular** and `task schema`.
- **Ops‑ready**: Taskfile‑driven workflows, Docker image build, Prometheus hooks, bandit security scan.

## Architecture

- **applications/API/** — models, serializers, endpoints (views), filters, permissions.
- **applications/graphQL/** — (optional) GraphQL surface if/when enabled.
- **common/** — cross‑cutting concerns (e.g., caching mixins, performance helpers).
- **run/manage.py** — entrypoint for management commands.
- **core/** — Django project settings, URLs, WSGI.

Key models:
- `Insult` — content, category, status, nsfw, added_by, timestamps.
- `InsultCategory` — short key (`P`), human name (`Poor`).
- `InsultReview` — moderation/review data.

## Tech Stack

- **Python 3.11+**, **Django 5.x**, **Django REST Framework**
- **drf‑spectacular** for OpenAPI 3
- **django‑filters**, **django‑extensions** (optional), **loguru** for logging
- **Redis/Dragonfly** for caching (via Django cache backend)
- **Gunicorn** for WSGI
- **Poetry** for dependency management
- **Taskfile** for repeatable commands

## Getting Started

### Prerequisites

- Python 3.11+
- Redis/Dragonfly running locally (or a hosted Redis‑compatible service)
- Postgres 13+ (recommended)
- [Doppler](https://www.doppler.com/) CLI if you use secrets syncing (optional but supported)

### Environment
Create a `.envrc` or export the following (the Taskfile expects some of these):

```env
DOPPLER_TOKEN=....            # Optional if using Doppler
PATH_TO_DB_ROOT_CERT=/path/to/root.crt
TEMP_STATIC_DIR=.tmp_static
DJANGO_SETTINGS_MODULE=core.settings
DATABASE_URL=postgres://user:pass@localhost:5432/dozens
CACHE_URL=redis://localhost:6379/0         # or dragonfly
SECRET_KEY=change-me
DEBUG=1
ALLOWED_HOSTS=127.0.0.1,localhost
```

> The Taskfile also sets `PYTHON_PATH` to include the app modules so imports Just Work™ in dev.

### Install & Run

```bash
# 1) Create venv + install deps
$ task install

# 2) Create/Run migrations
$ task db_sync

# 3) Start the server (dev, auto‑reload); default binds to 127.0.0.1:<PORT>
$ task run:dev 8888

# Collect static (if needed)
$ task collect
```

Visit `http://127.0.0.1:8888/`.

## Task Runner (Taskfile.yml)

Common tasks (see full list with `task`):

[!NOTE] This required the installation of Taskfile, a Go-Based Task Agent. For More Details - [Taskfile](https://taskfile.dev/)

- `task install` — creates venv, installs Poetry deps.
- `task db_sync` — `makemigrations` + `migrate`.
- `task run:dev <port>` — gunicorn in reload mode (debug‑friendly).
- `task run:test` — run API tests for `applications.API`.
- `task collect` — collect static for prod packaging.
- `task schema` — validate & emit OpenAPI schema file under `schema/`.
- `task lint:lint` — autoflake, isort, black, ruff, pylint, bandit, mypy, djlint.
- `task lint:fix` — auto‑fix formatting/linting where safe.
- `task django -- <cmd>` — pass‑through to `manage.py` (e.g., `task django -- createsuperuser`).
- `task build-image` — Docker Buildx (multi‑arch) with Doppler build arg.

## Configuration

- **Settings** are in `core/settings.py`. Adjust DB/cache backends as needed.
- **Cache**: Use a Redis‑compatible service. Keys are prefixed and invalidated by pattern (see mixins).
- **Auth**: Token authentication is enabled for mutating endpoints. Generate a token via djoser or DRF token auth.

## API Overview

Base path examples use `http://127.0.0.1:8888`.

### List insults''

**GET** `/api/insults/`

Query params:
- `nsfw` — `true|false` (optional)
- `page`, `page_size` — pagination

> If you include a category in this endpoint, you’ll get `400` with guidance to use the category route.

Example:
```bash
curl -s 'http://127.0.0.1:8888/api/insults/?nsfw=false' | jq
```

### List insults by category

**GET** `/api/insults/<category_name>/`

- `category_name` accepts either the **key** (e.g., `P`) or **name** (e.g., `Poor`).

Example:
```bash
curl -s 'http://127.0.0.1:8888/api/insults/Poor/' | jq
```

### Retrieve / Update / Delete

**GET/PUT/PATCH/DELETE** `/api/insults/<reference_id>/`

- Read is public; write requires token and ownership.

Example (retrieve):
```bash
curl -s 'http://127.0.0.1:8888/api/insults/SNICKER_NDc4/' | jq
```

Example (update):
```bash
curl -X PATCH \
  -H 'Authorization: Token <YOUR_TOKEN>' \
  -H 'Content-Type: application/json' \
  -d '{"content":"Yo momma is so cloud‑native…"}' \
  'http://127.0.0.1:8888/api/insults/SNICKER_NDc4/'
```

### Random insult'

**GET** `/api/insults/random/`

Query params:

- `nsfw` — `true|false` (optional)
- `category` — category name or key (optional)

Example:

```bash
curl -s 'http://127.0.0.1:8888/api/insults/random/?nsfw=false' | jq
```

### List categories

**GET** `/api/categories/`

Returns a mapping of available categories (key → name) for client UIs.

### Authentication

- **Read**: public.
- **Create/Update/Delete**: requires token. Include header:

```bash
Authorization: Token <YOUR_TOKEN>
```

## Schema & Docs

- Generate and validate the OpenAPI schema:

```bash
# Validates and writes a timestamped schema file to ./schema/
$ task schema
```

- Integrate with your preferred Swagger/Redoc UI using the generated schema, or wire up `SPECTACULAR_SETTINGS` to serve `/schema/` and `/docs/` in development.

## Caching & Performance

- Bulk list endpoints leverage a `CachedResponseMixin` for cache keys that include filters and pagination.
- Cache invalidation patterns cover `Insult:*`, bulk lists, categories, and per‑user lists.
- Category lookups are normalized so users can pass either a key (`P`) or the human name (`Poor`).

## Testing & Linting

```bash
# Run API tests
$ task run:test

# Check everything
$ task lint:lint

# Auto‑fix what’s safe
$ task lint:fix
```

Type‑checking is enforced with **mypy**. Security scanning via **bandit**. Pylint is configured with `pylint_django` and `pylint_celery`.

## Deployment

- **Prod entry**: `task run:prod 8080` installs deps, migrates, and runs gunicorn with 2 workers/threads.
- **Docker image**: `task build-image` builds a multi‑arch image. You can adapt the tag/registry in `.deploy/Dockerfile` and the Taskfile.
- **Static files**: `task collect` to gather static assets for production serving.

## Project Layout

```bash
.
├── applications
│   ├── API
│   │   ├── endpoints.py
│   │   ├── serializers.py
│   │   ├── models.py
│   │   ├── filters.py
│   │   └── permissions.py
│   ├── graphQL
│   └── frontend
├── common
│   └── performance.py
├── core
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── run
│   └── manage.py
├── schema/
├── templates/
├── Taskfile.yml
└── README.md
```

## Troubleshooting

- **401 when creating/updating**: Ensure you’re sending `Authorization: Token <token>` and that the token user matches the insult owner.
- **Category validation errors**: You can pass either the category **name** or **key**; the API normalizes internally.
- **Redis/Dragonfly connection**: Confirm `CACHE_URL` and that the cache service is reachable.
- **OpenAPI warnings**: Run `task schema` and address any serializer/view annotations flagged by drf‑spectacular.

## Contributing

PRs and issues are welcome! Please run `task lint:fix` before submitting and include tests for behavior changes.

## License

MIT (see `LICENSE`).

---

**Have fun, and be kind** — even when roasting like a pro. 😄