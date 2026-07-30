# Task Result — task1d-state-write-visibility

Bounded repair of the **five** uniform post-POST sites from the closed,
independently-audited list (`71-audit-result-and-scope-decision.md`).
`rework_count` is 2 of 3.

The three further class-(A) sites and the one UI question are **deferred by Human
decision D-10** (see §Out of scope) and go to `PROJECT_STATE.md` at stage close —
they are not touched here. Touching them would be a scope violation.

The defect at every site is the discarding, never the underlying call. Each site
now records an operator-visible `state_write_failed` task event before the worker
continues, fabricates nothing, never resends, and lets the next worker round
recover — exactly the template F2 (`service.py:1205`/`:1242`) established and that
review-2 has already reviewed twice.

Only `backend/hedge_open_tasks/service.py` and
`backend/tests/test_hedge_task_local.py` changed. Full suite **1097 passed**
(baseline 1092 + 5 new R4 tests), no flake this run.

## R1 — one uniform mechanism, distinct from F2's

One helper, `_record_state_write_failure(task_id, attempt_id, operation, exc,
now_us)` (`service.py:1316`), sits alongside `_record_settlement_failure` and is
called from all five sites. It emits a **new** persisted kind `state_write_failed`
with payload `{attempt_id, operation, error_type, error}` — `operation` names the
store call (`resolve_leg_from_query`, `mark_attempt_rate_limited`,
`resolve_attempt`, `mark_leg_querying`). No credentials, headers, tokens, or
request body. R2 wraps the recording itself in a narrow, commented inner guard so
a failure to record cannot raise and take the worker down; it guards ONLY the
audit write.

`settlement_failed` is **not** renamed or reused. It is a persisted kind with rows
already written by F2, asserted by tests reviewed twice, and it would be a false
label on `mark_leg_querying`. Two kinds, both accurate, no data migration.
`_record_settlement_failure` and its two call sites are byte-identical to before
(§F2 untouched).

## The five sites — before / after

### S1 — `resolve_leg_from_query` (`_reconcile_own_legs`, `service.py:1188`)

R2: the old `continue` skipped the `_persist_leg_raw` call immediately after it,
dropping the exchange's own query words — the exact defect family this stage
closes. The raw capture now runs even when the leg write failed (it lives in its
own transaction, isolated from that write), and the leg is **not** added to
`finalized` (it was not recorded terminal), so the next round re-queries it.

```python
# before
            except Exception:
                continue
            # T3 (10-design §3): capture the sanitized query response ...
# after
            except Exception as exc:
                # S1 (task1d): ... Record the failure (R1); R2: do NOT skip the raw
                # capture — append_raw_response runs in its own transaction, isolated
                # from the leg-row write that just failed ...
                self._record_state_write_failure(
                    task_id, leg["attempt_id"], "resolve_leg_from_query", exc, now_us,
                )
                self._persist_leg_raw(
                    task_id, leg["attempt_id"], leg["leg"], leg["client_order_id"],
                    "order_query", getattr(verdict, "raw_response", None), now_us,
                    decisive=self._query_verdict_decisive(verdict),
                )
                continue
```

### S2 — `mark_attempt_rate_limited` (`_dispatch_live`, `service.py:1827`)

R3 needs more than a log line: if the stamp fails the attempt is unstamped and a
later reconcile settles the 429 pair as an ordinary failure, consuming the counter
the design exempts. The stamp is recorded AND remembered as pending; settlement
retries it before deciding.

```python
# before
            except Exception:
                pass
            return D.SIGNAL_RATE_LIMITED
# after
            except Exception as exc:
                # S2 (task1d): ... Record the failure (R1) and remember the stamp is
                # pending so settlement retries it before deciding and never finalizes
                # a 429 pair as ordinary (R3 — see _rate_limited_for_settlement).
                self._record_state_write_failure(
                    ctx.task_id, attempt["id"], "mark_attempt_rate_limited", exc, now_us,
                )
                self._rate_limit_stamp_pending.add(attempt["id"])
            return D.SIGNAL_RATE_LIMITED
```

The retry-before-settle helper (`service.py:1358`) is consulted at **both**
settlement sites — the drain `finalized` loop (`:1225`) and the crash-gap loop
(`:1266`) — which re-enter every worker round:

```python
    def _rate_limited_for_settlement(self, task_id, attempt_id, attempt, now_us) -> bool:
        if attempt_id in self._rate_limit_stamp_pending:
            try:
                self._store.mark_attempt_rate_limited(attempt_id)        # R3 retry
            except Exception as exc:
                self._record_state_write_failure(
                    task_id, attempt_id, "mark_attempt_rate_limited", exc, now_us)
            else:
                self._rate_limit_stamp_pending.discard(attempt_id)
            return True          # a 429 pair is NEVER finalized as ordinary failure
        return bool(attempt.get("rate_limited"))
```

