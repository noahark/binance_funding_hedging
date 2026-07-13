# Development Breakdown — Terminal-Independent Local Service (`T1-launchd-service`)

Design-only freeze for stage `2026-07-local-service-launchd-v1`. No code is
implemented here; no `launchctl` is invoked; no `.env` is read; the server is
not started. This document freezes what the implementer (`claude_glm` /
`zhipu_glm`) may build and how the deterministic tests prove the real user
LaunchAgent domain is never mutated.

## 1. Serial Owner And Frozen File Set

Single serial owner: `claude_glm` (`zhipu_glm`). No parallel task. Reviewer-1:
`grok` (`xai_grok`). This is a `MEDIUM` / `small_real` auto pilot.

### 1.1 Allowed to create

```text
deploy/launchd/com.aoke.funding-hedging.server.plist.template
scripts/service-control.py
scripts/tests/test_service_control.py
backend/tests/test_service_health.py
```

### 1.2 Allowed to edit (bounded)

```text
backend/app/server.py   # ADD /healthz + /readyz routing only; no change to
                        # existing /api/* handlers, static serving, access-log
                        # silence, or response bodies.
```

### 1.3 Forbidden to modify

```text
scripts/run-server.sh              # reused as-is; entrypoint + .env/private
                                   # gate are unchanged. No functional edit.
backend/services/snapshot_service.py   # readiness reuses the EXISTING public
                                       # get_snapshot(); no new service method.
backend/config.py, backend/domain/**, backend/adapters/**, backend/services/**
frontend/**                        # no product change; self-check stays green.
.env, any real secret material
```

Any diff line outside §1.1–§1.2 is out of scope and must be rejected in review.
The stage evidence directory `reports/agent-runs/2026-07-local-service-launchd-v1/`
is excluded from blocking-check diffs (`evidence_exclude_pathspecs`).

## 2. Plist Rendering And `launchctl` Command Semantics

### 2.1 Rendering

`scripts/service-control.py` owns rendering. Build the plist with Python
`plistlib.dump`/`dumps` (an XML-safe writer), never string interpolation, so a
repository path containing spaces or XML metacharacters stays valid. The
`.plist.template` file is a documentation/reference artifact; the authoritative
rendered document is produced from a Python dict so escaping is guaranteed.

Frozen plist content (rendered to the target only by an explicit human
`install`):

```text
Label                 = com.aoke.funding-hedging.server
ProgramArguments      = ["/bin/bash", "<ABS repo>/scripts/run-server.sh"]
WorkingDirectory      = <ABS repo root>
RunAtLoad             = true
KeepAlive             = { "SuccessfulExit": false }   # restart on abnormal exit
ThrottleInterval      = 10   # bounded restart throttle (seconds)
ProcessType           = Background
EnvironmentVariables  = { "PYTHONUNBUFFERED": "1", "PYTHONFAULTHANDLER": "1" }
StandardOutPath       = <~>/Library/Logs/funding-hedging/server.stdout.log
StandardErrorPath     = <~>/Library/Logs/funding-hedging/server.stderr.log
```

No `BINANCE_*`, no expanded `.env`, no secret key/value is ever placed in
`EnvironmentVariables` or anywhere in the plist. `.env` continues to be loaded
by `run-server.sh` at process start, outside the plist.

### 2.2 `launchctl` verbs (user GUI domain)

Domain target `gui/<uid>` (runtime `id -u`; example uid=501). Service target
`gui/<uid>/com.aoke.funding-hedging.server`. Frozen argv construction:

```text
install    launchctl bootstrap gui/<uid> <installed-plist-path>
start      launchctl kickstart    gui/<uid>/<label>
stop       launchctl bootout      gui/<uid>/<label>
restart    stop (bootout) then install (bootstrap)  # re-reads the plist
status     launchctl print        gui/<uid>/<label>        # read-only
doctor     launchctl print        gui/<uid>/<label>        # read-only
uninstall  launchctl bootout      gui/<uid>/<label>, then unlink ONLY the known
                                   generated plist path; logs are NOT deleted.
```

