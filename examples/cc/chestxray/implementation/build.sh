#!/bin/bash
# Builds the confidential benchmark script image and publishes it.
#
# Not part of any test: MedPerf pulls whatever image a benchmark names, so the
# image has to already exist in a registry it can be pulled from. A run
# therefore executes the published tag, never this working tree -- bump the
# version in IMAGE and in container_config.yaml, then rerun this, after any
# change under benchmark/.
set -eo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_IMAGE="${BASE_IMAGE:-mlcommons/medperf-confidential-benchmark-base:0.0.0}"
IMAGE="${IMAGE:-mlcommons/medperf-cc-chestxray:0.0.1}"

IMAGE="$BASE_IMAGE" bash "$HERE/../../base_image/build.sh"
docker build -t "$IMAGE" "$HERE"

docker push "$IMAGE"
echo "Pushed $IMAGE"