This is "recording plus a next-round retry" — no new attempt column, no new status,
no operator copy (the envelope R3 allows). It is in-process (`__init__`
`_rate_limit_stamp_pending`, `service.py:425`); an attempt belongs to one task /
one worker thread, so each id is touched only by its own worker. Residual edge: a
process restart between the failed stamp and the next-round retry loses the pending
retry (the attempt would then settle as ordinary after restart) — the same crash
window the system already has, and the dispatch bounds the fix to next-round retry.

### S3 — pause-class `resolve_attempt` (`_dispatch_live`, `service.py:1849`)

```python
# before
            except Exception:
                pass
            return pause_signal
# after
            except Exception as exc:
                # S3 (task1d): orders already sent and both legs terminal; a discarded
                # resolve_attempt leaves pair_outcome NULL and the in-flight guard
                # stalls the task. Record (R1); keep catching (R2); crash-gap retries (R3).
                self._record_state_write_failure(
                    ctx.task_id, attempt["id"], "resolve_attempt", exc, now_us,
                )
            return pause_signal
```

### S4 — normal `resolve_attempt` (`_dispatch_live`, `service.py:1878`)

```python
# before
        except Exception:
            pass
        return None
# after
        except Exception as exc:
            # S4 (task1d): the main path — a real order placed and its conclusion
            # never persisted. Record (R1); keep catching (R2); crash-gap retries (R3).
            self._record_state_write_failure(
                ctx.task_id, attempt["id"], "resolve_attempt", exc, now_us,
            )
        return None
```

### S5 — `mark_leg_querying` (`_mark_legs_querying`, `service.py:1906`)

```python
# before
            except Exception:
                pass
# after
            except Exception as exc:
                # S5 (task1d): a leg needing drain was never marked, so an in-flight
                # order would never be reconciled by client ID. Record (R1); keep
                # catching (R2); the leg keeps its pre-failure state (ADR-2 holds).
                self._record_state_write_failure(
                    attempt["task_id"], attempt["id"], "mark_leg_querying", exc, now_us,
                )
```

## R4 — fault-injection tests, one per site (`test_hedge_task_local.py`)

Deterministic, temp SQLite, no real clock dependence, no network. Each forces the
named store call to raise (a `_boom` monkeypatch on `svc.store.<method>`, the same
idiom `test_4g` uses for `append_raw_response`), drives the **real service path**,
and asserts: the exception did not escape and the worker continued; a
`state_write_failed` event exists naming that `operation`; the state was **not**
fabricated. Plus the per-site extra (S1 raw still captured; S2 counter not
consumed).

- `test_s1_resolve_leg_write_failure_records_and_preserves_raw` — drain site;
  asserts the `order_query` raw row still landed despite the leg-write failure.
- `test_s2_rate_limit_stamp_failure_settles_without_consuming_counter` — asserts
  `fail_count == 0` (R3: the 429 pair is never settled as an ordinary failure) and
  that the pair recovered (`pair_outcome is not None`).
- `test_s3_pause_class_resolve_attempt_failure_is_recorded` — pause still took
  effect, `pair_outcome is None`.
- `test_s4_normal_resolve_attempt_failure_is_recorded` — `pair_outcome is None`.
- `test_s5_mark_leg_querying_failure_is_recorded` — legs stay `PREPARED` (not
  fabricated into `UNKNOWN_QUERYING`), non-terminal.

### Per-site mutation result (acceptance #3)

Reverting each site (faithfully — S1 back to `continue`, the rest back to `pass`,
with the record call and S1's `persist_leg_raw` / S2's pending-add removed) fails
**exactly its own test and no other**:

| Site reverted | test that fails | others |
|---|---|---|
| S1 | `test_s1_…` (`assert len(events) >= 1`) | s2–s5 pass |
| S2 | `test_s2_…` (`assert fail_count == 0`) | s1,s3–s5 pass |
| S3 | `test_s3_…` (`assert len(events) >= 1`) | s1,s2,s4,s5 pass |
| S4 | `test_s4_…` (`assert len(events) >= 1`) | s1–s3,s5 pass |
| S5 | `test_s5_…` (`assert len(events) >= 1`) | s1–s4 pass |

Verified with a script that reverts one site at a time from a saved fixed copy and
restores byte-identical afterwards. So each test is non-vacuous and pinned to its
site.

## Acceptance — raw output (both commands, verbatim)

Command 1 (task-local + service):

```text
$ python3 -m pytest backend/tests/test_hedge_task_local.py backend/tests/test_hedge_service.py -q
........................................................................ [100%]
64 passed in 2.30s
```

Command 2 (full suite):

```text
$ python3 -m pytest backend/tests -q
........................................................................ [ 65%]
........................................................................ [ 72%]
........................................................................ [ 78%]
........................................................................ [ 85%]
........................................................................ [ 91%]
........................................................................ [ 98%]
.................                                                            [100%]
1097 passed in 58.68s
```

Both green. 1097 = baseline 1092 + 5 new R4 tests. The known flake
`test_hedge_api.py::test_oversized_body_is_body_too_large`
(`p3-flaky-oversized-body-test`) did **not** fire this run.

