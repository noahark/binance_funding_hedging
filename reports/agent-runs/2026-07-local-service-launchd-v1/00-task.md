# Task — Terminal-Independent Local Service

## Objective

Provide a macOS `launchd`-managed local service that survives terminal closure,
serves the existing frontend and backend from the existing single Python
process, restarts after process exit, and leaves durable, secret-safe evidence
for diagnosis.

## Scope

One serial task, `T1-launchd-service`:

1. Add a repository-owned LaunchAgent template and a safe renderer/controller.
2. Reuse `scripts/run-server.sh` as the application entrypoint and preserve its
   `.env`/private-channel gates.
3. Add `install`, `start`, `stop`, `restart`, `status`, `doctor`, and `uninstall`
   operator commands with a non-mutating/dry-run path suitable for tests.
4. Persist stdout/stderr and lifecycle diagnostics under
   `~/Library/Logs/funding-hedging/`, never in Git.
5. Add secret-free `/healthz` liveness and `/readyz` readiness routes served by
   the same backend process.
6. Add deterministic tests that do not load or mutate the user's real
   LaunchAgent domain.
7. Document manual acceptance steps without executing them automatically.

## Architecture Constraint

There is no second frontend daemon. `backend.app.server` already serves
`frontend/` static files and the API on one origin. The LaunchAgent manages
that single process, whose in-process snapshot worker remains subordinate to
the main server lifecycle.

## Safety Boundaries

- Never commit, print, copy, or inspect real `.env` values.
- Never record API keys, secrets, signed query strings, private response bodies,
  cookies, or full environment dumps.
- Implementation and tests must not execute a real `launchctl bootstrap`,
  `bootout`, `enable`, `disable`, or `kickstart` against the user's domain.
- No public bind, reverse proxy, TLS, cloud deployment, Docker deployment,
  trading action, or account mutation.
- No handwritten PID-file authority; `launchd` owns process identity.
- Existing public snapshot response bodies and product semantics are unchanged.

## Acceptance Criteria

1. A generated plist parses with Python `plistlib`, contains the exact stage
   label, repository working directory, `run-server.sh` entrypoint,
   `RunAtLoad`, restart policy, throttling, and persistent stdout/stderr paths.
2. Rendering correctly escapes repository paths containing spaces and never
   embeds secret values.
3. `status` reports loaded/running state, PID when available, configured URL,
   liveness/readiness results, commit id, and log locations without secrets.
4. `doctor` writes a timestamped, bounded, secret-safe diagnostic bundle and
   includes recent stderr/stdout tails, not entire unbounded logs.
5. `/healthz` returns process liveness only; `/readyz` returns readiness only
   and neither returns market/account payloads or raw exception text.
6. Startup, shutdown, and uncaught/lifecycle failures reach durable stderr or
   operational output with timestamps; existing HTTP access-body silence is
   preserved.
7. Service-management tests use fixtures/mocks/temp directories and prove no
   real LaunchAgent mutation.
8. Existing backend suite and `frontend/self-check.js` remain green.
9. Auto runner reaches `completed_review_1` only after a schema-valid Grok
   ACCEPT bound to the sealed fingerprint.
10. Actual LaunchAgent installation and live private-enabled smoke remain an
    explicit human acceptance step after review-1.

## Frozen Blocking Checks

```text
python3 -m py_compile backend/app/server.py scripts/service-control.py
python3 -m pytest scripts/tests/test_service_control.py backend/tests/test_service_health.py -q -p no:cacheprovider
python3 -m pytest backend/tests -q -p no:cacheprovider
node frontend/self-check.js
bash -n scripts/run-server.sh
git diff --check
```

本地北京时间: 2026-07-13 12:35:49 CST
下一步模型: Claude Fable5（human dispatch）
下一步任务: 编写有界 development breakdown，冻结实现文件与测试矩阵
