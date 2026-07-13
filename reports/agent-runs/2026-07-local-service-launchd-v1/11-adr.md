# ADR — Native macOS LaunchAgent For Local Service

## Status

Approved direction; implementation pending mandatory development breakdown.

## Context

The existing `scripts/run-server.sh` safely loads `.env` and then replaces
itself with the Python server, but it remains attached to the launching terminal
or tool session. There is no persistent PID/exit/log evidence, so a later model
cannot reconstruct why the service disappeared.

The backend already serves the frontend and API from one same-origin process.

## Decision

Use one user-level macOS LaunchAgent to manage the existing single process.
Keep `.env` loading in `scripts/run-server.sh`. Add persistent stdout/stderr,
read-only status/doctor tooling, and secret-free health/readiness routes.

Actual installation remains a human external-side-effect gate. Auto review is
authorized only for repository changes and review-1 evidence.

## Rejected Alternatives

- `nohup`/`disown`: detached but weak lifecycle, restart, status, and evidence.
- A second frontend daemon: contradicts the current same-origin server and adds
  failure modes without value.
- Docker Compose in v1: cross-platform packaging is useful later but adds image,
  volume, secret, networking, and macOS VM lifecycle work unnecessary for this
  local workstation goal.
- Root LaunchDaemon: unnecessary privilege and a worse secret boundary.
- Handwritten PID files: duplicate and weaker authority than launchd.
- Automatic live watchdog restart: deferred until crash-restart behavior and
  diagnostics have real pilot evidence.

## Consequences

- Terminal closure no longer owns service lifetime.
- Process exits are restartable and diagnostically visible.
- Logs remain local and outside Git.
- Service installation is macOS-specific; a later deployment stage may add
  Docker/systemd without changing application configuration semantics.
- In-memory cache still resets after restart.

本地北京时间: 2026-07-13 12:35:49 CST
下一步模型: Claude Fable5（human dispatch）
下一步任务: 冻结实现边界、命令构造与无真实 launchctl 副作用的测试策略
