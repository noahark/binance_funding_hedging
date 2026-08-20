# 成交手续费冻价成本 V1 第二轮计划评审 dispatch — Opus 5 / Anthropic

## Identity

- task_id: `21-plan-review-r2`
- target_role: `Reviewer`
- target_model: `opus5`
- provider: `anthropic`
- status_revision: 4
- required_skill: `agents/skills/reality-checker.md`

## Goal

对 Planner（Grok 4.6 / xAI）修订后的 `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/10-design.md`（r2 修订版，commit `1f7612e`）执行第二次独立、跨 provider 的只读**计划评审**（HIGH_RISK 账务含义、历史回补、成交写入与展示）。

重点核查第一轮评审交接件（`evidence/20-plan-review.handoff.md` 勘误 1 与勘误 2）所列的必改清单（R1–R5）与约束项（O1–O5）在 r2 中是否已完备、安全、无歧义地落实，确认是否具备拆分后端（`claude_glm`）与前端（`kimi`）实现包的条件。

本任务为交付前只读计划评审，按 `AGENTS.md` §8 与 `agents/roles.md`，不触碰 `rework_count`。verdict 回到 Bookkeeper (`gemini-3.7-flash` / `agy`)。

## 隔离披露

- 设计作者：Grok 4.6 / xAI（provider `xai`）。
- Bookkeeper：Gemini 3.7 Flash / Google（provider `google`，窗口 `agy`）。
- 本 Reviewer：Opus 5 / Anthropic（provider `anthropic`，窗口 `claude` / `claude-review`；备选 Codex / OpenAI）。三方跨 provider 隔离成立。

## Allowed Files

Reviewer 完全只读，除下面唯一确定性 handoff 文件外零写入：

- **唯一允许新建（create-only）**：
  `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/21-plan-review-r2.handoff.md`
- **Bookkeeper 预检（2026-08-20 00:20 CST）**：
  `test ! -e reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/21-plan-review-r2.handoff.md` → **ABSENT**，create-only 权威成立。
  该路径在开始前不存在；若开始时已存在即任务失败。

Reviewer 不得修改任何代码、测试、既有文档、`status.json`、`PROJECT_STATE.md`、`ACTIVE.json`；严禁 commit/merge/push、严禁下单、严禁重启服务、严禁部署、严禁访问真实凭据与 live DB。

handoff 必须遵守 `agents/roles.md` 的 Task Handoff Evidence Contract：包含 Source Report、Required Reading for the Next Task、Human Brief / Console Receipt Source，并在末尾保留 `<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->` 标记。

## Inputs

按下列顺序读取：

