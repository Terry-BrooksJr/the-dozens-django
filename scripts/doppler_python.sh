#!/usr/bin/env bash
# Python interpreter shim for VS Code / debugpy launch configs.
#
# debugpy launches `<python> <launcher> ... -- <program> <args>` directly, so
# nothing runs `doppler run` and no secrets get injected. Pointing a launch
# config's "python" at this script wraps the interpreter itself in
# `doppler run`, so the debuggee process gets the Doppler secrets.
#
# Uses DOPPLER_TOKEN when set; otherwise falls back to the local CLI login
# and the project/config scoped to this directory via `doppler setup`.
# --preserve-env=DJANGO_CONFIGURATION keeps the launch config's selected
# settings class from being overridden by a same-named Doppler secret.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -n "${DOPPLER_TOKEN:-}" ]; then
    exec doppler run --preserve-env=DJANGO_CONFIGURATION -t "${DOPPLER_TOKEN}" -- "${ROOT}/.venv/bin/python" "$@"
else
    exec doppler run --preserve-env=DJANGO_CONFIGURATION -- "${ROOT}/.venv/bin/python" "$@"
fi
