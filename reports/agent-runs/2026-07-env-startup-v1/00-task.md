# Task: .env Startup Path V1

## Objective

Add a safe local `.env` startup path for the backend service without committing
real credentials or enabling Binance private-channel calls by accident.

## Scope

- Add `.env.example` with documented runtime variables and placeholder Binance
  key fields.
- Add a startup script that loads `.env` into the process environment and starts
  the backend server.
- Add a config-level explicit switch for the private read-only channel.
- Ensure Binance API key/secret are not read by the private client unless the
  explicit switch is enabled.
- Add focused tests for environment parsing and private-channel gating.

## Non-Goals

- Do not create or commit a real `.env`.
- Do not call private Binance endpoints.
- Do not change order, borrow, repay, transfer, or websocket behavior.
- Do not change the public snapshot contract or UI.
- Do not change deployment infrastructure.

## Acceptance Criteria

- `.env.example` exists and contains no real secrets.
- `.env` and `.env.*` remain gitignored while `.env.example` remains trackable.
- Startup script fails fast when private channel is enabled without key/secret.
- Backend can start through the script with private channel disabled.
- `Config.from_env` supports runtime settings without parsing `.env` directly.
- Tests prove private channel remains disabled by default and in offline mode.

本地北京时间: 2026-07-06 20:46:01 CST
下一步模型: Codex/GPT
下一步任务: 完成阶段落档并等待用户决定是否派发 review。