1. `AGENTS.md`
2. 本 dispatch：`reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/21-plan-review-r2.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. 本 stage `status.json`：`reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/status.json`
6. `agents/roles.md`（重点阅读 `Shared Rules`、`Task Handoff Evidence Contract`、`Reviewer` 节）
7. `agents/skills/reality-checker.md`（required_skill）
8. 第一轮计划评审交接件：`reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/20-plan-review.handoff.md`（含勘误 1、2 与 Bookkeeper 复核记录）
9. Stage 设计正文（r2 修订版）：`reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/10-design.md`
10. Stage intake：`reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/00-intake.md`
11. 真实存在的代码及既有契约参考（只读）：
    - `backend/hedge_open_tasks/store.py`（表结构、`hedge_open_leg` 字段、`aggregate_positions`、`insert_close_log`、`_cycle_leg_basis_locked` 均价算法）
    - `backend/hedge_open_tasks/service.py`（订单终态回写与 drain 流程、`get_close_logs` 查询）
    - `backend/services/hedge_open_live_client.py`（客户端只读白名单及签名请求封装）
    - `backend/services/live_hedge_executor.py`（`avgPrice` 现状核验）
    - `backend/services/hedge_preflight_provider.py`（`price_map` 缓存与时效常量 `_CACHE_MAX_AGE_PRICE`）
    - `frontend/index.html` 与 `frontend/self-check.js`（持仓表、历史表结构与测试）
    - `docs/api/public-market-contract.md` 与 `docs/product/PRD.md`（既有契约与产品规范）

## Acceptance Checks

Reviewer 须逐项核查以下内容并在 handoff 中给出明确检查结果（pass / fail / contested）：

1. **R1 历史回补方案（D9 & §4.3）**：
   - 回补范围是否明确（本地 `exchange_status=FILLED` 且 `order_id` 非空的全部开平仓腿；跳过已写腿）？
   - 触发方式是否安全（独立脚本 `scripts/backfill-leg-fees.py`，须 Human 明确授权，不挂在下单/平仓/worker/启动流）？
   - 控速与断点机制是否完备（签名 GET ≤ 1次/秒，遇到 429/418 立即停并保存断点，有 running 对冲任务时拒绝启动或降速）？
   - 回补冻价口径是否合理（取成交时刻附近 `BNBUSDT` 1 分钟 K 线收盘价，不使用当前现价，取不到则价格留空）？
   - 是否明确不回写已关闭的 `close_log` 旧行（避免给一次性历史表增加 UPDATE 风险）？
2. **R2 `close_log` 不全载体（D11 & §5.2）**：
   - 是否新增 `trading_fee_incomplete`（INTEGER 0/1）列并冻死后端字段名？
   - 是否明确「任一参与腿缺手续费构成量 → `incomplete=1` 且 `trading_fee_usdt=NULL`」，彻底消除半截数冒充完整成本风险？
   - 是否写死 `insert_close_log` 前参与腿必须已完成手续费查询？
3. **R3 折 U 均价口径与禁止 `avg_price`（D5 & §5.1）**：
   - 本币手续费折 U 是否严格写死为 `cumulative_quote_amt ÷ cumulative_base_qty`？
   - 是否显式禁用了现货腿基本为空的 `hedge_open_leg.avg_price` 列？
   - 是否限定仅当 `fee_other_asset ∈ {USDT, 该腿 base 资产}` 时折算，其他资产判定为不全？
4. **R4 交易所接口时间窗与不可全覆盖认知（§2.2）**：
   - 现货 `/api/v3/myTrades`、杠杆 `/papi/v1/margin/myTrades`、合约 `/papi/v1/um/userTrades` 三端点参数与时间窗描述是否符合官方规范？
   - 是否明确合约端点无 `orderId` 参数、按时间窗拉取后本地过滤的规则？
   - 是否承认历史回补可能无法做到 100% 覆盖并保留了 D10 兜底？
5. **R5 & O1–O5 写入时序与契约冻结**：
   - 实时路径每腿至多 1 次 GET，失败不重试、不进轮询（平滑任务 20 次成交至多 40 次 GET）；
   - 手续费查询放在订单终态事务提交之后，且同时覆盖 inline 派发与 drain 查询两个写入站点（§4.1）；
   - 新增费用字段纳入 money-zero 防抹零名单（§4.2）；
   - 实时路径明确为「写库时冻价」，最大偏离受 `price_map` 300 秒时效约束（D4）；
   - 历史仓位空表 `colspan` 明确从 16 改 17；`close_log` 字段名在后端先定死（`trading_fee_usdt`, `trading_fee_incomplete`, `fee_bnb_qty`）；
   - dispatch Inputs 路径已全部修正为仓内真实路径。
6. **拆包准备就绪度**：
   - 后端（`claude_glm`）与前端（`kimi`）的职责分工与先后依赖是否清晰？
   - API 键名与前端展示口径是否完全冻结？
7. **Handoff 与任务回执规范**：
   - 产物是否为唯一指定 handoff 路径，包含 `BOOKKEEPER_APPEND_ONLY` 标记？
   - 控制台回执严格符合 `AGENTS.md` §7，评审结论为 `ACCEPT（接受）` 或 `REWORK（返工）`？

## Stop

完成后停止，由 Bookkeeper (`gemini-3.7-flash` / `agy`) 核验。Reviewer 除指定 handoff 外零写入。

控制台严格按 `AGENTS.md` §7 输出 review 版 `[TASK_RESULT v2]`：
```text
[TASK_RESULT v2]
任务 ID: 21-plan-review-r2
执行结果: completed（完成）
结果摘要: <不超过 300 个总字符>
产物: [reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/21-plan-review-r2.handoff.md]
检查结果: [<各项 pass / fail / contested>]
评审结论: ACCEPT（接受） | REWORK（返工）
问题记录: <path | none>
修复要求: <path | none>
阻塞项: [<none or blockers>]
本地北京时间: <YYYY-MM-DD HH:MM:SS CST>
下一步模型: gemini-3.7-flash（Bookkeeper，agy 窗口）
下一步任务: 读取：reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/21-plan-review-r2.handoff.md；执行：核验第二轮计划评审结论；关卡：若 ACCEPT 且经 Human 批准后，拆分后端与前端实现 dispatch
[/TASK_RESULT]
```
闭合标记 `[/TASK_RESULT]` 后不得有任何额外文字。
