#!/usr/bin/env bash
# Runs "$@" through `doppler run` when Doppler is actually configured
# (DOPPLER_TOKEN is set), otherwise runs it directly - trusting that the
# required environment variables are already present some other way (a
# plain `export` in the shell, an .envrc that doesn't use Doppler, or
# secrets already injected by the caller, e.g. CI wrapping the whole `task`
# invocation in its own `doppler run --preserve-env`). This keeps basic
# local development and test workflows from hard-depending on an external
# service while still using Doppler automatically whenever it's available.
#
# --preserve-env=DJANGO_CONFIGURATION keeps whatever DJANGO_CONFIGURATION a
# task's own `env:` block set from being clobbered by a same-named value in
# the Doppler config, so the selected Django settings class is never
# silently swapped out from under a task.
set -euo pipefail

if [ -n "${DOPPLER_TOKEN:-}" ]; then
    exec doppler run --preserve-env=DJANGO_CONFIGURATION -t "${DOPPLER_TOKEN}" -- "$@"
else
    exec "$@"
fi
