# Dispatch — review1r2-task1c-grok45

```text
Identity:
  task_id:         review1r2-task1c-grok45
  target_role:     Reviewer
  target_model:    grok-4.5
  provider:        xai
  status_revision: 11
  required_skill:  agents/skills/code-reviewer.md
```

Second review-1 pass, required by `AGENTS.md:181`: the review-2 repair touched
`service.py`, which was a forbidden file in the range you accepted earlier, so the
cross-provider gate runs again before the final review.

Read-only: no edit, no commit, no branch, no network, no credentials, no service
control, no read or write of `data/**`. Read-only `git`/`grep`/`rg` and running the
test suite are expected.

You accepted the earlier range (`ac8d493..851dd08`) on 2026-07-30 16:34. Provider
isolation still holds: implementer `claude_glm` = `zhipu_glm`, you are `xai`.

## Goal

Judge **only** the incremental repair and whether it broke anything. Not a re-review
of the whole stage.

```text
new delivery range   ac8d493..7cadb88
the repair alone     851dd08..7cadb88
```

Review-2 (Codex) found that both settlement call sites in `service.py` wrapped
`finalize_attempt` / `settle_attempt_no_counters` in `except Exception: pass`, so
**any** settlement failure left `pair_outcome = NULL`, tripped
`prepare_attempt`'s in-flight guard, silently stalled the task, and was invisible —
including in the crash-gap recovery loop meant to unstick exactly that state. The
repair records a `settlement_failed` event instead of discarding.

Judge:

**K1 — Is the repair correct at both sites?** `service.py:1205-1210` (drain) and
`:1242-1247` (crash-gap), plus `_record_settlement_failure` at `:1256-1290`. Does
control flow still behave when the exception is *not* the timestamp one — a DB
error, a rollup bug? Is anything now reachable that was not before?

**K2 — Can the worker still be killed?** The inner guard around the audit write
exists so a recording failure cannot raise. Check it cannot itself raise (e.g. a
non-serialisable payload, a `str(exc)` that raises), and that no other new path can
escape into the worker thread.

**K3 — Is the event honest and safe?** Payload is `{attempt_id, error_type, error}`.
Can `str(exc)` carry a credential, a header, a token, or a request body from any
exception this path can actually raise? Trace at least one real exception source
rather than reasoning from the shape.

**K4 — Did the repair weaken what you already accepted?** Specifically: the
`ts_us <= 0` raise in `domain.build_leg_exposure` must still be there and must
still fire; the money-zero guard and its meta-tests must be untouched; the paired
per-site regressions must still pass. Confirm by reading, not by trusting this
packet.

**K5 — Are the two new tests load-bearing?** The Bookkeeper mutation-tested them:
reverting the drain site fails the drain test only; reverting the crash-gap site
fails both (the drain test's `>= 2` needs both). Re-derive that independently if you
doubt it. Judge whether `>=` rather than `==` leaves a hole, and whether asserting
`pair_outcome is None` is right (the Bookkeeper says yes — fabricating a settlement
to tidy the test would be the defect).

**K6 — Anything the repair should have covered and did not.** `service.py` still
holds three bare `except Exception: pass` blocks at `:995`, `:1024`, `:1062`. The
Bookkeeper checked each: all wrap `set_worker_exit_reason`, a best-effort audit
write, which is the legitimate narrow shape rather than the F2 shape. Verify or
reject that classification.

## Allowed Files

**None.** Read-only. Return findings in your terminal output; the Human operator
transfers them to the Bookkeeper.

## Inputs

| Path | Range | Why |
|---|---|---|
| `reports/agent-runs/2026-07-unknown-not-zero-v1/41-review-2-codex-result.md` | §F2 | The finding being repaired, and its verified chain |
| `reports/agent-runs/2026-07-unknown-not-zero-v1/44-f2-repair-glm.dispatch.md` | whole | What was ordered (R1-R4) |
| `reports/agent-runs/2026-07-unknown-not-zero-v1/45-task1c-glm-result.md` | whole | What the implementer claims |
| `reports/agent-runs/2026-07-unknown-not-zero-v1/46-bookkeeper-verification-task1c.md` | whole | The mutation-test evidence and the negative result on the other bare excepts |
| `git diff 851dd08..7cadb88` | whole | **The repair alone — start here** |
| `backend/hedge_open_tasks/service.py` | `985-1070`, `1180-1300`, `1390-1410` | Both sites, the new helper, the other bare excepts, the worker containment |
| `backend/tests/test_hedge_task_local.py` | `460-580` | The two new tests |
| `backend/hedge_open_tasks/domain.py` | `1017-1053` | The `ts_us` raise — K4 |

## Settled ground — do not re-litigate

All carry recorded reasons; filing one costs a round and will be declined.

1. **F1 (balance-missing → fabricated zero) is excluded by Human decision D-8.**
   Do not file it, do not file its absence as a risk. Context is preserved in
   `43-balance-shape-evidence.md`. It is a real pre-existing defect that Human
   chose not to fix now; that decision is not yours or mine to reopen.
2. **F3 (documents overstating the guard) is already corrected** by the Bookkeeper —
   `00-plan.md` in place, an erratum appended to `20-task1-glm-result.md` without
   editing the implementer's prose.
3. **Quantity is out of scope** (decision D-5); `cumulative_base_qty` keeping `'0'`
   is correct.
4. **The guard cannot cover the r5 category**, and saying so is correct behaviour.
5. **The five known guard evasions** (`or Decimal(0)`, `or 0`, ternary, laundering,
   `fee_amount` outside the money names) are recorded residual risks from your own
   earlier review. Not new findings.
6. **The review range contains bookkeeping commits and two unrelated `docs:`
   commits.** Harness finding G3, not a delivery defect.
7. **The flaky test** `test_hedge_api.py::test_oversized_body_is_body_too_large`
   (`ConnectionResetError`, passes on isolated re-run) is untouched. If it fires,
   re-run it alone and say so.

## Acceptance Checks

```text
python3 -m pytest backend/tests -q
```

Expected 1092 passed (previous 1090 + 2 new). Bookkeeper measured exactly that.

Your output must contain:

1. A verdict per judgement K1-K6, evidence-backed or explicitly undeterminable.
2. For K3, the real exception source you traced.
3. For K6, an explicit accept or reject of the Bookkeeper's classification.
4. Findings by severity, each with file, line, and a concrete failure scenario
   (inputs → wrong output). A finding without one is an opinion; label it.
5. Anything load-bearing that a later round must not weaken.

## Stop

Stop after the verdict. Return exactly the `[TASK_RESULT v2]` block from
`AGENTS.md` §7 — the nine mandated Chinese labels 任务 ID / 执行结果 / 结果摘要 /
产物 / 检查结果 / 阻塞项 / 本地北京时间 / 下一步模型 / 下一步任务, plus the three
closure lines 评审结论 / 问题记录 / 修复要求, closing with `[/TASK_RESULT]`.

No invented fields, no Identity block copied into the result, and the marker is not
`[/TASK_RESULT v2]`. `结果摘要` ≤ 300 characters, `检查结果` ≤ eight grouped items;
detail goes in prose above the block. `问题记录: none（结论在终端输出）` is correct
since you write no file.

`下一步模型: opus5（记账人，Human 转交结果）`.
