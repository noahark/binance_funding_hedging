# Design: .env Startup Path V1

## Design Decision

Use the shell startup script as the only `.env` loader. Python config reads only
the current process environment through `from_env()`.

Reasoning:

- Review and test commands should not accidentally parse local secrets.
- Runtime operators can still use a simple `.env` file locally.
- The service can also run in environments where variables are injected by a
  process manager, container, or host shell.

## Private Channel Gate

API key presence and private-channel enablement are separate conditions:

```text
BINANCE_API_KEY / BINANCE_API_SECRET present
AND BINANCE_PRIVATE_CHANNEL_ENABLED=true
AND APP_OFFLINE=false
```

Only when all three conditions hold may `SnapshotService` construct the private
client with key/secret. If any condition is false, private rows degrade through
the existing disabled/unverified path.

## Environment Names

Primary runtime variables use concise local names:

- `APP_BIND_HOST`
- `APP_BIND_PORT`
- `APP_TOP_N`
- `APP_CACHE_TTL_SECONDS`
- `APP_OFFLINE`
- `APP_OFFLINE_RAW_DIR`
- `APP_REQUEST_TIMEOUT`
- `BINANCE_API_KEY`
- `BINANCE_API_SECRET`
- `BINANCE_PRIVATE_CHANNEL_ENABLED`
- `BINANCE_RECV_WINDOW`
- `BINANCE_PRIVATE_CHANNEL_TTL_SECONDS`
- `BINANCE_PRIVATE_CHANNEL_FAST_TTL_SECONDS`
- `BINANCE_BORROW_CHECK_MAX_CALLS`

`FUNDING_HEDGING_*` aliases are accepted in `from_env()` for app settings that
may later need namespace isolation.

## Startup Script

`scripts/run-server.sh`:

- finds repository root,
- loads `$ENV_FILE` or `.env` with `set -a`,
- refuses to start when private channel is enabled without key/secret,
- uses `$PYTHON` when provided, otherwise prefers `.venv/bin/python` when
  available, then falls back to `python3`,
- executes the selected Python as `-m backend.app.server`.

## Evidence Boundary

This stage intentionally does not create `.env`. The only committed template is
`.env.example`.

本地北京时间: 2026-07-06 20:46:01 CST
下一步模型: Codex/GPT
下一步任务: Review the implementation and tests against this design.