## F2 untouched (acceptance #4)

`git show HEAD:service.py` vs the working tree: the only `+`/`-` lines mentioning
`settlement_failed` / `_record_settlement_failure` are two docstring references in
the new `_record_state_write_failure`. The kind `"settlement_failed"`, the
`_record_settlement_failure` body, and its two call lines
(`self._record_settlement_failure(task_id, attempt_id, exc, now_us)` and
`self._record_settlement_failure(task_id, attempt["id"], exc, now_us)`) are
byte-identical — only their line numbers shifted (1210→1238, 1247→1277) because
new code was inserted above them.

## No new product semantics (acceptance #5)

`_ENTRY_EVENT_KINDS` (`service.py:61-67`) is unchanged — neither
`state_write_failed` nor `settlement_failed` was added, so the new events reach the
logs list (like F2) and not the unified entries timeline (a UI question D-10
defers). No new `pause_reason`, task status, operator-facing Chinese copy, or UI
field was introduced. The only additions are one machine-readable event kind
(`state_write_failed`) and one in-process retry set.

## Which sites needed more than the template (acceptance #7)

Three of five followed the template verbatim (S3, S4, S5: record + keep catching).
Two needed more:

- **S1** needed the R2 raw-preservation guarantee — the `continue` skipped
  `_persist_leg_raw`, so the fix also runs the raw capture on the failure path.
- **S2** needed the R3 ordering guarantee — recording alone does not stop a later
  reconcile from finalizing the unstamped pair as an ordinary failure, so the fix
  adds the in-process pending-stamp retry consulted at both settlement sites. This
  stayed inside "recording plus a next-round retry"; it did not need a new column,
  status, or operator copy, so it is not a blocker.

## File boundary (acceptance #6)

```text
$ git status --short
 M backend/hedge_open_tasks/service.py
 M backend/tests/test_hedge_task_local.py
?? reports/agent-runs/2026-07-unknown-not-zero-v1/73-task1d-glm-result.md
```

Forbidden files untouched: `store.py`, `domain.py`, `executor.py`, `scheduler.py`,
`backend/services/**`, `test_hedge_purity.py`, `test_hedge_store.py`,
`frontend/**`, `schemas/**`, `scripts/**`, `docs/**`, `AGENTS.md`, `agents/**`,
`data/**`, `PROJECT_STATE.md`, `ACTIVE.json`. (Shown before the status flip; after
the flip `status.json` joins as the single allowed carve-out.)

## Safety kernel

- No network, no credentials, no service control, no read or write of `data/**`.
- F1 (balance gate) not touched — D-8 keeps it out of scope.
- Committed on `stage/2026-07-unknown-not-zero-v1`; `main` not touched; no merge.

```text
[TASK_RESULT v2]
任务 ID: task1d-state-write-visibility
执行结果: completed（完成）
结果摘要: 修复审计闭环中的 5 个 post-POST 丢弃点（S1-S5）：各点经新增 _record_state_write_failure 记录 state_write_failed 事件（含 operation/异常，无凭证），worker 存活、不伪造、不重发；S1 兼保 raw，S2 加在结算前重试 rate-limit stamp（R3，进程内 set，无新列/状态）。F2 的 settlement_failed 及两调用点字节不变。
产物: [backend/hedge_open_tasks/service.py, backend/tests/test_hedge_task_local.py, reports/agent-runs/2026-07-unknown-not-zero-v1/73-task1d-glm-result.md]
检查结果: [聚焦 task_local+service 64 passed；全套 1097 passed（基线 1092+5）；R4 五测试逐点注入 _boom 驱动真实路径，断言事件+operation+不伪造（S1 raw 仍落库、S2 fail_count==0）；逐点 mutation 已验：回退任一点恰好只挂其自身测试；F2 settlement_failed/两调用点字节不变（仅行号位移）；_ENTRY_EVENT_KINDS 未改、无新 pause_reason/状态/文案/UI；git status 仅 service.py+test_hedge_task_local.py+结果文件，未碰 forbidden；S1/S2 超模板但均在 recording+next-round retry 内、非阻塞]
阻塞项: none（五点均已可见且 worker 存活，R4 确定性覆盖、逐点 mutation 通过；D-10 延后的 :1141/:1632/live_hedge_executor 690-702 及 timeline UI 问题按规留待 PROJECT_STATE.md，不在本任务范围）
本地北京时间: 2026-07-30 21:19:19 CST
下一步模型: opus5（记账人，Human 转交结果）
下一步任务: 证据 reports/agent-runs/2026-07-unknown-not-zero-v1/73-task1d-glm-result.md；状态 current_task.state dispatched→reported（delivery_sha 7bd2bcef7882a642f8bee64192770da924b7e5c6）；本次触及 task1 review 范围内禁改文件 service.py，按 dispatch 末段路由须 review-1（Grok 4.5 交叉）再 review-2（Codex，D-6 披露）；rework_count 2/3，若再审 REWORK 则 AGENTS.md:182 转交 Human。
[/TASK_RESULT]
```
