FROM python:3.12-slim-bullseye

RUN apt-get update && apt-get install -y --no-install-recommends apt-transport-https ca-certificates libmagic1 curl libenchant-2-dev gnupg make git && \
    curl -sLf --retry 3 --tlsv1.2 --proto "=https" 'https://packages.doppler.com/public/cli/gpg.DE2A7741A397C129.key' | gpg --dearmor -o /usr/share/keyrings/doppler-archive-keyring.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/doppler-archive-keyring.gpg] https://packages.doppler.com/public/cli/deb/debian any-version main" | tee /etc/apt/sources.list.d/doppler-cli.list && \
    apt-get update && \
    apt-get --no-install-recommends -y install doppler=3.68.0 build-essential  && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ARG DOPPLER_TOKEN
ARG DOPPLER_PROJECT="yo-mama"
ARG DOPPLER_CONFIG="prod"
ARG DJANGO_CONFIGURATION="Production"

WORKDIR /src/app
EXPOSE 9090

RUN useradd --shell /bin/bash --create-home api
COPY --chown=api:api ./requirements/base.txt ./requirements.txt
COPY --chown=api:api \
    applications \
    common \
    core \
    run \
    schema \
    static \
    templates \
    Taskfile.yml \
    /src/

RUN python -m pip install --no-cache-dir -r ./requirements.txt && \
    mkdir -p /src/app/.doppler && \
    chown api:api /src/app/.doppler && \
    chmod 770 /src/app/.doppler

ENTRYPOINT [ "task", "start" ]
