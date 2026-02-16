#!/usr/bin/env bash
set -o errexit
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

exec gunicorn backend.wsgi:application --bind 0.0.0.0:${PORT:-10000}
