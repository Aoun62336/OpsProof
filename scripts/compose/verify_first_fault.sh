#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "$0")/.."

restore_worker() {
  docker compose start worker >/dev/null 2>&1 || true
}

trap restore_worker EXIT

echo "Stopping the background worker..."
docker compose stop worker

echo "Submitting jobs while the worker is unavailable..."
uv run --no-project --python 3.14 \
  python -m scripts.compose.verify_demo outage-submit

echo "Restarting the worker..."
docker compose start worker

echo "Verifying that queued jobs complete..."
uv run --no-project --python 3.14 \
  python -m scripts.compose.verify_demo outage-verify

trap - EXIT

echo "Worker-outage verification completed."

