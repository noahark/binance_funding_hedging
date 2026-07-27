# R4 Diff Reconciliation — Rework Round 1 (Review-2 P2 fix)

Performed by the bookkeeper after the fix session stopped. Covers only the
rework diff; the round-1 reconciliation is `16-r4-diff-reconciliation.md`.

## 1. File-boundary check — PASS

| File | Allowed by packet 60 |
| --- | --- |
| `backend/hedge_open_tasks/executor.py` | explicitly allowed |
| `backend/hedge_open_tasks/domain.py` | allowed "只复用/暴露现有纯过滤选择语义" |
| `backend/tests/test_hedge_wire_constraints.py` | explicitly allowed |
| `reports/agent-runs/…/40-fix-review-2-s5.md` | the fix report |

Forbidden files — **zero changes, verified**: `frontend/**`,
`backend/services/live_hedge_executor.py`,
`backend/services/hedge_open_live_client.py`, `backend/app/server.py`, DB
schema/migrations, `status.json`, `70-handoff.md`. The fix author did not
commit and did not touch bookkeeping files.

**ADR-H4 holds**: `wire_constraints` is still not imported or mounted anywhere
on the live send path.

## 2. Does the fix actually close the finding — verified against the code

Review-2's P2 was that `RecordTransportExecutor.execute` called
`validate_order_params` without `step_size`/`min_qty`/`max_qty`.

The fix author reports a root cause **one layer deeper than the finding**, and
the bookkeeper confirms it: `compute_preflight`'s `snapshot_record` only carried
`spot_step`/`perp_step` — the min/max bounds were never in the snapshot at all,
so the record transport had nothing to pass even if it had wanted to. Wiring
alone would not have been enough.

Both halves verified:

- `domain.py:755-771` — `compute_preflight` now records `spot_min_qty`,
  `spot_max_qty`, `perp_min_qty`, `perp_max_qty` using the **pre-existing**
  `_qty_bounds` helper. Confirmed pre-existing: `_qty_bounds` was introduced in
  commit `1749d94`, well before this rework, and carries the per-constraint
  `MARKET_LOT_SIZE → LOT_SIZE` fallback documented at `domain.py:567-575`. The
  packet required reusing that rule rather than writing a second filter-selection
  rule; the fix complies.
- `executor.py:303-310` + new `_leg_qty_filters` (`executor.py:367-389`) — each
  leg reads **its own** step/min/max out of the sanitized snapshot and passes
  them as kwargs. A field absent from the snapshot is omitted, so the validator
  treats that bound as disabled — the same convention `compute_preflight` uses.

## 3. Are the new tests behavioural — yes

Review-2 explicitly demanded end-to-end coverage, "不得只测试
validate_order_params 的直接调用". The four new tests drive
`RecordTransportExecutor()` itself and assert:

- `category == ATTEMPT_FAILED`, `error_code == "offline_constraint"`,
  `error_reason_zh == "离线参数约束校验失败"`;
- **both** legs `LEG_REJECTED` with `filled_qty == "0"` — proving no simulated
  fill happens on a constraint rejection;
- `record_payload["constraint_violations"]` contains the expected fragments,
  parametrised over two cases: `0.0005` (below both step and min → two
  violations) and `200` (above max, step/min still satisfied);
- a grid-aligned quantity still returns `ATTEMPT_SUCCESS` with no violations;
- spot and perp carrying **different** filters each use their own.

## 4. Merged-state rerun — PASS (authoritative)

Raw output: `60-test-output.txt`.

| Command | Result |
| --- | --- |
| `.venv/bin/python -m pytest backend/tests -q` | **983 passed** (baseline 979 + 4 new) |
| `node frontend/self-check.js` | 全部自检通过, **122 PASS** |
| `.venv/bin/python -m pytest scripts/tests/…dispatch_protocol.py -q` | 72 passed |
| `git diff --check` | clean |

## 5. Contract impact — additive only

`snapshot_record` gains four fields. It is persisted as JSON TEXT, so there is
no schema change and no migration. The frozen vocabularies (task status,
entries projection, settings doc, clientOrderId derivation) are untouched, and
S1–S4 are unchanged.

The fix author's stated reason the pre-existing tests stayed green is worth
recording because it also explains why the defect was reachable at all:
`q_common = floor_to_grid(single_amount, lcm)` is mathematically guaranteed to
satisfy both legs' steps, and `_check_common_quantity` already enforced min/max
— so the production path never produced a violating quantity. The gap was that
the **offline transport could not catch one if it ever appeared**, which is
exactly what S5 exists to guarantee. That matches Review-2's framing: the
defence was specified, built, and left unwired.

## 6. Verdict

**R4 reconciliation PASS.** Boundaries held, ADR-H4 intact, the finding is
genuinely closed at its real root, the new coverage is behavioural, and the
merged state is green. Proceeding to the evidence commit and a **new**
fingerprint; the previous one is void because the diff moved.

---

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-hardening-v1/19-r4-diff-reconciliation-rework1.md
本地北京时间: 2026-07-28 00:20:00 CST
下一步模型: bookkeeper
下一步任务: 证据 commit + 新指纹，然后重开后端 review-1 与 review-2
