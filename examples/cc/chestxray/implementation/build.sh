#!/bin/bash
# Builds the confidential benchmark script image and makes it reachable.
#
# Not part of any test: MedPerf pulls whatever image a benchmark names, so the
# image has to already exist somewhere it can be pulled from. Publishing to
# mlcommons is the eventual answer; until then this serves it from a registry on
# this machine, which is what the container config points at.
set -eo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_IMAGE="${BASE_IMAGE:-mlcommons/medperf-confidential-benchmark-base:0.0.0}"
IMAGE="${IMAGE:-localhost:5555/medperf-cc-chestxray:test}"
REGISTRY_PORT="${REGISTRY_PORT:-5555}"
REGISTRY_CONTAINER="${REGISTRY_CONTAINER:-medperf-cc-test-registry}"

docker build -t "$BASE_IMAGE" "$HERE/../../base_image"
docker build -t "$IMAGE" "$HERE"

if [[ "$IMAGE" == localhost:* ]]; then
    if ! docker ps --format '{{.Names}}' | grep -q "^${REGISTRY_CONTAINER}$"; then
        docker rm -f "$REGISTRY_CONTAINER" >/dev/null 2>&1 || true
        docker run -d --name "$REGISTRY_CONTAINER" \
            -p "127.0.0.1:${REGISTRY_PORT}:5000" registry:2
        sleep 3
    fi
fi

docker push "$IMAGE"
echo "Pushed $IMAGE"
