# Review-2 Result — Codex (`openai`), verdict REWORK

Transferred by the Human operator 2026-07-30 18:32 CST from a fresh read-only Codex
session run against `40-review-2-codex.dispatch.md`. Range `ac8d493..851dd08`.
Design involvement disclosed under decision D-6.

Format compliance: PASS — nine §7 labels, three closure lines, correct
`[/TASK_RESULT]` marker, no invented fields.

`rework_count` → **1**. This is a formal reviewer `REWORK` round for `task1`
(`AGENTS.md:182`), unlike the earlier pre-dispatch packet correction and the
Bookkeeper's own pre-review rejection. Two rounds of budget remain.

## Raw findings, verbatim

```text
- P1: 余额响应为 2xx（成功）但缺少目标资产、crossMarginFree 缺失或不可解析时，
  backend/services/hedge_preflight_provider.py:264 会跳过该值；
  backend/hedge_open_tasks/domain.py:947 随后伪造 available=0。结果是「无法读取余额」
  被错误显示为「余额不足」，并在实时路径中停止任务，而不是资料不完整后重试。

- P1: ts_us <= 0 时，backend/hedge_open_tasks/store.py:1238 抛出异常；
  backend/hedge_open_tasks/service.py:1205 和 backend/hedge_open_tasks/service.py:1238
  都静默吞掉。输入为终态单腿尝试与零/失效时钟，输出为 pair_outcome=NULL 的未结算尝试、
  后续准备被在途保护阻断且没有操作员可见记录。现有测试只确认辅助函数会抛异常，
  并未验证此运行后果。

- P2: 00-plan.md:15 的 "This stage closes the family" 与第 95 行 "prevents round 8"，
  以及 20-task1-glm-result.md:11 的同类表述过度承诺。review-1 已正确确认守卫只是
  防误操作的减速带，不能保证缺陷族不会回来。

修复要求：
1. 缺少所需余额资产必须返回 preflight_incomplete 与 available=None，不能伪造零；
   补充正反方向和不完整余额响应回归。
2. 结算时间戳异常必须进入操作员可见、可恢复的安全状态，不能由裸 except 静默吞掉；
   用注入的零时钟覆盖真实服务结算路径。
3. 更正上述阶段文档，明确守卫的已知范围与绕过限制。
4. 重跑 python3 -m pytest backend/tests -q；此次实测基线为 1090 passed。此修复扩大了
   文件和运行风险，按规则须重新 review-1（交叉评审）后再回到 review-2（最终评审）。
```

Verdict `REWORK`; blockers listed; `执行结果: completed`.

## Bookkeeper verification — all three CONFIRMED, two severity refinements

### F1 — balance-missing becomes zero. CONFIRMED, and worse than stated

The chain is exactly as described, verified line by line:

- `hedge_preflight_provider.py:249-259` fails closed only on transport error, no
  HTTP status, `>= 400`, or a non-list body. **A 2xx with a list body proceeds.**
- `:263-273` — a row whose `asset` or `crossMarginFree` is absent, or whose `free`
  will not parse, is skipped by `continue`. The returned dict simply lacks that
  asset. **Nothing signals that the read was partial.**
- `domain.py:947` / `:950` — `available = snapshot.balances.get(ASSET, Decimal(0))`.
  Missing asset → `Decimal(0)`.
- `:952`, `:958` — `balance_ok = available >= required` → False →
  `rejection = REJECT_INSUFFICIENT_BALANCE`.

**Worse than the review says**: `REJECT_INSUFFICIENT_BALANCE` is a member of
`PREFLIGHT_FATAL_REASONS` (`domain.py:296-298`) and maps to
`STOP_REASON_INSUFFICIENT_BALANCE` (`:309`). A fatal preflight **stops the task
permanently** — a stopped task is final, is not dispatch-eligible, and never
auto-resumes; the operator must create a new one. So the outcome is not a
misleading display, it is a task killed with a false reason (余额不足) for a
condition that is actually "we could not read the balance".

That is the same shape as the previous stage's S-1 design error, which was caught
for exactly the same reason: an operator told 保证金不足 about something that is
not a balance problem.