The controller must (a) build argv as pure data separate from execution,
(b) execute mutating verbs only after an explicit human `--confirm` flag,
(c) surface non-zero `launchctl` exit codes as command failure, and (d) never
report success from having merely written a file. `render`, `status`, `doctor`
are non-mutating and need no `--confirm`.

## 3. External-Side-Effect Isolation (No Real LaunchAgent Mutation)

The proof that tests never touch the user's real domain is structural, not
incidental:

1. **Injected executor.** The controller takes a subprocess runner collaborator
   (constructor arg / factory), defaulting to real `subprocess.run`. Every test
   injects a fake runner that records argv and returns a canned
   `CompletedProcess`; the real `launchctl` binary is never spawned.
2. **Parameterized target dirs.** LaunchAgents dir and Logs dir are resolved
   from injectable settings, defaulting to `~/Library/LaunchAgents` and
   `~/Library/Logs/funding-hedging` only at runtime. Tests point both at
   `tmp_path`.
3. **In-tree write assertion.** A test asserts the resolved install target
   under test is inside `tmp_path`, and that the real
   `~/Library/LaunchAgents/com.aoke.funding-hedging.server.plist` is never
   created or modified by the suite.
4. **Confirm-gate guard.** A test asserts every mutating subcommand refuses to
   execute without `--confirm`, and that the suite itself never passes
   `--confirm` to a real runner.
5. **Argv-only mutation tests.** Mutating verbs are tested by asserting the
   built argv strings against the fake runner — never by executing a real
   `bootstrap`/`bootout`/`kickstart`/`enable`/`disable`.

## 4. `/healthz` And `/readyz` Fixed Contract

Added to `backend/app/server.py` `do_GET`, dispatched before static serving.
Both are secret-free, business-payload-free, and never echo raw exception text.

### 4.1 `GET /healthz` (liveness)

- Always `200` when the HTTP process can answer (the handler running proves it).
- Fixed body: `{"status": "ok", "service": "com.aoke.funding-hedging.server"}`.
- No snapshot rows, account data, exception string, filesystem path, or env.

### 4.2 `GET /readyz` (readiness)

- Attempts a pure, zero-upstream published-state read via the existing
  `SnapshotService.get_snapshot()` inside `try/except`.
- `200` + `{"status": "ready"}` when a published snapshot is readable.
- `503` + `{"status": "not_ready"}` on `SnapshotNotReady` or any other
  exception (cold start / no publication). The exception object is caught and
  discarded — its text is never placed in the response.
- No market/account payload, no `data_time`/row content, no raw exception.

Neither route renames or alters the historical public-market API contract;
`Content-Type: application/json; charset=utf-8`, small fixed shapes.

## 5. Durable Logging And Diagnostic Redaction

### 5.1 Durable paths

```text
~/Library/Logs/funding-hedging/server.stdout.log
~/Library/Logs/funding-hedging/server.stderr.log
~/Library/Logs/funding-hedging/diagnostics/<UTC-timestamp>/
```

Logs live under `~/Library/Logs`, never in Git. `PYTHONUNBUFFERED=1` and
`PYTHONFAULTHANDLER=1` keep startup, shutdown, and uncaught/faulthandler traces
flowing to `server.stderr.log` with the existing HTTP access-body silence
(`_Handler.log_message` stays a no-op) preserved.

### 5.2 `status` output field contract (read-only)

`status` prints a single non-secret summary (satisfies acceptance criterion 3):

```text
loaded/running state (parsed from launchctl print)
pid (when launchctl reports one; else "n/a")
configured url  (host:port from config; no secrets)
liveness   (GET /healthz result)
readiness  (GET /readyz result)
commit id  (git rev-parse --short HEAD)  + dirty flag (git status --porcelain)
log locations (the two log paths above)
```

### 5.3 `doctor` bundle (bounded, secret-safe)

