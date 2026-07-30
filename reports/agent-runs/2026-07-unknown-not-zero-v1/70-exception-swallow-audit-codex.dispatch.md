# Dispatch — audit-discarded-failures-codex

```text
Identity:
  task_id:         audit-discarded-failures-codex
  target_role:     Reviewer
  target_model:    codex (GPT-5 class)
  provider:        openai
  status_revision: 13
  required_skill:  agents/skills/code-reviewer.md
```

**This is an exhaustive audit, not a review of a delivery, and not a repair.** It
produces the closed, classified list that one repair will then work from. It does
not gate the delivery and it does not consume a rework round (`rework_count` is 2 of
3 and stays there).

Read-only: no edit, no commit, no branch, no network, no credentials, no service
control, no read or write of `data/**`. Read-only `git`/`grep`/`rg` and running the
test suite are expected.

Human asked for this directly: 「能否给 codex 再派做一次全面审查，把类似的问题都暴露出来」.

## Why you are being asked for a sweep instead of another fix

This defect family has now been repaired three times, one named site at a time:

1. F2 (your review-2, first pass) — two sites in the drain and crash-gap paths.
2. Your review-2 second pass — four more sites on the **post-order dispatch** path.
3. And a Bookkeeper sweep in between **wrongly declared the family closed**: it
   reported three remaining sites from a `grep … | head` whose output was truncated
   at ten lines. A full enumeration finds thirteen in `service.py` alone. That error
   is documented in `61-review-2-r2-codex-result.md` §"My own error".

The previous stage in this repository spent seven review rounds fixing whichever
site the reviewer named, and the stage after it found two more that all seven had
missed. Point-fixing this family is a proven failure mode. Do not produce a list of
"the worst ones"; produce the complete one.

## Goal

**A1 — Enumerate every site in the hedge subsystem where a failure is discarded.**

The family is broader than one syntax. Cover at least:

- `except …:` whose body is `pass`;
- `except …:` whose body is `continue` — `service.py:1178` is one, around a
  state-authoritative leg write, and it also skips the raw-response capture that
  follows it;
- `except …:` that degrades to a default and moves on without recording;
- non-exception discards: a guard that drops a failed or inconclusive result, e.g.
  `if verdict is None: continue` (`service.py` drain loop, the standing follow-up
  `p1-inconclusive-query-raw-not-persisted`);
- a swallowed failure inside a `finally` or a nested guard.

Scope: `backend/hedge_open_tasks/**` and `backend/services/live_hedge_executor.py`,
`hedge_open_live_client.py`, `hedge_preflight_provider.py`. State your scope and
your commands.

**A2 — Classify every site into exactly one of three classes.**

- **(A) State-authoritative write.** Losing it changes what the system believes
  about money, orders, or task eligibility. Must be visible to an operator and
  recoverable. Every one of these is a defect until it is.
