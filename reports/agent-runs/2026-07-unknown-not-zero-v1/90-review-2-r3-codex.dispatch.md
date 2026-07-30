# Dispatch — review2r3-task1-codex

```text
Identity:
  task_id:         review2r3-task1-codex
  target_role:     Reviewer
  target_model:    codex (GPT-5 class)
  provider:        openai
  status_revision: 17
  required_skill:  agents/skills/reality-checker.md
```

**Last gate before Human's merge decision.** Read-only: no edit, no commit, no
branch, no network, no credentials, no service control, no read or write of
`data/**`.

## Disclosure, unchanged

You have now touched this stage three times: its plan (`REWORK`), its delivery
(`REWORK`), and the exhaustive audit that produced the closed list this repair works
from. Prior involvement stands disclosed under Human decision D-6. Provider isolation
holds: implementer `claude_glm` = `zhipu_glm`, you are `openai`.

You wrote the audit that scoped this repair. **Judge whether the five sites are
actually fixed, not whether the work matches your list.**

## What changed since your last REWORK

```text
delivery now      ac8d493..7bd2bce   (was ac8d493..7cadb88)
the repair alone  7cadb88..7bd2bce
```

Your audit named 8 class-(A) sites: 2 already fixed (F2, the template), 6 unfixed,
3 balance sites excluded by D-8. Human then decided (D-10) to repair **five** and
defer three with written reasons.

Repaired: `service.py:1178` (S1, the `continue` that also skipped the raw capture),
`:1723` (S2, rate-limit stamp), `:1736` (S3), `:1758` (S4), `:1780` (S5). Each records
through a new `_record_state_write_failure` emitting a **new** kind
`state_write_failed` — `settlement_failed` was deliberately not renamed, since it is
already persisted in production rows.

Review-1 (Grok 4.5, `xai`) re-ran on this range and returned `ACCEPT`.

## Judgements

**P1 — Are the five actually fixed, behaviourally?** Not "is there a log line". For
each: does a failure reach an operator, does the worker survive, and is state left
un-fabricated? Check a non-obvious exception type, not only the injected one.

**P2 — S1's raw-response preservation.** Your audit's point was that the `continue`
lost both the verdict and the exchange's own words. Confirm the raw capture now runs
on the failure path and cannot corrupt or duplicate a row.

**P3 — S2's ordering guarantee.** Your audit asked for "在标记成功前不可按普通失败
结算". The implementation uses an in-process `_rate_limit_stamp_pending` set, retries
the stamp at settlement, and returns "settle without counter" **whether or not the
retry succeeds** — so the guarantee does not depend on the retry. Both settlement
call sites route through the gate. Judge whether that satisfies what you asked for,
and whether the disclosed restart residual (a restart between failed stamp and
settlement lets that attempt consume one consecutive-failure count; effect is a task
pausing one failure early, fail-closed) is correctly bounded.

**P4 — Were the deferred three genuinely left alone?** `service.py:1141`, `:1632`,
`live_hedge_executor.py:690-702` and the `entries` timeline. Not half-fixed, not
"improved while passing". Confirm by reading.

**P5 — Release readiness.** The judgement only you make here. The complete residual
list, so you judge against the real picture rather than rediscovering it:

| Residual | Status |
|---|---|
| F1 — a malformed/truncated balance read becomes `available = 0` → fatal stop with a false reason | Human-excluded, **no follow-up filed** (D-8) |
| `service.py:1141` inconclusive query, `:1632` dry-run settle, `live_hedge_executor.py:690-702` lost send-thread reason | Deferred with reasons (D-10), to `PROJECT_STATE.md` at close |
| These events are on the logs page but not the `entries` timeline | Deferred as operator-interface meaning needing Human approval (D-10) |
| S2's in-process pending set lost on restart | Disclosed residual, fail-closed |
| Money-zero guard: five confirmed evasions plus `fee_amount` outside the money names | Recorded residual risks |
| The guard cannot cover the r5 category (a migration over-nulling a real `'0'`) | By construction; paired regressions cover it |
| The money-zero site list was extended three times after being declared exhaustive — by your plan review, by Bookkeeper verification, and by you | Historical fact about how closed the list is |

