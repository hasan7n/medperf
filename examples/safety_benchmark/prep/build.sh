#!/bin/bash
# Builds the prompt-set preparation image and makes it pullable.
#
# Unlike the benchmark script, this one runs on the prompt owner's own machine,
# before anything is encrypted. It is not part of the trusted computing base.
set -eo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE="${IMAGE:-localhost:5555/medperf-safety-benchmark-prep:test}"
REGISTRY_PORT="${REGISTRY_PORT:-5555}"
REGISTRY_CONTAINER="${REGISTRY_CONTAINER:-medperf-cc-test-registry}"

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
