# Dispatch — review2r2-task1-codex

```text
Identity:
  task_id:         review2r2-task1-codex
  target_role:     Reviewer
  target_model:    codex (GPT-5 class)
  provider:        openai
  status_revision: 12
  required_skill:  agents/skills/reality-checker.md
```

Final gate, second pass. Read-only: no edit, no commit, no branch, no network, no
credentials, no service control, no read or write of `data/**`. Read-only
`git`/`grep`/`rg` and running the test suite are expected.

## Disclosure, unchanged

You reviewed this stage's **plan** (`task0-plan-review`, `REWORK`) and then its
**delivery** (`review2-task1-codex`, `REWORK`). Prior design involvement stands
disclosed under Human decision D-6. Provider isolation holds: implementer
`claude_glm` = `zhipu_glm`, you are `openai`.

You raised the three findings this pass must judge. That makes you well placed and
also the reviewer most likely to accept a fix because it addresses the words you
wrote rather than the defect behind them. **Judge the behaviour, not the response
to your text.**

## What changed since your REWORK

```text
delivery now      ac8d493..7cadb88   (was ac8d493..851dd08)
the repair alone  851dd08..7cadb88
```

- **F2 repaired.** Both settlement sites now record a `settlement_failed` event
  through the existing `record_task_event` channel instead of discarding the
  exception. New helper `_record_settlement_failure` (`service.py:1256-1290`) with a
  narrow inner guard around the audit write only. Two new tests drive the real
  service path with an injected zero clock.
- **F3 corrected by the Bookkeeper**, not the implementer: `00-plan.md` §1 and the
  §5 heading rewritten in place with a dated note; an erratum appended to
  `20-task1-glm-result.md` **without editing the implementer's delivered prose**.
- **F1 dropped by Human decision D-8.** See §Human decisions below — read it before
  forming a view.
- Review-1 re-ran (Grok 4.5, `xai`) on the new range and returned `ACCEPT`, required
  because the repair touched a file forbidden in the range you reviewed
  (`AGENTS.md:181`).

## Judgements

**M1 — Is F2 actually fixed, behaviourally?** Not "is there now a log line". Does a
settlement failure now reach an operator, does the worker survive, and does the task
still avoid a fabricated settlement? Check what happens on a **non**-timestamp
exception too — that was the substance of your finding, not the clock.

**M2 — Are the two new tests load-bearing?** The Bookkeeper mutation-tested them:
reverting the drain site fails the drain test only; reverting the crash-gap site
fails both, because the drain test's `>= 2` needs both sites
(`46-bookkeeper-verification-task1c.md` §2). Re-derive independently if you doubt it.
Judge whether `>=` rather than `==` leaves a hole.

**M3 — Is F3's correction adequate, or cosmetic?** You quoted three overstatements.
Read what replaced them. Does the record now state the guard's real reach —
including the five confirmed evasions and that the site list was extended three
times after being declared exhaustive — or has an inflated claim been replaced by a
softer inflated claim?

**M4 — Did the repair damage anything you accepted?** The `ts_us <= 0` raise, the
money-zero guard and its meta-tests, the paired per-site regressions. Confirm by
reading.

**M5 — Release readiness, with F1 knowingly open.** This is the judgement that
matters and the one only you can make here.

F1 is excluded by Human decision, so **do not file it as a defect finding requiring
repair** — that decision is not a reviewer's or a Bookkeeper's to reopen. But you
are the release gate, and your independence is not waived: if you judge that merging
with F1 open is not fit for release, **say so plainly in your release
recommendation**, with the concrete scenario and its consequence, and Human will
decide with that in front of them. Stating a risk is your job; re-filing a
Human-decided exclusion as a blocker is not. Do not soften your assessment to be
agreeable, and do not smuggle it back as a different finding id.

**M6 — Anything still missed.** Third-and-final sweep. You found the balance path
last time; the closed list has now been extended by the plan review (S4), Bookkeeper
verification (the guard blind to S2), and you (`domain.py:947/950`). If a money site
remains unnamed, this is the last cheap moment to say so. A negative result stated
as a negative is a useful answer — 「查过且没有」 must stay distinguishable from
「没查」.

## Human decisions — recorded, not reviewable

Each is a Human call with a written reason in `01-human-decisions.md`. A reviewer may
state residual risk (M5) but may not re-file these as defects:

1. **D-8 — F1 ignored, no follow-up filed.** Human's reasoning: the trigger needs a
   malformed or truncated balance response; the failure is fail-closed (it stops a
   task, it never places an order or moves money); a domain-contract change on a
   fatal-stop admission path is not worth paying for speculatively.
   `43-balance-shape-evidence.md` preserves the analysis, including that the correct
   pattern already exists in a sibling module (`snapshot.py:924-926` — `None` plus a
   warning, real zero preserved) so the eventual fix is not a design question.
