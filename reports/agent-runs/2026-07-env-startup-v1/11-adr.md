# ADR: Explicit Private Channel Switch for .env Startup

## Status

Proposed for review.

## Context

The project needs a practical local startup path using `.env` because Binance
private read-only endpoints will be required for account balance, borrowability,
and interest-cost display. The user's real API key may have broad permissions,
so code-level endpoint and channel gating remain important even with IP
whitelisting and a private repository.

## Decision

1. Keep real `.env` files untracked.
2. Commit only `.env.example`.
3. Load `.env` only in `scripts/run-server.sh`.
4. Add `BINANCE_PRIVATE_CHANNEL_ENABLED=false` as the default.
5. Do not initialize private-channel credentials unless the flag is explicitly
   true and offline mode is false.

## Consequences

- Local startup is simple: edit `.env`, run `scripts/run-server.sh`.
- Accidentally leaving key/secret in the shell does not enable private requests.
- Tests and review commands avoid implicit `.env` parsing.
- Deployment can later inject the same variables through systemd, Docker, or a
  managed secret store without changing application code.

本地北京时间: 2026-07-06 20:46:01 CST
下一步模型: Codex/GPT
下一步任务: Validate that implementation follows this ADR.
