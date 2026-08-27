# Roadmap

Status: as-built roadmap sync, 2026-08-27. Live detail and acceptance state:
`PROJECT_STATE.md`.

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
7. Manual immediate and smooth market-order execution (spot/perp hedge).
   **Live and in use, with known limitations.** Durable tasks, Human Start,
   public spot/perpetual L1 WebSocket gates, timeout/manual current-round
   release, concurrent two-leg dispatch, per-attempt logs, smooth dispatch
   audits, and the backend-merged position table have shipped. Real orders have
   been placed and closed. F-A and the accepted timing/UI limits remain in
   `PROJECT_STATE.md`.
8. Accounting, reconciliation, and alerting. Future.
9. **Position cycle + per-cycle cost statistics. Done — developed,
   live-validated, Human acceptance 2026-08-05 (see below).**
10. **Manual Portfolio Margin debt repayment. Done — T1/T2 delivered, dual
    review accepted, XLM specified-amount and INJ full repayment live-verified,
    Human final acceptance 2026-08-10.** The independent repayment gate remains
    enabled by Human decision; automatic repayment is still out of scope.
11. **Hedge order trading fee costing and BNB price freezing v1 (成交手续费冻价成本 V1).
    Done — Phase 1/2/3 delivered, dual review accepted across all phases (Kimi ACCEPT +
    Opus 5 ACCEPT), 268/269 historical legs backfilled, real-time commit-first write
    live-verified, merged to main and deployed 2026-08-20.** Position table renders
    realtime USD-equivalent fee costs and BNB quantity; close cycles freeze total fee costs
    on close; legacy close logs remain immutable.
12. **Single-instance cloud UI/API login and HTTPS deployment. Done.**
    One `.env` supplies one HTTP Basic username/password; all UI and business
    APIs are protected, health probes remain public, and remote binds fail
    closed without credentials. The first AWS instance runs the reviewed commit
    behind a loopback-only Docker/systemd boundary and a Caddy-managed HTTPS
    endpoint. Password hardening remains required before private Binance access.


## 持仓周期三功能（2026-08 交付，Human 验收通过）

依赖链：**周期表（地基）→ 费率/利息统计（只读消费）→ 平仓记录 + 平仓执行（最重）**。
功能 2 是 3 和 1 的共同地基；功能 1b（平仓执行）是系统第一次获得主动改仓能力，风险最高，
放在最稳的地基之后。

| 顺序 | 功能 | 交付物 | 风险级别 | 独立验收点 |
|---|---|---|---|---|
| ① | 持仓周期表 | `hedge_open_cycle` + `attempt.cycle_id` + 聚合按周期拆分 + 历史回填 + **预留 `close_cycle` 关闭接口（供功能③调用；不做自动归零观察、不接线触发逻辑）** | HIGH_RISK（改记账口径；纯记账无实盘下单） | 平仓再开仓不混算；起始持仓时间正确；`close_cycle` 契约（幂等/单向/事务）单测通过（设计 v1 §8 用例 1/2/2b/3/4/5/5b/8） |
| ② | 费率/利息统计 | 持仓行 `accrued_funding`/`borrow_interest`/`net_pnl` 从占位「暂无」变周期窗口真值（自 ledger-flow 现算） | 中（资金/PnL 展示，纯读） | 三列真值；覆盖率不足降级显示 |
| ③a | 平仓记录 | `hedge_open_cycle_close_log` + 平仓完成/人工核实时写结算日志 + 历史仓位页接真数据 | 低（结构先行） | 开/平时间、费率、利息与均价真值；开/平滑点按两腿真实成交加权均价、卖减买、四位百分比记录 |
| ③b | 平仓执行 | 真实平仓（实盘双腿、滑点校验、还债、资金移动），**平仓完成调用①预留的 `close_cycle`（close_reason='auto_close'）** | 最高（实盘资金操作，需 Human 授权 + 最严评审） | 平仓事件精确关周期；close_log 补全平单均价/滑点 |

