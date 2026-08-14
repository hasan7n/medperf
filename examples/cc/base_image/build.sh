#!/bin/bash
# Builds the confidential benchmark base image.
#
# Use this rather than a bare `docker build`: the integrity statement contract
# is not kept here. It is `cc/medperf_cc/statement.py`, the same file whoever
# verifies a proof runs, and it is staged into the build context so that the
# producing and the verifying side cannot drift apart. Building without it
# leaves the image unable to import `statement`.
set -eo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE="${IMAGE:-mlcommons/medperf-confidential-benchmark-base:0.0.0}"
CONTRACT="$HERE/../../../cc/medperf_cc/statement.py"

if [[ ! -f "$CONTRACT" ]]; then
    echo "Cannot find the integrity statement contract at $CONTRACT" >&2
    exit 1
fi

cp "$CONTRACT" "$HERE/src/statement.py"
trap 'rm -f "$HERE/src/statement.py"' EXIT

docker build -t "$IMAGE" "$HERE"

if [[ -n "${PUSH:-}" ]]; then
    docker push "$IMAGE"
fi
