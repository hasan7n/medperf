#!/bin/bash
# Builds the safety benchmark script image and publishes it.
#
# MedPerf pulls whatever image a benchmark names, so a run executes the
# published tag rather than this working tree. After any change under
# benchmark/, bump the version in IMAGE and in container_config.yaml and rerun
# this.
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
IMAGE="${IMAGE:-mlcommons/medperf-safety-benchmark:0.0.0}"
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

docker push "$IMAGE"
echo "Pushed $IMAGE"
