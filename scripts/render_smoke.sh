#!/usr/bin/env bash
# Runs render.yaml's build and start commands exactly as written, as Render does (from the
# repo root, with PORT set), then waits for /api/ready to answer 200.
#
# Run from the repo root with DATABASE_URL and the API settings in the environment. Needs
# yq (preinstalled on GitHub's runners) and a Python on PATH whose pip may install uv.
set -euo pipefail

build="$(yq -e '.services[0].buildCommand' render.yaml)"
start="$(yq -e '.services[0].startCommand' render.yaml)"
export PORT="${PORT:-10000}"
ready="http://127.0.0.1:${PORT}/api/ready"

echo "Build: $build"
bash -c "$build"

echo "Start: $start"
bash -c "$start" &
server=$!
trap 'kill "$server" 2>/dev/null || true' EXIT

for _ in $(seq 120); do
  if ! kill -0 "$server" 2>/dev/null; then
    echo "The start command exited before $ready answered." >&2
    exit 1
  fi
  if curl -sSf "$ready"; then
    echo
    echo "Ready"
    exit 0
  fi
  sleep 1
done
echo "$ready did not answer 200 within 120 seconds." >&2
curl -sS "$ready" || true
exit 1
