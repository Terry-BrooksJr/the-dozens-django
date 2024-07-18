FROM python:3.12-slim-bullseye as builder

RUN apt-get update && apt-get install -y --no-install-recommends apt-transport-https ca-certificates libmagic1 curl libenchant-2-dev gnupg make git && \
    curl -sLf --retry 3 --tlsv1.2 --proto "=https" 'https://packages.doppler.com/public/cli/gpg.DE2A7741A397C129.key' | gpg --dearmor -o /usr/share/keyrings/doppler-archive-keyring.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/doppler-archive-keyring.gpg] https://packages.doppler.com/public/cli/deb/debian any-version main" | tee /etc/apt/sources.list.d/doppler-cli.list && \
    apt-get update && \
    apt-get --no-install-recommends -y install doppler=3.68.0 build-essential  && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN  ["doppler", "run", "--", "printenv"]
ARG DOPPLER_TOKEN
ARG DOPPLER_PROJECT
ARG DOPPLER_CONFIG