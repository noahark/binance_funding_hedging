# Software Architect Amendment — launchd Service v1

## Explicit Skill And Evidence

- Explicit skill: `software_architect`.
- Skill source: `agents/skills/software-architect.md`.
- Mode: `read_write_docs` design amendment; no delivery-code authorship.
- Author: Codex/OpenAI bookkeeper/designer.
- Raw inputs: current `00-task.md`, `10-design.md`, `11-adr.md`, Opus 4.8
  `12-development-breakdown.md`, current runtime source, and the operator-named
  Grok 4.5 plan session `019f59c9-1145-73c2-81a0-a7e928ad11eb`.
- Grok raw output remains outside stage evidence as requested in that session;
  this artifact records the bookkeeper's bounded design decisions, not a copied
  review transcript and not formal review-1 evidence.

The explicit architect skill requires naming failure behavior, observability,
trade-offs, reversibility, and dependency boundaries without adding speculative
infrastructure. This amendment therefore resolves only ambiguities that could
make the bounded implementation diverge.

## Authority

This amendment supersedes `10-design.md` and `12-development-breakdown.md` only
where the decisions below differ. All other frozen scope, file boundaries,
safety constraints, health response shapes, and blocking commands remain
unchanged.

## A1 — Restart Semantics

Use:

```text
KeepAlive = true
RunAtLoad = true
ThrottleInterval = 10
```

Rationale: the operator's reliability requirement is that loss of the service
process is repaired independently of terminal state. Restricting restart to a
non-zero exit would leave an unexpected clean exit down. An intentional stop
uses `launchctl bootout`, which removes the job from the user domain and does
not fight `KeepAlive=true`.

Trade-off: a broken configuration can retry indefinitely, but launchd throttles
attempts and persistent stderr preserves the cause. Automatic config rollback
or watchdog logic remains out of scope.

## A2 — Controller Health URL Source

`service-control.py` must never parse or source `.env`.

The health base URL comes from, in priority order:

1. explicit `--base-url` CLI value;
2. non-secret `FUNDING_HEDGING_SERVICE_URL` process environment value;
3. fixed local default `http://127.0.0.1:8787`.

The value is used only for `/healthz` and `/readyz` probes. It is not copied
into the LaunchAgent plist and it must not contain credentials or query data.

## A3 — Render And Template Authority

- `render` writes the generated plist to stdout only by default.
- It does not write `~/Library/LaunchAgents`, create log directories, or invoke
  `launchctl`, and requires no `--confirm`.
- The committed `.plist.template` is documentation/reference only.
- The authoritative plist is the `plistlib` serialization of a Python dict;
  tests validate that output so there is no executable dual source.

## A4 — Mutating Command Semantics

- `install --confirm`: fail non-zero when the job is already loaded; direct the
  operator to `restart --confirm`. Do not silently boot out a running job.
- `start --confirm`: `launchctl kickstart gui/<uid>/<label>`; fail if the job is
  not installed/loaded.
- `stop --confirm`: `launchctl bootout gui/<uid>/<label>`; fail non-zero when it
  is not loaded.
- `restart --confirm`: require the known installed plist and loaded job, then
  bootout followed by bootstrap so the plist is re-read; any failed step makes
  the command fail.
- `uninstall --confirm`: tolerate only the specific not-loaded/not-found
  bootout result, then unlink only the exact known generated plist. Other
  launchctl errors fail and do not claim successful uninstall.

All argv is built as data and tests inject a fake executor. No test passes a
mutating command to real `subprocess.run`.

## A5 — Status And Doctor Semantics

- `status` is read-only. It preserves every field even when unavailable,
  reports `unreachable` rather than a traceback, and exits non-zero unless the
  job is loaded and both health and readiness succeed.
- `doctor` may write only beneath the configured logs diagnostics directory;
  that bounded filesystem write is allowed without `--confirm` because it does
  not mutate LaunchAgent state.
- Diagnostic tails are frozen at the most recent 200 lines per stdout/stderr
  file.
- `doctor` exits zero when the sanitized bundle was successfully captured even
  if the service is down; bundle-write or redaction failures exit non-zero.

## A6 — Health-Test Construction

Health tests use an injected/stub service or a live-mode service with an empty
published state. They must not change `snapshot_service.py`, make upstream
requests, load `.env`, or rely on offline fixture construction to represent the
cold-start path.

## A7 — Lifecycle Observability

`backend/app/server.py` may add minimal UTC-timestamped lifecycle records for:

```text
server_start
server_stop
server_fatal_error
```

Records go to stderr/stdout already redirected by launchd, contain only a fixed
event name plus non-secret host/port and exception class where applicable, and
never include exception text, URLs, environment values, snapshot/account data,
or HTTP bodies. Existing `_Handler.log_message` access-log silence remains.

A fatal main-loop exception must produce a non-zero process exit after cleanup
so launchd restarts it. Do not expand this into a general logging framework.

## A8 — Correct Auto-Review Accounting

`model_calls_used` and `auto_code_changes_used` are usage counters that the
runner increments. They are not budgets that are decremented. Caps remain only
in the committed authorization artifact.

`embedded_cross_check.required_attempt=true` means an attempt and evidence are
required. Per the accepted auto contract, an unavailable required cross-check
may continue only through the documented unavailable artifact and `N/A` bind;
it is advisory and does not substitute for formal review-1.

## Design Disposition

With A1–A8 applied, the Opus 4.8 development breakdown is validated and the
stage may enter auto implementation. The named Grok session is useful advisory
design evidence but remains neither a skill-qualified design gate nor formal
review-1 because its prompt did not explicitly invoke `software_architect` and
its output was requested not to be landed.

本地北京时间: 2026-07-13 13:34:29 CST
下一步模型: Claude-GLM / GLM-5.2（auto runner）
下一步任务: 按 00/10/11/12/13 设计权威实现 T1-launchd-service，不执行真实 launchctl mutation
