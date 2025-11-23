FROM terrybrooksjr/base-image:py3.13

ARG DOPPLER_TOKEN
ARG DOPPLER_PROJECT="yo-mama"
ARG DOPPLER_CONFIG="prod"
ARG DJANGO_CONFIGURATION="Production"

ENV DJANGO_CONFIGURATION=${DJANGO_CONFIGURATION}

WORKDIR /src/app

RUN chmod 770 /src/app/.doppler

ENTRYPOINT [ "task", "start" ]
EXPOSE 9090

RUN useradd --shell /bin/bash --create-home api
COPY --chown=api:api ./requirements.txt ./requirements.txt
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