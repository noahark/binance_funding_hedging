# Task Result — task1c-f2-settlement-visibility

Bounded repair of the **one** review-2 finding in scope (F2) from
`41-review-2-codex-result.md` §F2. F1 is out of scope by Human decision D-8
(`hedge_preflight_provider.py` / `domain.py` balance gate untouched); F3 was
already corrected by the Bookkeeper. `rework_count` is 1 of 3.

The defect is the discarding, not the timestamp: `build_leg_exposure`'s
`ts_us <= 0` raise stays (the T5 backstop, untouched in `domain.py`). The two
bare `except Exception: pass` sites that swallowed it (and any other settlement
failure) now record an operator-visible event before the worker continues.

Only `backend/hedge_open_tasks/service.py` and
`backend/tests/test_hedge_task_local.py` changed. Full suite **1092 passed**
(baseline 1090 + 2 new tests), no flake this run.

## R1/R2 — stop discarding, keep the worker alive, no new product semantics

One helper, `_record_settlement_failure`, is called from both sites. It records
a `settlement_failed` task event on the **existing** `record_task_event` channel
(the one the logs page already reads) — no new table, storage mechanism, or API
field. The payload carries `attempt_id`, `error_type` (`type(exc).__name__`), and
`error` (`str(exc)`): enough to diagnose, with no credentials, headers, tokens,
or request body. R2 wraps the recording itself in a narrow, commented inner guard
so a failure to record cannot raise and take the worker down; it guards ONLY the
audit write, not settlement business logic. R3 adds no `pause_reason`, task
status, operator-facing copy, or UI change — the crash-gap loop already retries
every worker round, so a transient cause self-heals and a permanent one produces
a repeated, visible event.

### Before / after — both named sites

Drain site (`_reconcile_own_legs`, `service.py:1205`):

```python
# before
            except Exception:
                pass
# after
            except Exception as exc:
                # F2 (review-2): stop discarding. A settlement exception left
                # pair_outcome NULL, silently stalling the task on prepare's
                # in-flight guard. Record an operator-visible event before the
                # worker continues (R1); keep catching so the worker survives (R2).
                self._record_settlement_failure(task_id, attempt_id, exc, now_us)
```

Crash-gap site (`_recover_crash_gaps`, `service.py:1238`):

```python
# before
            except Exception:
                pass
# after
            except Exception as exc:
                # F2 (review-2): the same discarding defect on the crash-gap
                # recovery loop — the mechanism meant to unstick this exact
                # state. Record an operator-visible event (R1); the worker
                # survives (R2) and the loop retries next round (R3).
                self._record_settlement_failure(task_id, attempt["id"], exc, now_us)
```

Neither bare `except Exception: pass` remains at the two named sites (pass
condition 3). `grep -n "settlement_failed" service.py` returns exactly one hit —
the event kind in the helper — confirming no new pause reason, task status, or UI
field was introduced (pass condition 4).

## R4 — test the runtime consequence, not the helper

Two deterministic tests in `test_hedge_task_local.py`, both driving the **real
service settlement path** with an injected zero clock (`_Clock(0)` →
`wall_us() == 0`), no network, temp SQLite only.

`test_drain_settlement_failure_is_recorded_not_swallowed` — the drain site. An
UNKNOWN pair is dispatched (`_unknown_pair()`); the next worker round drains both
legs via `query_leg` (spot → FILLED accepted, perp → absent REJECTED), so
`finalize_attempt` derives a single-leg pair and `build_leg_exposure(ts_us=0)`
raises the T5 backstop. Asserts: the exception did not escape (the second
`_pump_worker` returns normally); a `settlement_failed` event was recorded and
names the failure (`"ts_us" in payload["error"]`); the payload carries only
`attempt_id` / `error_type` / `error` (no credential leakage); and the attempt is
still unsettled (`pair_outcome is None` — no fabricated settlement). The drain
raise leaves a crash-gap that the crash-gap loop then hits in the same round, so
**both** sites record — `len(events) >= 2`; fixing only one site would leave the
count at 1.

`test_crash_gap_settlement_failure_is_recorded` — the crash-gap site in
isolation. The crash-gap state (both legs terminal, `pair_outcome` NULL, one
accepted / one rejected) is constructed directly with `resolve_leg_from_query`
(the state a crash between leg-terminalization and pair settlement leaves), then
one worker round drives `_recover_crash_gaps` → `finalize_attempt(ts_us=0)` →
raise. Asserts the same: event recorded naming the failure, worker survives, the
attempt stays unsettled. This isolates the crash-gap `except` from the drain
site, so each site's fix is independently detectable.

## Acceptance — raw output (both commands, pasted verbatim)

Command 1 (service + task-local):