**状态（2026-08-06）**：① ② ③a ③b **全部开发完成并实盘验证，Human 2026-08-05 验收通过**；
**sonnet5 综合评审完成（review-1+review-2 合一）：首轮 REWORK（1 处真实 P0：平仓 fresh preflight
余额校验方向未反转）→ DeepSeek 一行修复 + 2 条 live 回归测试 → sonnet5 复评 ACCEPT（受控还原
验证测试真实钉住缺陷，`2026-08-hedge-position-cycle-v1-review-sonnet5.handoff.md` 复评节）**。
修复链全部生效：现货卖出路由重设计（普通账户+划转+复检+USDT 回流）、划转前统一余额检查、close
完成判定重构（running→其他状态先走合约无仓核实）、前端提前量检测、任务卡开平仓标记、导航徽标
联动、历史页补全（现货均价/成交量/成交额/滑点 %）。持仓表口径：只显示未平仓周期
（`closed_at_us IS NULL` 过滤）。本地数量口径保持现状（方案 B 已回退，整改方案待 Human 定）。
四任务交付 + 全部修复已提交 `97ecb7f`（评审 ACCEPT 后）。**2026-08-06 数据清理**
（三库记录清空、保留表结构，备份 bak-clean-*，交易所全平）——**从头测试起点**。服务其后已
恢复运行（当前由 Human 手动前台启动，2026-08-08 00:13 重启，见 `PROJECT_STATE.md` Live Risks
的 launchd 条目）。前端「假数据 · 预览」探针已删除。close 已实盘使用（2026-08-07 SNXXUSDT
全平），`close_gate` 默认开（`store.py` `DEFAULT 1`）。挂账 follow-up：本地数量与交易所脱节（X/Y/Z 方案待定）、
close_log 利息 ≈U（价格源注入 service 层）。（「MUUUSDT 现货别名配对」已随 `SPOT_SYMBOL_MAP`
解决：MUUSDT→MUBUSDT 与 MUUUSDT→MUUBUSDT 是两个并存的真实合约，均已收录。）

**2026-08-12 滑点口径收口**：历史仓位开/平滑点改为对应阶段两腿真实成交数量加权均价的
`(卖价 - 买价) / min(两腿均价) × 100`，卖价高于买价为正，四位小数；缺腿保持 `NULL/—`，
不再使用 preflight `est_price`。JSTUSDT 历史行已在备份后补录为 `0.2316/-0.2192`。

设计权威：`docs/planning/hedge-open-position-cycle-v1.md`（周期设计 v1；五项口径 + 关闭触发决策已拍板——**不做自动归零观察，关闭由功能三平仓任务触发、人工核实作纠偏**）。
开发文稿：`docs/planning/hedge-open-cycle-stage2-cycle-dev.md`（功能 ①）、
`docs/planning/hedge-open-cycle-stage3-stats-dev.md`（功能 ②）。
前置检查：功能 ② 开始前核对 ledger-flow 覆盖率（`interest_coverage_start/end`、
`income_coverage_start/end`），历史窗口未拉全时统计会偏小。

## Current Focus

The display-honesty family closed on 2026-08-07. Current priorities and every
item's acceptance state live in `PROJECT_STATE.md` (Live Risks / Open
Follow-ups).

- **F4 — RESOLVED 2026-08-07** (`184d76e` + `44ab175`): the position table no
  longer claims "exchange has no position" when account reads fail; the
  contract carries `private_account.unavailable_sources`, and a single red
  title line replaces the per-row fabrication. Live-verified 2026-08-08. The
  archive `49-` smoke gate it referenced is void (see below).
- **Task-card pause reasons — RESOLVED 2026-08-07** (`dd0b3e3`): the frontend
  reads `pause_reason_zh` directly (the backend actually has 11
  `PAUSE_REASON_*` values, not the 7 originally recorded); the orphan
  `HEDGE_PAUSE_REASON_LABELS` table was deleted.
- **The read-only smoke checklist gate — VOIDED by Human 2026-08-07.** It was
  never executed while live opens, closes, and transfers repeatedly happened
  around it; live activation no longer has this prerequisite. The checklist
  remains in `archive/2026-07-31-hedge-task-lifecycle-v1` file `49-` as
  history only, with no force.
- **Current priorities** (detail in `PROJECT_STATE.md`): 1000x multiplier
  leg-quantity conversion — a money-path change awaiting Human authorization;
  server deployment with a systemd unit (launchd is unrepaired by decision
  2026-08-15; local stays manual foreground). (Q2 flow-log display
  cap and Q3 task-card error hint were fixed 2026-08-08.)
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
- Optional F-A hardening if its accepted-risk reopen condition is met: reject
  or pause a smooth card whose create-time frozen preflight was never complete.
- Position mismatch monitoring beyond the current merged table (the single-leg
  and drift markers themselves were fixed 2026-08-07 — partial-imbalance
  tolerance `_EXPOSURE_IMBALANCE_TOLERANCE`, drift sums both accounts;
  `d7057e3` et al.).
- Funding, commission, rebate, and borrow-interest accounting.
