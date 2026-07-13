# Design — launchd Single-Service Local Deployment

## 1. Outcome

The local workstation gets one user-level LaunchAgent that manages the existing
single Python HTTP process. Closing the terminal no longer stops the service;
process exits are restarted with throttling; stdout/stderr and a bounded doctor
bundle make later failures traceable.

This design does not turn the workstation into a public production deployment.

## 2. Process Topology

```text
macOS user launchd domain
  -> com.aoke.funding-hedging.server
     -> /bin/bash <repo>/scripts/run-server.sh
        -> exec <python> -m backend.app.server
           -> same-origin frontend static files
           -> /api/*
           -> /healthz and /readyz
           -> in-process snapshot worker
```

Only the main server process is managed. The existing frontend requires no
build server, Node daemon, CORS configuration, or second lifecycle.

## 3. Repository Artifacts

Expected implementation files:

```text
deploy/launchd/com.aoke.funding-hedging.server.plist.template
scripts/service-control.py
scripts/run-server.sh
scripts/tests/test_service_control.py
backend/app/server.py
backend/tests/test_service_health.py
```

`scripts/service-control.py` owns rendering and operator subcommands. Using
Python `plistlib` or an equivalently safe XML mechanism is preferred over raw
shell substitution so paths containing spaces and XML metacharacters remain
valid.

## 4. LaunchAgent Contract

The rendered user plist is installed only by an explicit human command at:

```text
~/Library/LaunchAgents/com.aoke.funding-hedging.server.plist
```

Required semantics:

- label: `com.aoke.funding-hedging.server`;
- user LaunchAgent, never a root LaunchDaemon;
- working directory: repository root;
- entrypoint: `/bin/bash` plus absolute `scripts/run-server.sh`;
- `RunAtLoad=true`;
- restart on unexpected exit with a bounded `ThrottleInterval`;
- `PYTHONUNBUFFERED=1` and `PYTHONFAULTHANDLER=1`;
- stdout/stderr under `~/Library/Logs/funding-hedging/`;
- no credentials or expanded `.env` content in the plist.

The controller must use the current macOS user domain (`gui/<uid>`) and modern
`launchctl` verbs. It must surface command errors and never claim success based
only on a generated file.

## 5. Operator Commands

The controller exposes:

```text
render      render/validate without launchctl mutation
install     render and bootstrap after explicit human action
start       kickstart an installed service
stop        bootout/stop cleanly without deleting logs
restart     controlled stop/start
status      read-only launchctl + HTTP + version summary
doctor      read-only bounded diagnostic capture
uninstall   bootout and remove only the known generated plist
```

Tests invoke render/status parsers with injected subprocess collaborators or
fixtures. Tests must not invoke real mutating launchctl commands.

## 6. Health Semantics

`GET /healthz`:

- returns `200` when the HTTP process can answer;
- fixed small JSON shape with service/version state only;
- no snapshot rows, account data, exception string, paths, or environment.

`GET /readyz`:

- returns `200` only when a published snapshot can be read without upstream I/O;
- returns `503` during cold start or unavailable publication;
- fixed small JSON shape; no business payload or raw exception string.

These endpoints are operational local contracts and do not rename or alter the
historical public-market API contract.

## 7. Diagnostics And Privacy

Default paths:

```text
~/Library/Logs/funding-hedging/server.stdout.log
~/Library/Logs/funding-hedging/server.stderr.log
~/Library/Logs/funding-hedging/diagnostics/<timestamp>/
```

The doctor bundle may include:

- sanitized `launchctl print` output limited to this label;
- process/PID and port state;
- liveness/readiness status;
- repository commit and dirty/not-dirty flag;
- configured non-secret host/port;
- bounded recent stdout/stderr tails;
- timestamps and tool exit codes.

It must not include `.env`, environment dumps, command expansions containing
credentials, API response bodies, signed URLs, cookies, or private data.
Existing HTTP access logging remains silenced.

## 8. Failure Behavior

- A process exit is visible in stderr/service status and launchd restarts it.
- Restart loops are throttled so invalid configuration does not spin rapidly.
- A living but unready process is distinguishable through `/readyz`.
- Automatic remediation of a hung-but-still-alive process is deferred; this v1
  records health and leaves a future watchdog decision explicit rather than
  silently adding a self-restart loop.
- The in-memory history cache still resets on process restart; disk persistence
  remains outside this stage.

## 9. Auto-Review Boundary

This is a `small_real` auto pilot. The runner may dispatch repository-scoped
implementation, deterministic checks, an advisory embedded cross-check, seal,
and Grok review-1. It must stop before review-2 and must not run real launchctl
mutations or private-channel live probes.

本地北京时间: 2026-07-13 12:35:49 CST
下一步模型: Claude Fable5（human dispatch）
下一步任务: 对设计做 development breakdown，特别检查 launchctl 外部副作用隔离和测试可执行性