```text
$ python3 -m pytest backend/tests/test_hedge_service.py backend/tests/test_hedge_task_local.py -q
...........................................................           [100%]
59 passed in 1.95s
```

Command 2 (full suite):

```text
$ python3 -m pytest backend/tests -q
........................................................................ [  6%]
........................................................................ [ 13%]
........................................................................ [ 19%]
........................................................................ [ 26%]
........................................................................ [ 32%]
........................................................................ [ 39%]
........................................................................ [ 46%]
........................................................................ [ 52%]
........................................................................ [ 59%]
........................................................................ [ 65%]
........................................................................ [ 72%]
........................................................................ [ 79%]
........................................................................ [ 85%]
........................................................................ [ 92%]
........................................................................ [ 98%]
............                                                             [100%]
1092 passed in 59.50s
```

Both green. 1092 = baseline 1090 + 2 new R4 tests. The known flake
`test_hedge_api.py::test_oversized_body_is_body_too_large`
(`p3-flaky-oversized-body-test`) did **not** fire this run.

## File boundary (pass condition 5)

```text
$ git status --short
 M backend/hedge_open_tasks/service.py
 M backend/tests/test_hedge_task_local.py
?? reports/agent-runs/2026-07-unknown-not-zero-v1/45-task1c-glm-result.md
```

(Shown before the status flip; after the flip `status.json` joins as the single
allowed carve-out.) `test_hedge_task_local.py` is the honest home for both R4
cases — the crash-gap loop's existing coverage lives there, and so does the drain
loop's (test_4d / test_r3 family), so the new tests reuse `_RoutingExecutor`,
`_Clock`, `_pump_worker`, `_filled_leg`, `_absent_query`, and `_unknown_pair`
verbatim. Forbidden files untouched: `store.py`, `domain.py`, `executor.py`,
`backend/services/**` (incl. `hedge_preflight_provider.py`),
`test_hedge_purity.py`, `test_hedge_store.py`, `frontend/**`, `schemas/**`,
`scripts/**`, `docs/**`, `AGENTS.md`, `agents/**`, `data/**`, `PROJECT_STATE.md`,
`ACTIVE.json`. `build_leg_exposure`'s `ts_us <= 0` raise is unchanged; the old
1970-timestamp behaviour is not restored.

## Safety kernel

- No network, no credentials, no service control, no read or write of `data/**`.
- F1 (balance gate) was not touched — D-8 keeps it out of scope. If F2's fix had
  required touching the balance path it would have been a blocker; it did not.
- Committed on `stage/2026-07-unknown-not-zero-v1`; `main` not touched; no merge.

```text
[TASK_RESULT v2]
任务 ID: task1c-f2-settlement-visibility
执行结果: completed（完成）
结果摘要: 有界修复 review-2 的 F2：drain 与 crash-gap 两处裸 except Exception: pass 改为经新增 _record_settlement_failure 在既有 record_task_event 通道记录 settlement_failed 事件（含 attempt_id/异常类型/消息，无凭证），记录本身加窄内部 guard（R2）。未碰 ts_us<=0 raise、未加 pause_reason/状态/UI（R3）。
产物: [backend/hedge_open_tasks/service.py, backend/tests/test_hedge_task_local.py, reports/agent-runs/2026-07-unknown-not-zero-v1/45-task1c-glm-result.md]
检查结果: [聚焦 service+task_local 59 passed；全套 1092 passed（基线 1090+2）；R4 两测试注入零时钟驱动真实结算路径，drain site 断言 len>=2（drain+crash-gap 同 round 触发）、命名 ts_us、worker 继续、pair_outcome 仍 NULL、payload 仅 attempt_id/error_type/error；crash-gap site 隔离构造断言 len>=1；两 site before/after 已贴；grep settlement_failed 仅 1 处（event kind）证无新 pause/status/UI；git status 仅 service.py+test_hedge_task_local.py+结果文件，未碰 forbidden；ts_us<=0 raise 与 1970 行为均未改]
阻塞项: none（F2 两 site 均改为可见且 worker 存活，R4 已确定性覆盖；F1 按 D-8 不在范围、F3 已由记账人完成，均无遗留）
本地北京时间: 2026-07-30 19:20:33 CST
下一步模型: opus5（记账人，Human 转交结果）
下一步任务: 证据 reports/agent-runs/2026-07-unknown-not-zero-v1/45-task1c-glm-result.md；状态 current_task.state dispatched→reported（delivery_sha 7cadb88da501）；因本次修复触及 task1 review 范围内的禁改文件 service.py，按 AGENTS.md:181 须重回 review-1（Grok 4.5 交叉评审）再回 review-2；请 opus5 复核 base_sha..delivery_sha 范围与文件边界。
[/TASK_RESULT]
```
