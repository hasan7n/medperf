#!/bin/bash
# Spawns the grader as a localhost HTTP endpoint.
set -eo pipefail
exec python3 "$(cd "$(dirname "$0")" && pwd)/server.py" "$@"
