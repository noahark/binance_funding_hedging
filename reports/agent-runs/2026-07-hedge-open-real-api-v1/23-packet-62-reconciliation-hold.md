# Packet 62 reconciliation hold

## Result

Packet 62's local tests pass, and its source-file boundary is respected. The
bookkeeper cannot create the evidence commit or send the renewed backend
Review-1 yet, because the implementation still contains a permanent global
recovery scanner in live mode. This conflicts with the user-approved runtime
amendment and the executable packet.

## Verified evidence

- The uncommitted code/report changes are limited to packet-62 allowed backend
  files, backend tests, and the permitted stage test-output/report paths. No
  `frontend/**`, credential/config-secret, public API sample, or canonical-doc
  file changed.
- Independent bookkeeper checks on the resulting worktree:
  - explicit hedge test set plus the new task-local test file: **218 passed**;
  - `backend/tests`: **894 passed** in 45.33s;
  - `node frontend/self-check.js`: PASS;
  - Harness protocol suite: **55 passed** in 0.76s;
  - `git diff --check`: PASS.
- No credential was read and no Binance request, live activation, Start action,
  or real order was performed by the bookkeeper checks.

## H-1 — permanent recovery scanner remains (P1 / user-policy conflict)

The new local-worker code correctly removes the old synchronous global
reconciliation before dispatch. However, in live-capable mode it leaves the
existing daemon `HedgeOpenScheduler` running:

```text
service.start()
  -> HedgeOpenScheduler.start()
  -> daemon loop
  -> service.tick() on every scheduler cadence
  -> _recover_workers()
  -> scan all RUNNING tasks, then all PAUSED/STOPPED tasks for pending legs
```

Evidence: `backend/hedge_open_tasks/service.py` lines 385–386 start the
scheduler; lines 1055–1097 route live `tick()` to `_recover_workers()`; lines
1130–1152 iterate every running/paused/stopped task. `backend/hedge_open_tasks/
scheduler.py` lines 25–50 make that invocation a continuing daemon loop.

This scanner does not synchronously call an exchange query and therefore does
not recreate the already-fixed “A query blocks B dispatch” defect. It still is
a permanent all-task recovery scanner, though. Amendment 21 says recovery may
be a **one-time startup/manual invocation** which returns after handing a
specific task to its worker; it must not become a permanent scanner. Packet 62
repeats the same restriction.

The practical consequence is architectural rather than an observed failed
order: when real mode is eventually enabled, the process would keep examining
all task cards in the background even after the user asked for only the
short-lived workers belonging to the active cards. It must be resolved before
review instead of being silently treated as an acceptable interpretation.

## Required human decision

The stage has reached its configured `rework_count=3` limit. A fourth code
change needs explicit human authorization. The smallest conforming correction
would make live service startup perform one recovery handoff, let manual Start
launch only its named task, and prevent the periodic scheduler from scanning
live hedge-open tasks. Dry-run scheduling can remain unchanged. That correction
would need focused regression coverage proving the one-time recovery and the
absence of recurring live task scans.

Until that decision, packet 62 is recorded as **reconciliation hold**, not as
review-ready delivery evidence and not as permission to activate real trading.

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/23-packet-62-reconciliation-hold.md
本地北京时间: 2026-07-25 18:41:46 CST
下一步模型: human
下一步任务: decide whether to authorize one narrowly bounded final correction for H-1