**This is a third miss of the "closed list", and it is mine.** `domain.py:947` and
`:950` appeared in my very first sweep output and I classified them into neither
§4a (must fix) nor §4c (audited, deliberately unchanged) — they are simply absent
from `00-plan.md` §4. The list has now been extended by every independent reader
who looked: the plan review found S4, Bookkeeper verification found the guard blind
to S2, review-1 found nothing new, review-2 found this. It is the most consequential
of the three misses because it changes behaviour rather than a displayed figure.

**Severity refinement the review did not make.** The failure requires that an asset
be absent from an otherwise-valid 2xx list, or its `crossMarginFree` be
unparseable. Two sub-cases behave differently and the fix must not conflate them:

- **Row present, `crossMarginFree` missing or unparseable, or a truncated list** —
  genuinely wrong. `0` is fabricated.
- **Row absent because the balance really is zero** — exchanges commonly omit
  zero-balance assets. Here `0` is *correct*, and returning
  `preflight_incomplete` instead would stall a task that should simply report
  insufficient balance.

Which case Binance actually produces cannot be determined from the repository, and
determining it needs an authorized read-only live observation, which no agent may
perform unbidden. **A fix that maps every missing asset to `incomplete` may trade a
false stop for a permanent stall.** This must be resolved before the fix is
specified, not during it.

### F2 — settlement exception swallowed. CONFIRMED; the real defect is broader and the named trigger is narrower

Verified:

- `store.py:1237-1238` — `finalize_attempt` calls `_exposure_from_legs`, which
  since D4 delegates to `domain.build_leg_exposure`, which raises on `ts_us <= 0`.
- `service.py:1204-1206` and `:1237-1239` — both call sites are wrapped in
  `except Exception: pass`.
- The consequence chain is real: an exception leaves `pair_outcome = NULL`, and
  `pair_outcome IS NULL` is precisely `prepare_attempt`'s in-flight guard
  (`store.py:712-717`), so the task is silently barred from opening another pair.
  The second bare except sits in the **crash-gap recovery loop** — the mechanism
  designed to unstick exactly this state — so recovery cannot recover it either.

**Refinement 1, against the review.** `now_us` comes from `self._wall_us()`, which
defaults to `_real_wall_us = int(time.time() * 1_000_000)` and is injectable only
through the constructor (`service.py:385-388`). With the production clock,
`ts_us <= 0` is unreachable. So P1 **as stated for the zero-clock trigger
overstates reachability**.

**Refinement 2, in the review's favour and more important.** The bare
`except Exception: pass` swallows *any* exception from `finalize_attempt` — rollup
errors, DB errors, a future bug — not only the timestamp one. Judged on that, P1 is
right, and the finding is better than its own justification: this is a pre-existing
defect that D4 made reachable by one additional path. It also means the correct fix
is not "handle the timestamp" but "stop discarding settlement failures".

**What this stage did do wrong**: D4 converted a cosmetic defect (silently writing a
1970 timestamp) into a task-stalling one, on a live settlement path guarded by a
bare except, and covered it with a test that only asserts the helper raises. My own
review-2 packet asked whether that was safe (J5); the answer is no, and the packet's
disclosure of the risk does not excuse shipping it.

### F3 — documents overstate the guard. CONFIRMED, and mine

Exact text verified:

- `00-plan.md:15` — "This stage closes the family instead of a site".
- `00-plan.md:95` — heading "## 5. Guard to add (this is what prevents round 8)".
- `20-task1-glm-result.md:11-12` — "family is closed at the root in one pass".

I wrote a document instructing others not to overstate the guard
(`31-review-1-grok45-result.md` §"Consequence for how this stage may be described")
while leaving the overstatement in the plan itself. Review-2 found the
inconsistency the packet asked it to hunt (J3), in the packet author's own text.
Uncontested; to be corrected.

## Route

Review-2's routing requirement is correct and follows the contract, not just its
preference: `AGENTS.md:181` — "A review-2 repair that expands files, changes a
contract, or adds risk must pass review-1 again." F1's fix touches
`hedge_preflight_provider.py` and the `PreflightResult` contract in `domain.py`,
both forbidden files in `task1`; F2's touches `service.py`, also forbidden. So the
repair re-enters at review-1 and then returns to review-2.

**Blocked pending a Human scope decision** — see `42-scope-decision-request.md`.
F1 is a different subsystem (preflight admission, not order records), changes a
domain contract, and carries the sub-case ambiguity above that cannot be settled
without an authorized live observation. Whether it belongs in this stage or its own
is a scope and risk call, not a Bookkeeper call.
