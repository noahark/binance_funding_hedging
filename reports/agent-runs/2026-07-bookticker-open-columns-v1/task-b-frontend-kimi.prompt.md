# Task B Frontend Implementation Prompt — Kimi

你是本 stage 的 Task B 实现者，负责把已 committed/frozen 的
`opening_quotes` contract 接入前端机会表，并完成用户要求的表格压缩。请在
严格文件边界内实现、运行 self-check、写 implementation report；不要启动
其他模型。

## Identity And Mode

- Adapter: `kimi`
- Provider identity: `moonshot_kimi`
- Required model alias: `kimi-code/kimi-for-coding`
- Skill: `senior_developer`
- Mode: write code inside allowed files only
- Stage role: Task B implementer；不得担任本 Task B review-1，也不得担任本
  stage review-2。

## Repository And Git Boundary

- Repository: `/Users/ark/Desktop/ai code/funding_hedging`
- Required branch: `stage/2026-07-bookticker-open-columns-v1`
- Task A committed contract SHA:
  `01fca8cda4e3ce37ab2b976f1ca060ed9da109a0`

先确认 branch，并确认 Task A SHA 是当前 HEAD 的 ancestor。Bookkeeper 可能在
它之后只提交 status/handoff/prompt，因此不要要求 HEAD 必须恰好等于 Task A
SHA。若 branch 不匹配或该 SHA 不可达，停止报告 blocker；不得自行切 branch、
merge、rebase、commit、push 或改写 history。保留所有已有 stage/backend/
Harness/API evidence，不清理无关文件。

## Required Read Set

必须亲自读取：

1. `AGENTS.md`
2. `agents/developer-discipline.md`
3. `docs/model-adapters.md` 的 Kimi 与 Session receipt 段
4. `reports/agent-runs/2026-07-bookticker-open-columns-v1/00-task.md`
5. `reports/agent-runs/2026-07-bookticker-open-columns-v1/10-design.md`
6. `reports/agent-runs/2026-07-bookticker-open-columns-v1/11-adr.md`
7. `reports/agent-runs/2026-07-bookticker-open-columns-v1/12-development-breakdown.md`
8. `reports/agent-runs/2026-07-bookticker-open-columns-v1/14-design-review-reconciliation.md`
9. `reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation-task-a.md`
10. `reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json`
11. `schemas/api/public-market/snapshot.schema.json` 的 `opening_quotes` 定义
12. `frontend/index.html`
13. `frontend/self-check.js`
14. `frontend/fixture/public-market-snapshot.json`

Task A contract 已冻结，前端不得重解释或重算 `*_spread_pct`。

## Allowed Writes

只允许修改或创建：

