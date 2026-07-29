# Narrow Design Revision Dispatch — T2's `51169` Semantics And T4's Replacement

Human operator: run this in a fresh **Claude Fable 5** session (backup: Opus 4.8;
record which ran). Design-only, no code, no other model.

## Why this exists

The three design artifacts were produced at **2026-07-28 14:45:33 CST** against
the packet as it stood then. The packet was revised at **14:46** (commit
`5fe1a6f`) because T4's root cause had just been established from the user's own
Binance app and Binance's official documentation. The design therefore never saw
`02-collateral-cap-finding.md`.

**The design is not being re-run.** T1, T3, T5, the historical-data migration
(§6), the schema summary (§7), the stale-recon review (§9) and the file
boundaries (§10) are all unaffected and stand as written. Two things are stale,
and one of them is a factual error that this stage exists to prevent.

The revision must be **surgical**. Reproduce the two affected sections in full,
revised, plus the small downstream edits listed below. Do not restate or
"improve" anything else.

## Required reading

- `reports/agent-runs/2026-07-hedge-order-truth-v1/02-collateral-cap-finding.md`
  — the new evidence. Read this first.
- The revised `00-task.md` §T2 (the `51169` block) and §T4, and
  `status.json.scope.T2.required_verdict_for_51169` and `.scope.T4`.
- Your own `10-design.md` §2, §5, §8, §11; `11-adr.md` ADR-T2; and
  `12-development-breakdown.md` §3 test line and §4.

## Stale item 1 — `51169 → insufficient_funds` is factually wrong

`10-design.md` §2(a) seeds `MARGIN_BUSINESS_CODES` with
`51169 → insufficient_funds`, calls it 「与 UM 的 -2019 同义」, and §2(d) maps it
to `pause_reason = insufficient_margin`. `11-adr.md` ADR-T2 records the same.

That reasoning was sound given the packet you had — the code's own name is
`MARGIN_TRADE_COEFF_INSUFFICIENT`. It is now known to be wrong:

`51169` is **not** an insufficient-funds fact about this account. NOM is above
Binance's platform-wide, per-asset **Maximum Collateral Limit** — a cap shared
across all users, explicitly covering Portfolio Margin. Above 100% utilisation,
buying or transferring that asset into a margin account is blocked outright; the
user's app reports a maximum buy quantity of `0`. Adding balance does nothing.

Why this matters more than a label: `store`'s insufficient-funds path is
documented as 「a CONFIRMED insufficient balance/margin/available-quantity
fact」, and `insufficient_margin` will render an operator message meaning
**保证金不足**. Telling the operator their margin is short, when the truth is
that a platform-wide cap on that coin is full, is exactly the
plausible-but-false substitution this stage was opened to eliminate. Your own
`§11` risk 4 asked review to confirm the user accepts 「margin 保证金不足现在会
暂停任务」 — that question's premise is false.

Revise §2(a), §2(c), §2(d), ADR-T2, and the §8 T2 test bullet to give `51169` a
category and operator copy that state what is true. Decide and justify:

- **(a) Its own category, or a sub-reason under an existing one?** The stage's
  discipline is that unrecognised and recognised must stay distinguishable; the
  same logic argues a *misdescribed* condition is no better than an
  unclassified one. State which you choose and why.
- **(b) What task-level outcome?** Pausing (stop retrying) is plausibly still
  correct — the cap will not clear in a task's retry window. But say so on the
  correct grounds, not by inheriting `-2019`'s. Also note the asymmetry: this
  blocks the **forward** direction's spot leg for that asset; the perp leg is
  unaffected.
- **(c) The 90–100% band.** Between 90% and 100% of the cap a **smaller** order
  can still succeed (capped at 50,000 USD equivalent). So `51169` does not
  universally mean 「任何数量都不行」 — for NOM today it does, because NOM is
  above 100%. A design that treats quantity as irrelevant is wrong in that band.
  Decide whether the system should do anything about it or merely not claim
  otherwise, and justify. Do **not** add a retry-with-smaller-size mechanism to
  this stage's scope; if you think it is warranted, record it as a follow-up.
- **(d) Not permanent.** The cap is consumed by all users' holdings, so a blocked
  asset can clear later. Nothing may cache this as a static property of a coin,
  and nothing may permanently blacklist the coin.
- **(e) The Chinese operator copy**, verbatim and frozen, saying what is true:
  this coin's platform collateral cap is full, the spot leg cannot be bought into
  the margin account right now, try another coin or later.

