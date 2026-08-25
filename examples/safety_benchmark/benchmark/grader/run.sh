#!/bin/bash
# Spawns the grader as a localhost HTTP endpoint.
#
# The grader's weights ship inside the image, so unlike the model under test
# there is nothing to point it at. GRADER_MODEL_PATH overrides that for local
# development, where downloading 16GB into the build context is unwelcome.
#
# GRADER_LLAMA_GUARD_VERSION says which prompt format those weights expect.
# Baked in at build time by build.sh, so a run cannot disagree with the image.
set -eo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$HERE/server.py" \
    --model-path "${GRADER_MODEL_PATH:-$HERE/weights}" \
    --llama-guard-version "${GRADER_LLAMA_GUARD_VERSION:-2}" \
    "$@"