- `frontend/index.html`
- `frontend/self-check.js`
- `frontend/fixture/public-market-snapshot.json`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation-task-b.md`

## Forbidden Writes And Semantics

- 不修改任何 backend、schema、backend fixture、canonical docs、Harness、
  status/handoff/ACTIVE、API samples、Task A report 或 `60-test-output.txt`。
- 不改 selected-symbol click HTTP 行为、drawer、private panels、privacy toggle、
  filters、row ordering、auto-refresh timer 或 backend contract validation。
- 不删除 frontend `REQUIRED_ROW_FIELDS` 中的 `ui_flags`、`route_class` 等既有
  校验；只删除默认表中的提示列展示。
- 不新增交易按钮、业务计算、WebSocket、额外 fetch、第三方库或配置。
- 不使用 JavaScript `Number` 重新计算 opening spread，不将 backend
  `*_spread_pct` 再乘 100。

## Final 12-Column Contract

最终表头顺序和 index 必须固定：

0. 标的
1. 借贷状态 / 资产
2. 资金费率
3. 结算时间
4. 日费率
5. 年化 24h
6. 年化 7D
7. 年化 30D
8. 日净收益
9. 标记价格 / 指数价格
10. 正向开单
11. 反向开单

必须保持恰好 12 个 `<th>` / 每行 12 个 `<td>` / empty-state
`colspan="12"`。系统性更新 `self-check.js` 中所有 numeric cell index；不要只
改新增断言。

## Required UI Changes

### Header and duplicate-column cleanup

- “净收益”改为“日净收益”；`net_daily_yield` sort-basis 文案同步为
  “日净收益优先”。
- 删除默认表“提示标记” `<th>` 和 row cell；底层 `ui_flags` 必须继续校验。
- 删除独立“负费率状态”展示列；把其行感知状态 badge 移入合并列上行。

### Combined `借贷状态 / 资产` cell

- 上行：保留现有 `badgeForNegativeFundingStatus(row)` 的完整行感知语义和
  既有中文状态，包括已验证可借、`可借 0(已借完)`、杠杆交易对未列出、
  资产不可借、有利率但可借性未探测、限速预算未探测、需私有验证等。
- 已有 max-borrowable 数量与约合 USDT 从日净收益 cell 迁到这里；不得在
  两处重复。
- 下行：`badgeForAssetTag(row.asset_tag)`，例如
  `CRYPTO(加密货币)`；保持 CRYPTO/METAL/BSTOCK/UNKNOWN 既有语义。
- 排列必须是状态在上、资产在下，共占一格。

### `日净收益` cell

- 保留净百分比、borrow-rate source badge 和符合既有条件的日借币成本。
- 删除 max-borrowable/约合 USDT 的重复子行。

### `正向开单` and `反向开单`

- 正向上方：`合约买一` = `futures_bid_price`；下方：`现货卖一` =
  `spot_ask_price`；右侧 = `forward_spread_pct`。
- 反向上方：`现货买一` = `spot_bid_price`；下方：`合约卖一` =
  `futures_ask_price`；右侧 = `reverse_spread_pct`。
- 使用 price stack + 右侧 percentage 的单元格布局。正 spread 用 success，
  负 spread 用 danger，零/缺失 muted。
- 使用独立 opening-spread formatter：后端字符串已经是 percentage point，
  只保证固定两位、正值 `+`、负值 `-`、零 `0.00%`。禁止调用/复用
  `formatFundingRate`，锁定：
  - `"-0.04" -> "-0.04%"`，不得 `"-4%"`
  - `"0.04" -> "+0.04%"`
  - `"0.00" -> "0.00%"`，不得 `"0%"`

### Degradation and operator wording

- `opening_quotes` 不加入 `REQUIRED_ROW_FIELDS`。
- 整体缺失、`stale`、`unavailable`：两个 opening cells 显示 `—`，不白屏。
- `incomplete`：展示仍存在的单腿价格；每个方向只根据自己的两个 operand
  决定 spread 是否 `—`，不得连带清空另一个有效方向。
- title/说明明确：“约 60 秒刷新；失败时 last-good 最多约两个周期（默认
  120 秒）后停用；非成交保证”，并解释 stale/incomplete。
- `updated_at` 可用于 title/freshness 提示，但不要新增定时器或业务 age
  计算。

## Fixture And Self-Check

- `frontend/fixture/public-market-snapshot.json` 补 `opening_quotes`，至少覆盖
  fresh、incomplete、stale/unavailable，供静态预览。
- 注意 `frontend/self-check.js` 实际读取的是
  `backend/tests/fixtures/private-account-v1-design.json`；该 backend fixture 是
  forbidden。必须在 self-check 内存中给 `designFixture.rows` 注入
  `opening_quotes` 状态，沿用已有 annualized/value 注入模式。
- self-check 必须覆盖：
  - exact 12 headers、12 cells、`colspan=12`
  - 无提示标记/独立负费率状态列
  - 合并 cell 状态在上、资产在下、借贷额度只出现一次
  - 正反向四个腿的上下顺序与字段映射
  - 独立 formatter 三个锁定向量和禁止 100 倍误用
  - missing/stale/unavailable/incomplete 降级及双方向独立
  - 既有 filters、click、keyboard、drawer、private panels、refresh 全部继续过

## Required Tests

运行：

```text
node frontend/self-check.js
git diff --check
```

不得修改 `60-test-output.txt`。在 implementation report 中记录 command、
exit code 和完整关键结果；bookkeeper 会独立重跑 frontend + full backend。

## Required Report

写入 `20-implementation-task-b.md`，包含：

- implementer/provider/model/skill；
- exact changed files；
- layout/formatter/degradation 决策；
- 测试命令与结果；
- task boundary/ADR deviations（没有写 None）；
- remaining work/findings；
- git status（不得 commit）；
- 以下 footer。

Session ID 按 `docs/model-adapters.md`：用 Kimi workspace 的准确
`session_<uuid>` 目录，并以 `state.json.workDir/lastPrompt` 交叉验证；不得只按
最新 mtime 猜。保留 provider-native `session_` 前缀。

最终响应也必须以同一 footer 结束：

```text
当前 Session ID: <provider-native session_<uuid> | unavailable (reason)>
Session ID 来源: <cli_output | transcript_path | unavailable>
原始输出路径: reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation-task-b.md
本地北京时间: YYYY-MM-DD HH:MM:SS CST
下一步模型: codex_bookkeeper
下一步任务: 核对 Task B diff/file boundary，独立重跑 frontend 与 full backend 并创建 Task B evidence commit
```

时间必须来自本地 `date`。不得输出 token、cookie、credential、expanded env
或 global diagnostic log。完成后停止，交回 codex_bookkeeper；不要执行
review、commit、push 或 merge。