Give an explicit recommendation: fit for Human's merge decision, or not, and what
risk remains after merge. **If you judge it unfit, say so plainly** — but note that
the Human-decided exclusions (D-8, D-10) are risks to state, not defects to re-file.

**P6 — Final sweep, and this is the last cheap moment.** Anything still unnamed in
the two families this stage touched — fabricated money zeros, and discarded failures.
A negative result stated as a negative is a complete answer: 「查过且没有」 must stay
distinguishable from 「没查」.

## Settled ground — do not re-litigate

1. **D-8, D-10, D-5, D-7, D-9** — Human decisions with written reasons in
   `01-human-decisions.md`. State residual risk under P5; do not re-file as defects.
2. **No static guard for the discarded-failure family** — your own A4 conclusion, which
   the Bookkeeper accepted.
3. **`state_write_failed` as a second kind rather than a rename** — `settlement_failed`
   has production rows and twice-reviewed assertions.
4. **F2's recording body is byte-identical (1,861 bytes, extracted and compared at both
   commits); its settlement condition changed legitimately under S2.** Judge the
   change, do not assume those lines were untouched.
5. **The range contains bookkeeping and two `docs:` commits** — Harness finding G3.
6. **The flake** `test_hedge_api.py::test_oversized_body_is_body_too_large`
   (`ConnectionResetError`, passes on isolated re-run), untouched.

## Inputs

`00-plan.md` remains top authority for what was required.

| Path | Range | Why |
|---|---|---|
| `git diff 7cadb88..7bd2bce` | whole | **The repair alone — start here** |
| `.../71-audit-result-and-scope-decision.md` | whole | Your audit and the scope reasoning |
| `.../72-state-write-visibility-glm.dispatch.md` | whole | What was ordered, and what is out of scope |
| `.../73-task1d-glm-result.md`, `.../74-bookkeeper-verification-task1d.md` | whole | The claim and its independent verification |
| `.../81-review-1-r3-grok45-result.md` | whole | Review-1's third ACCEPT, and the two-site mutation evidence |
| `.../01-human-decisions.md` | D-5..D-10 | The decisions |
| `backend/hedge_open_tasks/service.py` | `55-70`, `405-430`, `1130-1300`, `1310-1400`, `1700-1830` | Event kinds, pending set, five sites, the gate |
| `backend/tests/test_hedge_task_local.py` | `460-700` | F2's two tests plus the five new |
| `backend/hedge_open_tasks/domain.py` | `1017-1053` | The `ts_us` raise, unchanged |
| `backend/tests/test_hedge_purity.py` | `160-400` | The money-zero guard, unchanged |

## Acceptance Checks

```text
python3 -m pytest backend/tests -q
```

Expected 1097 passed. Bookkeeper and review-1 both measured that.

Your output must contain:

1. A verdict per judgement P1-P6, evidence-backed or explicitly undeterminable.
2. For P6, your sweep commands and raw output; a negative result stated as negative.
3. For P5, an explicit release recommendation and the post-merge risk.
4. Findings by severity, each with file, line, and a concrete failure scenario. A
   finding without one is an opinion; label it.
5. What is load-bearing and must not be weakened later.

## Stop

Stop after the verdict. Return exactly the `[TASK_RESULT v2]` block from
`AGENTS.md` §7 — nine mandated Chinese labels 任务 ID / 执行结果 / 结果摘要 / 产物 /
检查结果 / 阻塞项 / 本地北京时间 / 下一步模型 / 下一步任务, plus the three closure
lines 评审结论 / 问题记录 / 修复要求, closing with `[/TASK_RESULT]`.

No invented fields, no Identity block copied in, marker is not `[/TASK_RESULT v2]`.
`结果摘要` ≤ 300 characters, `检查结果` ≤ eight grouped items.

`评审结论: ACCEPT` means fit for Human's merge decision.

**`rework_count` is 2 of 3.** A `REWORK` here reaches the cap, and `AGENTS.md:182`
then routes the next decision to Human: narrow, redesign, accept a limitation, or
stop. So a finding must be worth that, and anything short of it must be labelled an
opinion or a risk rather than a repair requirement. This is not a request to soften
your judgement — it is a request to be precise about which kind of statement you are
making.

`下一步模型: opus5（记账人，Human 转交结果）`.
