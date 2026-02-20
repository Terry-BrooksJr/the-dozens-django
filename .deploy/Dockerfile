FROM python:3.11-slim-bookworm AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --timeout=300 -r requirements.txt

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

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=api:api applications ./applications
COPY --chown=api:api common ./common
COPY --chown=api:api core ./core
COPY --chown=api:api run ./run
COPY --chown=api:api schema ./schema
COPY --chown=api:api static ./static
COPY --chown=api:api templates ./templates
COPY --chown=api:api .deploy/gunicorn.ini ./.deploy/gunicorn.ini

ENV PYTHONPATH="/src:/src/applications/API:/src/applications/graphQL:/src/applications/frontend:/src/common:/src/run"

RUN mkdir -p /src/logs && chown api:api /src/logs

USER api

EXPOSE 9090

CMD ["gunicorn", "-c", ".deploy/gunicorn.ini"]