- **(B) Best-effort audit write.** Losing it loses only a log line; the durable
  state is elsewhere and authoritative. A narrow guard is the correct form here, not
  a defect. `service.py:1818` (a `record_task_event` for `raw_persist_failed`) and
  `:1279` (the F2 fix's own guard) are the intended examples of this class.
- **(C) Deliberate containment.** Swallowing is the intended behaviour with a stated
  reason — e.g. a worker's last-resort handler that must not let one task's error
  kill the thread. Legitimate **only** where the reason is recorded and the durable
  state is authoritative; say which sites qualify and which merely look like it.

For each class-(A) site, add two facts: **is it after a POST** (an order may already
exist at the exchange), and **what an operator sees today**.

**A3 — Rank the class-(A) sites and say what the minimum repair is.**

Not a fix — the shape of one. Where the existing `record_task_event` pattern is
enough, say so. Where it is not — a lost `resolve_attempt` leaves an unsettled
attempt that the in-flight guard turns into a permanent stall — say what else is
needed, and whether that crosses into product semantics (a new pause reason, new
operator copy) which would require Human approval rather than an implementer's
choice.

**A4 — Can recurrence be prevented mechanically?**

This stage's durable deliverable was a static guard against fabricated money zeros
(`find_money_zero_defaults` in `backend/tests/test_hedge_purity.py`), which the
same author then evaded four times. Judge whether an analogous guard is possible
here — e.g. "an exception handler around a call to a state-authoritative store
method may not have a bare `pass`/`continue` body without a
`# discard-ok: <reason>` marker" — and be honest if it is not, or if it would be
defeated as easily as the money one was. A reasoned "no" is a complete answer and is
more useful than a guard nobody can trust.

**A5 — Discrepancy report, both directions.**

My enumeration is below. It was produced by a Bookkeeper whose previous enumeration
of this exact family was truncated and wrong, so treat it as a starting point to
verify, not as a boundary. Report sites I listed that you judge misclassified or
absent, **and** sites I missed. Both directions matter.

```text
service.py
   995  except Exception -> pass       set_worker_exit_reason
  1024  except Exception -> pass       set_worker_exit_reason (inside worker containment)
  1062  except Exception -> pass       set_worker_exit_reason
  1178  except Exception -> continue   resolve_leg_from_query  ** unclassified
  1279  except Exception -> pass       F2 fix's own audit guard
  1401  except Exception -> pass       thread join (pragma: no cover)
  1410  except Exception -> pass       ** unclassified
  1632  except Exception -> pass       resolve_attempt, record/dry-run path ** unclassified
  1723  except Exception -> pass       mark_attempt_rate_limited   (your P1)
  1736  except Exception -> pass       resolve_attempt, pause-class (your P1)
  1758  except Exception -> pass       resolve_attempt, normal path (your P1)
  1780  except Exception -> pass       mark_leg_querying           (your P1)
  1818  except Exception -> pass       record_task_event — believed class (B)
store.py
   479  except (TypeError, ValueError) -> continue  ** unclassified
```

Note the fact that motivates A4: `:1818` already implements the pattern F2's repair
introduced — catch, record an event, continue. The correct pattern existed about a
hundred lines from the wrong ones and was not reused.

## Allowed Files

**None.** Read-only. Return the audit in your terminal output; the Human operator
transfers it to the Bookkeeper. Do not write into the repository.

## Inputs

| Path | Range | Why |
|---|---|---|
| `reports/agent-runs/2026-07-unknown-not-zero-v1/61-review-2-r2-codex-result.md` | whole | Your own P1 verified, the Bookkeeper's error, the full site table |
| `backend/hedge_open_tasks/service.py` | whole (1,978 lines) — the audit needs the whole file | Every site |
| `backend/hedge_open_tasks/store.py` | search-driven; `700-720` for the in-flight guard, `470-485` | The store methods being called, and why a lost `resolve_attempt` stalls a task |
| `backend/hedge_open_tasks/executor.py`, `backend/services/live_hedge_executor.py`, `hedge_open_live_client.py`, `hedge_preflight_provider.py` | search-driven | Scope completeness |
| `backend/tests/test_hedge_purity.py` | `160-400` | A4: the analogous guard and how it was evaded |

Reading budget is deliberately exceeded for this task; the reason is recorded here
as `AGENTS.md:61` allows — an exhaustive audit cannot work from line ranges chosen
by the person whose previous enumeration was incomplete.

## Out of scope — do not fold in

- **F1**, the balance-missing→zero path, excluded by Human decision D-8. If a site
  you enumerate happens to sit in that path, list it and mark it D-8-excluded; do
  not repair-plan it.
- **Quantity semantics** (D-5).
- **The money-zero guard's five known evasions** — recorded residual risks, relevant
  only as A4's precedent.
- **Anything outside the hedge subsystem.** The borrow and snapshot subsystems have
  their own history; naming them widens this beyond what Human asked for.

## Acceptance Checks

Your output must contain:

1. The complete enumeration, one row per site, with file, line, shape, the call it
   guards, and its class (A/B/C).
2. For every class-(A) site: after-POST yes/no, and what an operator sees today.
3. The A3 ranking and minimum-repair shape, flagging anything that crosses into
   product semantics.
4. The A4 judgement, with a concrete evasion if you propose a guard.
5. The A5 discrepancy report in both directions, explicitly including sites I listed
   that you believe are **not** defects — a shorter correct list is a better result
   than a longer cautious one.
6. Your commands and raw output. A negative result stated as a negative: 「查过且没有」
   must stay distinguishable from 「没查」.

## Stop

Stop after the audit. Do not repair, do not prepare another packet, do not launch
another model.

Return exactly the `[TASK_RESULT v2]` block from `AGENTS.md` §7 — nine mandated
Chinese labels 任务 ID / 执行结果 / 结果摘要 / 产物 / 检查结果 / 阻塞项 /
本地北京时间 / 下一步模型 / 下一步任务, plus the three closure lines
评审结论 / 问题记录 / 修复要求, closing with `[/TASK_RESULT]`.

For this task the closure lines mean: `评审结论: ACCEPT` = no unclassified
class-(A) discard remains in scope, i.e. the family is now fully enumerated and any
remaining sites are legitimately (B) or (C). `REWORK` = class-(A) defects exist,
and `修复要求` names them. Either way the enumeration itself is the deliverable.

No invented fields, no Identity block copied into the result, marker is not
`[/TASK_RESULT v2]`. `结果摘要` ≤ 300 characters and `检查结果` ≤ eight grouped
items — the enumeration goes in prose above the block, not inside it.

`下一步模型: opus5（记账人，Human 转交结果）`.
