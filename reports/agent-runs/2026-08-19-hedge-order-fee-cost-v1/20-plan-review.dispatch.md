# 成交手续费冻价成本 V1 计划评审 dispatch — Opus 5 / Anthropic

## Identity

- task_id: `20-plan-review`
- target_role: `Reviewer`
- target_model: `opus5`
- provider: `anthropic`
- status_revision: 1
- required_skill: `agents/skills/reality-checker.md`

## Goal

对 `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/10-design.md` 进行独立、跨 provider 的只读**计划评审**（HIGH_RISK 账务含义、成交写入与展示）。
评估该设计是否以最小修改、自洽语义、fail-closed 安全与完备的测试用例达成产品目标，确认已拍板口径（D1–D10）无遗漏、无膨胀，并判断是否可推进至后端与前端实现拆包。

本任务为只读计划评审，不触碰 `rework_count`。verdict 回到 Bookkeeper (`gemini-3.7-flash` / `agy`) 以便在 ACCEPT 后准备实现 dispatch。

## 隔离披露

- 设计作者：Grok 4.6 / xAI（provider `xai`）。
- Bookkeeper：Gemini 3.7 Flash / Google（provider `google`，窗口 `agy`）。
- 本 Reviewer：Opus 5 / Anthropic（provider `anthropic`，窗口 `claude` / `claude-review`；备选 Codex / OpenAI）。三方跨 provider 隔离成立。

## Allowed Files

Reviewer 完全只读，除下面唯一确定性 handoff 文件外零写入：

- **唯一允许新建（create-only）**：
  `reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/20-plan-review.handoff.md`
- **Bookkeeper 预检（2026-08-19 23:02 CST）**：
  `test ! -e reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/20-plan-review.handoff.md` → **ABSENT**，create-only 权威成立。
  该路径在开始前不存在；若开始时已存在即任务失败。

Reviewer 不得修改任何代码、测试、既有文档、`status.json`、`PROJECT_STATE.md`、`ACTIVE.json`；严禁 commit/merge/push、严禁下单、严禁重启服务、严禁部署、严禁访问真实凭据与 live DB。

handoff 必须遵守 `agents/roles.md` 的 Task Handoff Evidence Contract：包含 Source Report、Required Reading for the Next Task、Human Brief / Console Receipt Source，并在末尾保留 `<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->` 标记。

## Inputs

按下列顺序读取：

1. `AGENTS.md`
2. 本 dispatch：`reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/20-plan-review.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. 本 stage `status.json`：`reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/status.json`
6. `agents/roles.md`（重点阅读 `Shared Rules`、`Task Handoff Evidence Contract`、`Reviewer` 节）
7. `agents/skills/reality-checker.md`（required_skill）
8. Stage intake：`reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/00-intake.md`
9. Stage 设计正文：`reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/10-design.md`
10. 相关代码及既有契约参考（只读）：
    - `backend/store.py`（表结构与 `hedge_open_leg` 既有字段、`aggregate_positions` 与 `close_log`）
    - `backend/services/hedge_open_live_service.py`（订单终态回写与查询流）
    - `backend/services/hedge_open_live_client.py`（币安 PAPI/现货/合约客户端接口）
    - `backend/domain/positions.py`（持仓聚合计算）
    - `frontend/index.html` 与 `frontend/self-check.js`（持仓表与历史仓位展示及自动化测试）
    - `docs/api/public-market-contract.md` 与 `docs/product/PRD.md`（既有契约与产品规范）

## Acceptance Checks

Reviewer 须逐项核查以下内容并在 handoff 中给出明确检查结果（pass / fail / contested）：

1. **已拍板口径（D1–D10）合规性**：
   - 四列冻价设计（`fee_bnb_qty`, `fee_bnb_price`, `fee_other_qty`, `fee_other_asset`）是否满足多币种与冻价需求？
   - 停写旧 `fee_amount` / `fee_asset`、不删列、不回补历史、不修改 `hedge_open_fill` 的最小范围原则是否成立？
   - 持仓表只汇总 open 腿手续费、历史仓位汇总 open+close 腿手续费的边界是否清晰？
   - 净盈亏公式本轮不动（不扣减手续费）、缺数/缺价显示「—」不当 0 的原则是否严格恪守？
2. **交易所数据语义与接口契约**：
   - 币安成交历史接口选择（现货 `GET /api/v3/myTrades`、统一账户杠杆 `GET /papi/v1/margin/myTrades`、合约 `GET /papi/v1/um/userTrades`）及过滤 `orderId` 分组求和逻辑是否准确？
   - 成交明细中 `commission` 与 `commissionAsset` 标量结构、单订单多笔成交多币种求和逻辑是否自洽？
   - 客户端只读白名单及权重开销评估是否合理？
3. **BNB 取价顺序与 Fail-Closed 保证**：
   - 写入时取价顺序（进程内 `price_map["BNBUSDT"]` → 公开拉取 `BNBUSDT` → 缺价留空）是否合理？
   - **关键安全红线**：手续费接口拉取失败或 BNB 缺价时，是否严格禁止阻塞订单成交落库及 `FILLED` 终态流转？
4. **两包拆分（后端 `claude_glm` + 前端 `kimi`）可行性**：
   - API 字段命名与契约（如 `trading_fee_usdt`, `fee_bnb_qty`, `trading_fee_incomplete`）是否明确冻结，能完全防止前端猜测？
   - 历史仓位 `close_log` 字段落库与展示契约是否完整？
5. **测试夹具与验收策略**：
   - 离线测试夹具是否覆盖 6 种场景（纯 BNB、纯 USDT、BNB+USDT 混合、非 USDT 本币折 U、成交历史调用失败、缺 BNB 价格）？
   - 是否包含 `node frontend/self-check.js` 对应的前端渲染断言与变异测试？
6. **Handoff 与任务回执规范**：
   - 产物是否为唯一指定 handoff 路径，包含 `BOOKKEEPER_APPEND_ONLY` 标记？
   - 控制台回执严格符合 `AGENTS.md` §7，评审结论为 `ACCEPT（接受）` 或 `REWORK（返工）`？

## Stop

完成后停止，由 Bookkeeper (`gemini-3.7-flash` / `agy`) 核验。Reviewer 除指定 handoff 外零写入。

控制台严格按 `AGENTS.md` §7 输出 review 版 `[TASK_RESULT v2]`：
```text
[TASK_RESULT v2]
任务 ID: 20-plan-review
执行结果: completed（完成）
结果摘要: <不超过 300 个总字符>
产物: [reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/20-plan-review.handoff.md]
检查结果: [<各项 pass / fail / contested>]
评审结论: ACCEPT（接受） | REWORK（返工）
问题记录: <path | none>
修复要求: <path | none>
阻塞项: [<none or blockers>]
本地北京时间: <YYYY-MM-DD HH:MM:SS CST>
下一步模型: gemini-3.7-flash（Bookkeeper，agy 窗口）
下一步任务: 读取：reports/agent-runs/2026-08-19-hedge-order-fee-cost-v1/evidence/20-plan-review.handoff.md；执行：核验计划评审结论并准备后端实现 dispatch；关卡：Human 批准进入实现阶段
[/TASK_RESULT]
```
闭合标记 `[/TASK_RESULT]` 后不得有任何额外文字。