2. **D-5 — quantity out of scope.** `cumulative_base_qty` is `TEXT NOT NULL DEFAULT '0'`;
   honesty there costs a live-table rebuild, and a leg never sent genuinely has zero
   fill.
3. **D-7 — `task2` withdrawn** from this stage into the Harness batch. The stage's
   scope is `task1` only. Do not file the stage as incomplete.

## Settled ground — do not re-litigate

1. **The guard cannot cover the r5 category** (a migration over-nulling a real
   `'0'`); the paired regressions cover it, and saying so is correct behaviour.
2. **The five guard evasions** — `or Decimal(0)`, `or 0`, ternary, laundering through
   an intermediate variable, `fee_amount` outside the money names — are recorded
   residual risks, raised by review-1 and confirmed by the Bookkeeper. Relevant to
   M3 and M5; not new findings.
3. **D6 prevents semantic row rewriting, not all writes.** Additive DDL still writes;
   the `hedge_open_leg` rebuild is `PRAGMA`-guarded.
4. **Three bare `except Exception: pass` remain in `service.py`** (`:995`, `:1024`,
   `:1062`); all wrap `set_worker_exit_reason`, a best-effort audit write. Two
   independent readings (Bookkeeper, review-1 K6) agree this is the legitimate narrow
   shape. Reject it if you disagree, but with a failure scenario.
5. **The range contains bookkeeping commits and two unrelated `docs:` commits** —
   Harness finding G3, not a delivery defect.
6. **The flake** `test_hedge_api.py::test_oversized_body_is_body_too_large`
   (`ConnectionResetError`, passes on isolated re-run) is untouched.

## Inputs

`00-plan.md` remains top authority for what was required.

| Path | Range | Why |
|---|---|---|
| `git diff 851dd08..7cadb88` | whole | **The repair alone — start here** |
| `.../41-review-2-codex-result.md` | whole | Your own findings and the Bookkeeper's verification of them, including two severity refinements |
| `.../44-f2-repair-glm.dispatch.md` | whole | What was ordered for F2 (R1-R4) |
| `.../45-task1c-glm-result.md` | whole | What the implementer claims |
| `.../46-bookkeeper-verification-task1c.md` | whole | Mutation-test evidence, the negative result on the other bare excepts |
| `.../51-review-1-r2-grok45-result.md` | whole | Review-1's second ACCEPT and the credential-bound argument |
| `.../01-human-decisions.md` | D-5, D-7, D-8 | The decisions above |
| `.../43-balance-shape-evidence.md` | whole | F1's preserved analysis — for M5's risk statement |
| `.../00-plan.md` | §1, §3, §5 | M3: the corrected text |
| `.../20-task1-glm-result.md` | the appended erratum | M3 |
| `backend/hedge_open_tasks/service.py` | `985-1070`, `1180-1300` | Both sites, the helper, the other bare excepts |
| `backend/tests/test_hedge_task_local.py` | `460-580` | The two new tests |
| `backend/hedge_open_tasks/domain.py` | `550-575`, `1017-1053` | `HedgeError`, the `ts_us` raise |
| `backend/tests/test_hedge_purity.py` | `160-400` | M4: the guard, untouched |

## Acceptance Checks

```text
python3 -m pytest backend/tests -q
```

Expected 1092 passed. Bookkeeper and review-1 both measured that.

Your output must contain:

1. A verdict per judgement M1-M6, evidence-backed or explicitly undeterminable.
2. For M6, your sweep commands and raw output, negative result stated as negative.
3. For M5, an explicit release recommendation: fit for Human's merge decision or
   not, and the residual risk after merge — including F1's, framed as risk rather
   than as a finding.
4. Findings by severity, each with file, line, and a concrete failure scenario. A
   finding without one is an opinion; label it.
5. What is load-bearing and must not be weakened later.

## Stop

Stop after the verdict. Return exactly the `[TASK_RESULT v2]` block from
`AGENTS.md` §7 — nine mandated Chinese labels 任务 ID / 执行结果 / 结果摘要 / 产物 /
检查结果 / 阻塞项 / 本地北京时间 / 下一步模型 / 下一步任务, plus the three closure
lines 评审结论 / 问题记录 / 修复要求, closing with `[/TASK_RESULT]`.

No invented fields, no Identity block copied into the result, and the marker is not
`[/TASK_RESULT v2]`. `结果摘要` ≤ 300 characters, `检查结果` ≤ eight grouped items;
detail goes in prose above the block. `问题记录: none（结论在终端输出）` is correct
since you write no file.

`评审结论: ACCEPT` means fit for Human's merge decision. `REWORK` requires findings
plus executable repair requirements. `rework_count` is 1 of 3.

`下一步模型: opus5（记账人，Human 转交结果）`.
