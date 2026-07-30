# Dispatch — review1r3-task1d-grok45

```text
Identity:
  task_id:         review1r3-task1d-grok45
  target_role:     Reviewer
  target_model:    grok-4.5
  provider:        xai
  status_revision: 16
  required_skill:  agents/skills/code-reviewer.md
```

Third review-1 pass, required by `AGENTS.md:181`: the repair touches `service.py`,
forbidden in the range you accepted. Read-only — no edit, no commit, no branch, no
network, no credentials, no service control, no read or write of `data/**`.

You accepted `ac8d493..851dd08` and then `ac8d493..7cadb88`. Provider isolation
holds: implementer `claude_glm` = `zhipu_glm`, you are `xai`.

## Goal

Judge **only** the incremental repair.

```text
new delivery range   ac8d493..7bd2bce
the repair alone     7cadb88..7bd2bce
```

An exhaustive audit (Codex, read-only) enumerated the discarded-failure family:
8 class-(A) sites, 2 already fixed as the template, 6 unfixed, 3 balance sites
excluded. Human then decided (D-10) to repair **five** and defer three with reasons.
This repair is those five:

| # | Site | Discarded call |
|---|---|---|
| S1 | `service.py:1178` | `resolve_leg_from_query` (a `continue` that also skipped the raw capture) |
| S2 | `service.py:1723` | `mark_attempt_rate_limited` |
| S3 | `service.py:1736` | `resolve_attempt`, pause-class settle |
| S4 | `service.py:1758` | `resolve_attempt`, normal settle |
| S5 | `service.py:1780` | `mark_leg_querying` |

Judge:

**N1 — Are all five correct?** Each records through the new
`_record_state_write_failure`, keeps catching so the worker survives, and does not
fabricate state. Does control flow still behave for a non-obvious exception type?
Is anything newly reachable?

**N2 — S1's raw-response preservation.** The old `continue` skipped
`_persist_leg_raw` immediately after it. Confirm the raw capture now runs when the
leg write failed, and that doing so cannot itself corrupt or duplicate a row.

**N3 — S2's ordering guarantee, the only non-uniform part.** Read
`service.py:418-425` and `:1360-1387`. An in-process
`_rate_limit_stamp_pending` set records a failed dispatch-time stamp;
`_rate_limited_for_settlement` retries at settlement and returns `True` **whether or
not the retry succeeds**, so a 429 pair never settles as an ordinary failure.

Check specifically:
- that **both** settlement call sites (`:1224-1232`, `:1263-1271`) route through the
  gate — a gate covering one path would leak the guarantee;
- the concurrency claim: "an attempt belongs to exactly one task and that task owns
  one worker thread, so each id is only ever touched by its own worker, and
  individual set ops are GIL-atomic". Is that true in this codebase, including the
  recovery-discovery and HTTP `fill-once` entry paths?
- the disclosed residual: a process restart loses the set, so an unstamped 429
  attempt then settles as an ordinary failure and consumes one count. Is the
  consequence correctly bounded (a task pauses one failure early, fail-closed), or
  worse than stated?

**N4 — Did the repair damage what you already accepted?** ⚠️ **Read this precisely.**
The implementer's report says F2's `settlement_failed` and its two call sites are
byte-identical. That is true of the **recording calls** — the Bookkeeper extracted
`_record_settlement_failure` at both commits and compared: identical, 1,861 bytes.
But **the settlement condition immediately above them changed at both sites**, from
`attempt.get("rate_limited")` to `self._rate_limited_for_settlement(...)`. That is
required by S2 and is not a violation, but F2's reviewed blocks do not begin the same
way any more. Judge that change on its merits rather than assuming those lines were
untouched.

Also confirm still intact: `domain.build_leg_exposure`'s `ts_us <= 0` raise, the
money-zero guard and its meta-tests, the paired per-site regressions.

**N5 — Are the five new tests load-bearing?** The Bookkeeper spot-checked one:
reverting S5 to a bare `pass` fails exactly `test_s5_mark_leg_querying_failure_is_recorded`
and nothing else (36 others pass). The implementer claims this holds per site. Verify
at least one other site yourself, and say which.

**N6 — Was anything in scope missed?** The five are from a closed audited list, not a
reviewer's guess. Confirm they are the five, that the deferred three were genuinely
left alone (not half-fixed), and that no class-(B)/(C) site was "improved while
passing".

## Allowed Files

**None.** Read-only. Return findings in your terminal output; the Human operator
transfers them to the Bookkeeper.

## Inputs

| Path | Range | Why |
|---|---|---|
| `git diff 7cadb88..7bd2bce` | whole | **The repair alone — start here** |
| `.../71-audit-result-and-scope-decision.md` | whole | The closed list, its classification, and what was deferred |
| `.../72-state-write-visibility-glm.dispatch.md` | whole | What was ordered (R1-R4) and what is out of scope |
| `.../73-task1d-glm-result.md` | whole | What the implementer claims |
| `.../74-bookkeeper-verification-task1d.md` | whole | Independent verification, the residual, and the F2 wording correction |
| `backend/hedge_open_tasks/service.py` | `55-70`, `405-430`, `1130-1300`, `1310-1400`, `1700-1830` | Event kinds, the pending set, all five sites, the gate |
| `backend/tests/test_hedge_task_local.py` | `460-700` | F2's two tests plus the five new ones |
| `backend/hedge_open_tasks/domain.py` | `1017-1053` | N4 |

## Settled ground — do not re-litigate

1. **The three deferred sites** — `service.py:1141`, `:1632`,
   `live_hedge_executor.py:690-702` — and the `entries` timeline question are deferred
   by **Human decision D-10**, each with a recorded reason. Do not file them as
   defects. If you believe deferring one is unsafe, say so as a **risk** in your
   findings, not as a repair requirement.
2. **F1 / the balance path** — excluded by D-8. Same rule.
3. **Quantity semantics** — out of scope by D-5.
4. **The money-zero guard's five evasions** — recorded residual risks from your own
   earlier review.
5. **No static guard for this family.** Codex's audit judged that no static rule can
   defend it (it cannot see `verdict is None`, thread-exception conversion, wrappers,
   aliases, or set-flag-then-return) and recommended a closed list plus
   fault-injection tests plus cross review. The Bookkeeper agreed. Do not ask for one.
6. **The range contains bookkeeping and two `docs:` commits** — Harness finding G3.
7. **The flake** `test_hedge_api.py::test_oversized_body_is_body_too_large`.

## Acceptance Checks

```text
python3 -m pytest backend/tests -q
```

Expected 1097 passed (1092 + 5). Bookkeeper measured exactly that.

Your output must contain:

1. A verdict per judgement N1-N6, evidence-backed or explicitly undeterminable.
2. For N3, an explicit answer on the concurrency claim and on whether the restart
   residual is correctly bounded.
3. For N5, which second site you mutation-checked and the result.
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
`问题记录: none（结论在终端输出）` is correct since you write no file.

`rework_count` is 2 of 3. If you return `REWORK`, the cap is reached and
`AGENTS.md:182` routes the next decision to Human — so a finding must be worth that,
and an opinion must be labelled as one.

`下一步模型: opus5（记账人，Human 转交结果）`.