Keep everything else about T2 — the `(product, code)` keyed tables, the shared
gateway layer first, the explicit `unclassified` category, conservative seeding,
the attempt-row roll-up, the negative-code non-regression matrix, and the
rejected alternatives. Those are unaffected and good.

Update §2(c)'s verdict-change table to match whatever you decide, and update §11
risk 4 to the real question.

## Stale item 2 — T4's discriminator order is cancelled

`10-design.md` §5 specifies the paid discriminator order. Its interpretation was
pre-registered as 「仍然 51169 ⇒ 与并发无关：原因在抵押折算系数或钱包位置」 —
which is the branch now reached. The app reports a maximum buy quantity of `0`,
so the order would spend real money to confirm a known answer. **Cancelled. This
stage places no order at all.** The concurrency-contention hypothesis is not
disproven but is no longer needed; the cap explains the identical failure with
zero concurrency.

Replace §5 entirely with the read-only successor. It must specify:

- **The recon question**: does *any* API surface expose the per-asset collateral
  cap or its current utilisation? Two official FAQ pages name none. That is not
  proof of absence in the API — treat it as an open fact, and do not write either
  answer as a conclusion.
- **Method**: public documentation reads and signed **GET** reads only. No order,
  no write, no service start. Name the candidate endpoints worth checking and say
  what each would prove or fail to prove.
- **Evidence path** under `reports/api-samples/2026-07-hedge-order-truth-v1/`,
  and who executes it.
- **The preflight decision, conditional on the answer**: endpoint exists → design
  a real gate against it; no endpoint → the preflight cannot see this constraint
  and must not pretend to, handling belongs entirely to T2, and say that
  explicitly. 「preflight 有意不动，理由如下」 is a complete, acceptable T4
  outcome — the preflight (`domain.py:806-825`) still may not change until the
  recon answers.
- **Time-varying**: nothing may cache the cap as static.

Then update `12-development-breakdown.md` §4 and `10-design.md` §11 risk 7, both
of which currently tell the bookkeeper to request the user's authorization for an
order. No authorization is needed to *not* place one.

## One thing you found that survives, and grows

§5(a) noted, correctly, that buying 10000 NOM spot would have **hedged** the
outstanding SHORT 10000 NOMUSDT rather than creating new exposure. That
observation now has a sharper consequence worth recording where the design
discusses the outstanding position: while NOM is above its cap, that route is
**unavailable** — the naked short cannot be flattened by buying spot into the
margin account. Closing it means buying back the perp on UM, which the collateral
cap does not touch. Record it as a factual mechanism note only. Unwinding is the
user's action, closing functionality is the programme's third stage, and neither
is in this stage's scope.

## Output

Produce **three** blocks, each fenced with an explicit file marker, to be saved
over the existing files:

```text
=== FILE: 10-design.md ===   (full file, with §2 / §5 / §8-T2 / §11 revised)
=== FILE: 11-adr.md ===      (full file, with ADR-T2 revised)
=== FILE: 12-development-breakdown.md ===  (full file, with §3 test line and §4 revised)
```

Full files, because they are saved over the originals — but the diff must be
confined to the sections named above. The originals are already committed
(`acfccbd`), so any drift outside those sections is visible in review and will be
treated as an unrequested change.

Add a short 「## 修订记录」 section at the end of `10-design.md` stating what was
revised, why, and against which evidence file. Do not silently rewrite history.

## Hard constraints

- Design only. No product source, no `status.json`, no `70-handoff.md`, no PRD.
- ⚠️ The live surface is open: service PID 96409 in live mode, `start_gate=1`, a
  real naked SHORT 10000 NOMUSDT outstanding. No card, no Start, no order, no
  credentials, no service start/stop, no write to
  `data/hedge-open-tasks.sqlite3`. Read-only queries are permitted.
- Facts carry paths. Anything unverified is labelled 未验证. The whole reason
  this revision exists is that a fact with a shelf life went unrechecked.

最后附上下面的 footer。

当前 Session ID: 报告你的 provider-native id，取不到就写 unavailable 并说明原因
Session ID 来源: runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/10-design.md, 11-adr.md, 12-development-breakdown.md
本地北京时间: 用本地 date 命令取
下一步模型: bookkeeper
下一步任务: 归档修订后的三份产物并核对 diff 是否只落在指定章节

Current dispatch executor: **human operator**.

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/16-design-revision.dispatch.md
本地北京时间: 2026-07-28 15:05 CST
下一步模型: human operator
下一步任务: 在全新的 Claude Fable 5 终端执行本 packet
