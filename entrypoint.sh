#!/usr/bin/env bash

cd "${HOME}" || exit 1

gunicorn --workers="${GUNICORN_WORKERS:-2}" --threads="${GUNICORN_THREADS:-2}" thedozens.wsgi:application -b :8080 || exit 1
