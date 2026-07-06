# Handoff: .env Startup Path V1

## Current State

- Stage: `2026-07-env-startup-v1`
- Branch: `stage/2026-07-env-startup-v1`
- Base HEAD: `afd9e377be2035272bc9cc33f7ec84cc99b16f49`
- Status: implementation and tests complete; checkpoint commit pending; formal
  review not started.

## What Changed

The backend now has an explicit `.env` startup path:

- `.env.example` documents local variables.
- `scripts/run-server.sh` sources `.env` and starts `python3 -m backend.app.server`.
- The script honors `$PYTHON`, otherwise prefers `.venv/bin/python`, then
  falls back to system `python3`.
- `backend.config.from_env()` maps process env to `Config`.
- `BINANCE_PRIVATE_CHANNEL_ENABLED` defaults to false.
- `SnapshotService` does not read `BINANCE_API_KEY` / `BINANCE_API_SECRET`
  unless private channel is explicitly enabled and offline mode is false.

## Verification

Passed:

- `python3 -m py_compile ...`
- `bash -n scripts/run-server.sh`
- `pytest backend/tests/test_config.py`
- `pytest backend/tests/`
- `node frontend/self-check.js`
- `git diff --check`
- startup script probe with private channel disabled
- local ignored `.env` startup probe on 8799 with `APP_OFFLINE=false` and
  `BINANCE_PRIVATE_CHANNEL_ENABLED=false`; `/api/public-market/snapshot`
  returned `schema_version=public-market-snapshot/v1`, 648 rows, and
  `sort_basis=abs_daily_funding_rate`.
- local ignored `.env` private-enabled smoke probe on 8787 after the user set
  `BINANCE_PRIVATE_CHANNEL_ENABLED=true`; `/api/public-market/snapshot` returned
  `private_channel=enabled`, `sort_basis=net_daily_yield`, 648 rows, 638
  `borrow_validation.verified=true` rows, and 10 bounded-probe omissions from
  `rate_limit_budget`.

## Local .env State

An ignored local `.env` now exists for runtime testing. The user populated local
Binance credentials and set `BINANCE_PRIVATE_CHANNEL_ENABLED=true` for the
private-enabled smoke probe. The file remains ignored by git and key values are
not recorded in any stage artifact.

To test the real private read-only panel later, edit `.env` locally:

```bash
BINANCE_API_KEY=<your key>
BINANCE_API_SECRET=<your secret>
BINANCE_PRIVATE_CHANNEL_ENABLED=true
APP_OFFLINE=false
```

Then run:

```bash
scripts/run-server.sh
```

Do not paste real key values into model prompts or reports.

## Review Notes

This stage is a checkpoint commit, not a formal accepted stage. A formal Harness
review still requires a clean committed state, standard diff fingerprint, and
review artifacts.

Recommended next step:

1. Update the stage to a formal review state if the user wants to enter review.
2. Run `scripts/validate-stage.py 2026-07-env-startup-v1 --phase pre-review`
   after status is updated to a review state with base/head/fingerprint.
3. Dispatch review on raw diff and these stage artifacts.

本地北京时间: 2026-07-06 22:35:04 CST
下一步模型: user
下一步任务: Decide whether to commit this small stage and dispatch review.