Writes a timestamped bundle under `diagnostics/<UTC-timestamp>/` containing:
sanitized `launchctl print` limited to this label; pid/port state;
liveness/readiness; commit + dirty flag; configured non-secret host/port;
**bounded** recent stdout/stderr tails (last N lines, not whole files); tool
exit codes and timestamps.

The bundle and `status` MUST NOT include: `.env` contents, environment dumps,
command expansions containing credentials, API/private response bodies, signed
URLs, cookies, or any private data.

## 6. Deterministic Test Commands (Frozen, match `00-task.md`)

Blocking checks run exactly as frozen (`status.json` `blocking_checks.commands`
== `00-task.md` Frozen Blocking Checks):

```text
python3 -m py_compile backend/app/server.py scripts/service-control.py
python3 -m pytest scripts/tests/test_service_control.py backend/tests/test_service_health.py -q -p no:cacheprovider
python3 -m pytest backend/tests -q -p no:cacheprovider
node frontend/self-check.js
bash -n scripts/run-server.sh
git diff --check
```

Required coverage in the two new test files:

- `scripts/tests/test_service_control.py`: plist renders and re-parses with
  `plistlib` carrying the exact label/cwd/entrypoint/RunAtLoad/KeepAlive/
  ThrottleInterval/log paths; rendering a repo path containing a space stays
  valid and secret-free; each `launchctl` verb builds the exact frozen argv via
  the fake runner; mutating verbs refuse without `--confirm`; the §3 in-tree /
  no-real-domain-mutation assertions; `status`/`doctor` parsing produces the
  §5.2/§5.3 fields with no secrets.
- `backend/tests/test_service_health.py`: `/healthz` → `200` fixed body;
  `/readyz` → `200 ready` when a published state exists and `503 not_ready`
  before first publication; both bodies carry no business payload and no raw
  exception text.

## 7. Auto-Run Implementation / Review Focus And Repair Routing

- **Dispatch mode:** `human_dispatch`. Authorization:
  `auto-run-authorization-v1.json`. Budgets (`model_calls_used`,
  `auto_code_changes_used`) start at 0 and are decremented by the runner; the
  implementer/fix work is scoped to the §1.1–§1.2 pathspecs only.
- **Implementation focus:** the six frozen blocking checks green; the §3
  isolation proof; the §4 fixed health contract; §5 redaction.
- **Embedded cross-check:** advisory, `required_attempt: true`; bound to the
  sealed diff fingerprint; non-blocking.
- **Review-1 (`grok`, plan mode):** the runner reaches `completed_review_1`
  only after a schema-valid Grok **ACCEPT** bound to the sealed fingerprint
  (acceptance criterion 9). Any P0/P1 routes back to `claude_glm` for repair;
  fix authorship stays with the implementer adapter, `rework_count` bounded by
  `max_rework = 3`. Re-review must rebind to the new fingerprint.
- **Hard stop:** the runner MUST stop before review-2. It must not run real
  `launchctl` mutations or any private-channel live probe.

## 8. Non-Goals And Human-Only Live Acceptance

Explicit non-goals (deferred or out of scope): live watchdog / self-restart of a
hung-but-alive process; disk persistence of the in-memory history cache (still
resets on restart); root `LaunchDaemon`; handwritten PID files; public bind,
reverse proxy, TLS, cloud/Docker deployment; any trading or account mutation;
any change to public snapshot response bodies or product semantics.

Human-only live acceptance steps (performed by the operator AFTER review-1,
never by the auto runner or tests — acceptance criterion 10):

```text
python3 scripts/service-control.py install --confirm
python3 scripts/service-control.py status
# close the launching terminal, confirm the service survives, then:
python3 scripts/service-control.py doctor
# optional private-enabled live smoke, then teardown:
python3 scripts/service-control.py uninstall --confirm
```

`real_launchctl_mutation_authorized` stays `false` in `status.json` until the
operator performs the above; no automated step flips it.

本地北京时间: 2026-07-13 12:49:30 CST
下一步模型: Codex bookkeeper
下一步任务: 校验 12-development-breakdown.md 并更新 status.json（含 breakdown_author provenance）后放行实现
