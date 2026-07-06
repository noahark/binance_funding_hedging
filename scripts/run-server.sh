#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-"$ROOT_DIR/.env"}"
if [ -n "${PYTHON:-}" ]; then
  PYTHON_BIN="$PYTHON"
elif [ -x "$ROOT_DIR/.venv/bin/python" ]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
else
  PYTHON_BIN="python3"
fi

cd "$ROOT_DIR"

if [ -f "$ENV_FILE" ]; then
  # Export variables defined in .env for backend.config.from_env().
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
else
  echo "No .env found at $ENV_FILE; starting with environment/defaults." >&2
fi

if [ "${BINANCE_PRIVATE_CHANNEL_ENABLED:-false}" = "true" ]; then
  if [ -z "${BINANCE_API_KEY:-}" ] || [ -z "${BINANCE_API_SECRET:-}" ]; then
    echo "BINANCE_PRIVATE_CHANNEL_ENABLED=true requires BINANCE_API_KEY and BINANCE_API_SECRET." >&2
    exit 2
  fi
fi

exec "$PYTHON_BIN" -m backend.app.server
