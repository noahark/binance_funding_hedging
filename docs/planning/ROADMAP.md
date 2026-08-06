# Roadmap

Status: as-built roadmap sync + position-cycle plan, 2026-08-03

This file is the canonical approved roadmap.

## Milestones

1. Public market API contract discovery. Done.
2. Public market backend snapshot API. Done.
3. Frontend market table and manual-open planning UI against the frozen backend
   contract. Done.
4. Private account discovery and read-only account validation. Done for the
   current snapshot surface.
5. Borrow-cost display, private-account UI polish, and borrowability edge-case
   mapping. Done for current read-only scope.
6. Real PM borrow execution (Boundary C live path, durable tasks, global Start).
   Landed on local main; operator live validation ongoing. See
   `docs/planning/CHANGELOG-2026-07-22-live-borrow-ops.md` and
   DEC-2026-07-22-001…003.
7. Manual open planning + market-order execution (spot/perp hedge). **Live and
   in use, with known limitations.** Durable hedge-open tasks, a task-local
   worker, real PAPI order dispatch behind the Start gate, an inline per-attempt
   log, and a backend-merged position table have all shipped. Real orders have
   been placed. The open items are display honesty and runtime verification, not
   capability — see Current Focus and `PROJECT_STATE.md`.
8. Accounting, reconciliation, and alerting. Future.
9. **Position cycle + per-cycle cost statistics. Planned (see below).**

## Planned: 持仓周期三功能（2026-08 排期）

依赖链：**周期表（地基）→ 费率/利息统计（只读消费）→ 平仓记录 + 平仓执行（最重）**。
功能 2 是 3 和 1 的共同地基；功能 1b（平仓执行）是系统第一次获得主动改仓能力，风险最高，
放在最稳的地基之后。

| 顺序 | 功能 | 交付物 | 风险级别 | 独立验收点 |
|---|---|---|---|---|
| ① | 持仓周期表 | `hedge_open_cycle` + `attempt.cycle_id` + 聚合按周期拆分 + 历史回填 + **预留 `close_cycle` 关闭接口（供功能③调用；不做自动归零观察、不接线触发逻辑）** | HIGH_RISK（改记账口径；纯记账无实盘下单） | 平仓再开仓不混算；起始持仓时间正确；`close_cycle` 契约（幂等/单向/事务）单测通过（设计 v1 §8 用例 1/2/2b/3/4/5/5b/8） |
| ② | 费率/利息统计 | 持仓行 `accrued_funding`/`borrow_interest`/`net_pnl` 从占位「暂无」变周期窗口真值（自 ledger-flow 现算） | 中（资金/PnL 展示，纯读） | 三列真值；覆盖率不足降级显示 |
| ③a | 平仓记录 | `hedge_open_cycle_close_log` + 平仓完成/人工核实时写结算日志 + 历史仓位页（已做 fake）接真数据 | 低（结构先行） | 历史仓位 fake → 真实（开/平时间、费率、利息真值；平单均价/滑点仍占位） |
| ③b | 平仓执行 | 真实平仓（实盘双腿、滑点校验、还债、资金移动），**平仓完成调用①预留的 `close_cycle`（close_reason='auto_close'）** | 最高（实盘资金操作，需 Human 授权 + 最严评审） | 平仓事件精确关周期；close_log 补全平单均价/滑点 |

**状态（2026-08-06）**：① ② ③a ③b **全部开发完成并实盘验证，Human 2026-08-05 验收通过**；
**sonnet5 综合评审完成（review-1+review-2 合一）：首轮 REWORK（1 处真实 P0：平仓 fresh preflight
余额校验方向未反转）→ DeepSeek 一行修复 + 2 条 live 回归测试 → sonnet5 复评 ACCEPT（受控还原
验证测试真实钉住缺陷，`2026-08-hedge-position-cycle-v1-review-sonnet5.handoff.md` 复评节）**。
修复链全部生效：现货卖出路由重设计（普通账户+划转+复检+USDT 回流）、划转前统一余额检查、close
完成判定重构（running→其他状态先走合约无仓核实）、前端提前量检测、任务卡开平仓标记、导航徽标
联动、历史页补全（现货均价/成交量/成交额/滑点 %）。持仓表口径：只显示未平仓周期
（`closed_at_us IS NULL` 过滤）。本地数量口径保持现状（方案 B 已回退，整改方案待 Human 定）。
四任务交付 + 全部修复在工作树**未提交**（`delivery_sha=pending`）。**下一步（Human 决策）**：
提交代码 / 合并 / Bookkeeper 补记 status.json；**close_gate 实盘启用（平仓发单）需 Human 单独
明确授权，评审 ACCEPT 不构成该授权**。挂账 follow-up：本地数量与交易所脱节（X/Y/Z 方案待定）、
MUUUSDT 现货别名配对、close_log 利息 ≈U（价格源注入 service 层）。

