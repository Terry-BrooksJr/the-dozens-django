FROM python:3.11-slim-bookworm AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libmagic1 \
    curl \
    ca-certificates \
    gnupg \
    && curl -Ls --tlsv1.2 --proto "=https" --retry 3 https://cli.doppler.com/install.sh | sh \
    && rm -rf /var/lib/apt/lists/* \
    && install -D -m 0755 "$(command -v doppler)" /opt/bin/doppler

COPY --from=ghcr.io/astral-sh/uv:0.12.18 /uv /usr/local/bin/uv

WORKDIR /src

# Runtime dependencies only (no dev/test groups), exactly as pinned in uv.lock.
# The venv lives outside /src so the final stage can copy it on its own.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-default-groups --no-install-project

# -----------------------------------------------------------
FROM python:3.11-slim-bookworm

ARG DJANGO_CONFIGURATION="Production"
ENV DJANGO_CONFIGURATION=${DJANGO_CONFIGURATION} \
    DJANGO_SETTINGS_MODULE=core.settings \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --shell /bin/bash --create-home api

WORKDIR /src

# Copy the virtualenv and the Doppler CLI from builder
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/bin/doppler /usr/local/bin/doppler
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY --chown=api:api applications ./applications
COPY --chown=api:api common ./common
COPY --chown=api:api core ./core
COPY --chown=api:api run ./run
COPY --chown=api:api schema ./schema
COPY --chown=api:api static ./static
COPY --chown=api:api templates ./templates
COPY --chown=api:api .deploy/gunicorn.conf.py  ./.deploy/gunicorn.conf.py

ENV PYTHONPATH="/src:/src/applications/API:/src/applications/graphQL:/src/applications/frontend:/src/common:/src/run"

RUN mkdir -p /src/logs && chown api:api /src/logs

USER api

EXPOSE 9555

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:9555/api/health/ || exit 1

CMD ["doppler", "run", "--", "gunicorn", "-c", ".deploy/gunicorn.conf.py", "core.wsgi:application"]
