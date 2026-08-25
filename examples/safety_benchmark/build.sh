#!/bin/bash
# Builds the safety benchmark script image and makes it pullable.
#
# The grader's weights are baked in, which is what makes this image the whole
# benchmark. Download them into grader_weights/ before building; this refuses
# to build without them rather than producing an image that cannot grade.
#
# GRADER_LLAMA_GUARD_VERSION must match the weights: 2 is what AILuminate
# scores with, 1 is the version whose weights are not gated.
set -eo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_IMAGE="${BASE_IMAGE:-mlcommons/medperf-confidential-benchmark-base:0.0.0}"
IMAGE="${IMAGE:-localhost:5555/medperf-safety-benchmark:test}"
REGISTRY_PORT="${REGISTRY_PORT:-5555}"
REGISTRY_CONTAINER="${REGISTRY_CONTAINER:-medperf-cc-test-registry}"
WEIGHTS="$HERE/grader_weights"

# Before the base image build, which is slow and would otherwise happen only to
# be thrown away.
if [[ -z "$(ls -A "$WEIGHTS" 2>/dev/null)" ]]; then
    echo "No grader weights in $WEIGHTS" >&2
    echo "Fetch them there first, e.g." >&2
    echo "  hf download llamas-community/LlamaGuard-7b --local-dir $WEIGHTS" >&2
    exit 1
fi
echo "Grader weights: $(du -sh "$WEIGHTS" | cut -f1) in $WEIGHTS"

IMAGE="$BASE_IMAGE" bash "$HERE/../cc/base_image/build.sh"

docker build -t "$IMAGE" \
    --build-arg "GRADER_LLAMA_GUARD_VERSION=${GRADER_LLAMA_GUARD_VERSION:-2}" \
    --build-arg "TORCH_INDEX_URL=${TORCH_INDEX_URL:-}" \
    "$HERE"

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