设计权威：`docs/planning/hedge-open-position-cycle-v1.md`（周期设计 v1；五项口径 + 关闭触发决策已拍板——**不做自动归零观察，关闭由功能三平仓任务触发、人工核实作纠偏**）。
开发文稿：`docs/planning/hedge-open-cycle-stage2-cycle-dev.md`（功能 ①）、
`docs/planning/hedge-open-cycle-stage3-stats-dev.md`（功能 ②）。
前置检查：功能 ② 开始前核对 ledger-flow 覆盖率（`interest_coverage_start/end`、
`income_coverage_start/end`），历史窗口未拉全时统计会偏小。

## Current Focus

Hedge-open display honesty, then runtime verification. Detail and acceptance
state for every item below live in `PROJECT_STATE.md`.

- **F4 — the position table claims "exchange has no position" without checking.**
  The fix is fully specified and plan-reviewed, deliberately not implemented.
  It remains an accepted limitation and release/runtime concern; if restarted,
  read the archived stage closure record and the Opus5 report §9. The third-path
  smoke coverage is also a follow-up to archive `49-`.
- **Task-card pause reasons render 1 of 7 in Chinese** — the frontend never reads
  the `pause_reason_zh` the backend already returns. Two-line change.
- **Run the read-only smoke checklist** (`archive/2026-07-31-hedge-task-lifecycle-v1`
  file `49-`). Never executed; now a hard prerequisite for the next live
  activation. Nothing in the hedge-open path has runtime evidence.
- The lifecycle rework (deadlock fix, five-reason auto-delete, `rate_limited`
  backoff) is designed and deliberately deferred — DEC-2026-08-02-003 and
  `docs/planning/deferred-hedge-task-lifecycle.md`.
- Keep canonical docs aligned with as-built code (this roadmap, DECISIONS,
  DEVELOPMENT_GUIDE, public-market contract).

## Done (Selected)

- `2026-07-public-market-contract-v2`: public endpoint field verification and
  initial backend-to-frontend snapshot contract.
- `2026-07-public-market-impl-v1`: backend snapshot implementation.
- `2026-07-public-market-ui-cn-v1`: Chinese workstation UI over the snapshot
  contract.
- `2026-07-public-market-bstock-alias-v1`: bStock route alias amendment.
- `2026-07-private-account-v1`: optional private read-only signed GET channel,
  account blocks, borrow validation, and borrow-cost enrichment.
- `2026-07-private-account-ui-polish-v1`: private-account UI and value display
  polish.
- `2026-07-phase2-borrow-sort-v1`: borrow-aware sort basis.
- `2026-07-ui-filter-balance-metal-v1`: metal asset tagging and UI balance
  updates.
- `2026-07-borrow-cost-coverage-v2`: borrow-cost coverage updates.
- `2026-07-borrowability-error-zero-mapping-v1`: maps borrowability error
  `51061` into the zero-borrowable display path.
- `2026-07-real-borrow-boundary-c-v1` (+ execution stages): durable borrow
  tasks, live PM `marginLoan` path, execution gates, recon skeleton.
- 2026-07-22 live-ops patches (session changelog): Scheme A/C classification,
  attempt-log coalesce, error-code labels, `cross_margin_borrowed` UI, market
  workstation polish (正费率 badge, opening-quote price trim, snapshot meta).
- Hedge open, 2026-07-22 → 2026-08-02: fake UI, dry-run skeleton, the real-API
  round (first real order rejected on a 38-char clientOrderId), live hardening,
  order-truth, the inline per-attempt log, the backend-merged position table, and
  the 500ms re-query cadence with a ten-try retry budget. DEC-2026-07-30-001…003
  and DEC-2026-08-02-001…003.

## Next Product Work

- Optional: durable `fail_count` / true attempt counters if coalesce-aware stats
  are needed on the task card.
- Optional: surface `crossMarginInterest` next to borrowed principal.
- API route naming and wire version cleanup for the now mixed public/private
  read-only snapshot contract.
- Clearer borrowability state semantics beyond the generic `verified` flag
  (green「已验证可借」still does not mean maxBorrowable was probed).
- Websocket depth display after operator clicks open.
- Position mismatch monitoring beyond the current merged table (the single-leg
  marker under-reports partial imbalance; drift detection reads the wrong
  account pool and is permanently inert).
- Funding, commission, rebate, and borrow-interest accounting.
