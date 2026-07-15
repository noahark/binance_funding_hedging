# Task B Frontend Pre-Commit Fix 1 — Resume Kimi

继续当前 stage 的 Task B 前端实现。优先在原实现 Session
`session_727145b3-694a-4467-8277-60a65dd1b1c5` 中执行；这是 evidence commit
前的 scope-contained 修正，不是 formal review，也不增加 stage rework count。

## Identity And Boundary

- Adapter/provider/model：`kimi` / `moonshot_kimi` /
  `kimi-code/kimi-for-coding`
- Branch 必须仍为 `stage/2026-07-bookticker-open-columns-v1`。
- 当前 HEAD 必须仍为
  `dff8b4785f43cd9fb82b7fab6214bc8c7d98ac88`；保留现有未提交 Task B
  工作树，不 reset、不 checkout、不清理。
- 只允许继续修改：
  - `frontend/index.html`
  - `frontend/self-check.js`
  - `frontend/fixture/public-market-snapshot.json`
  - `reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation-task-b.md`
- 不修改 backend/schema/backend fixture/Harness/status/handoff/ACTIVE/
  `60-test-output.txt`，不 commit、不 push、不启动 reviewer。

先重读原 Task B prompt、`10-design.md` D8/D9、
`12-development-breakdown.md` Task B 与当前四个允许文件，然后完成以下最小修正。

## Required Fixes

### F1 — 已探测额度不得被 borrow-rate source 隐藏

当前 `maxBorrowableSubline(row)` 先用 `row.borrow_rate_source == null` 返回，
会隐藏 `borrow_validation.portfolio_account.max_borrowable` 已有真实证据。例如当前
backend design fixture 的 CUSDT 同时满足 `borrow_rate_source=null` 和
`max_borrowable=<AMOUNT>`。冻结设计要求“已探测额度时”在合并列显示额度；
`borrow_rate_source` 只门控日净收益格的日借币成本子行，不门控 max-borrowable。

- 删除 max-borrowable 对 `borrow_rate_source` 的依赖。
- 仅根据 `borrow_validation.portfolio_account.max_borrowable != null` 决定额度子行。
- 保持 null 不显示、合法 `0` 显示 `可借 0(已借完)`、约合 USDT 既有行为。
- self-check 增加 `borrow_rate_source=null` 但 max-borrowable 已探测时仍显示额度的
  确定性断言。

### F2 — 浏览器预览 fixture 不得给无现货腿资产伪造 fresh spot quote

`frontend/fixture/public-market-snapshot.json` 的 XAUUSDT 是
`PERP_ONLY_EXCLUDED`、`spot.exists=false`、`spot.symbol=null`，当前却写成
`opening_quotes.status=fresh` 并伪造 spot bid/ask。Task A 冻结语义明确：无现货腿
时为 `incomplete`，保留真实 futures price，spot price 与两个 spread 为 null，
不得猜替代现货资产。

- 把 XAUUSDT preview `opening_quotes` 改为 `incomplete`。
- `spot_bid_price`、`spot_ask_price`、`forward_spread_pct`、
  `reverse_spread_pct` 为 null。
- 可保留该行 futures bid/ask 与非 null `updated_at`，与 usable incomplete
  contract 一致。
- 检查其他 preview row 的 route/spot leg/status 不存在同类矛盾。

### F3 — 补齐冻结的 self-check，而不是只在报告中声称覆盖

当前 self-check 已数 12 个 header，但没有严格锁定 header 顺序、每个 rendered
data row 恰好 12 个 `<td>`、empty-state `colspan="12"`；合并列测试也没有真正
断言状态位于资产之前、额度只出现一次且不在日净收益格。

补充确定性断言：

1. 抽取市场表 `<th>` 文本并与冻结的 12 项数组逐项、逐序完全相等，不只是
   `includes`。
2. 对默认渲染的每个 data row 计数，断言恰好 12 个 `<td>`。
3. 行为或源码断言 empty/blocked state 使用 `colspan="12"`；至少实际触发一次
   无匹配行 empty state，并恢复 fixture，不能破坏后续测试。
4. 合并格中状态 badge 的位置必须早于资产 badge；已探测额度只在 index 1
   出现，在 index 8 日净收益格不得出现。
5. `incomplete` 的无效方向明确断言百分比为 `—` 且现存腿继续显示；不能只
   断言“不含 ±0.04%”。有效方向继续显示。
6. 删除 self-check 中对 `designFixture.rows[4].opening_quotes` 的重复赋值。

可顺手让 `classForOpeningSpread` 对 null/empty/invalid formatter 输入都返回
`muted`，避免 invalid dash 获得 positive 色；若修改，补一条断言。不得扩大范围。

### F4 — 更正 implementation report

在 `20-implementation-task-b.md` 追加清晰的 `Pre-Commit Fix 1` 记录并更正原先
过度声明：列出 F1-F3 的实际修改、最终测试数量/结果、当前 git status。
`Remaining Work / Findings` 只能在这些缺口确实修复后写“formal review pending”；
不要删除原始 Session receipt。

## Required Commands

运行并记录：

```text
node frontend/self-check.js
python3 -m json.tool frontend/fixture/public-market-snapshot.json
git diff --check
git status --short
```

若任一失败，留在允许文件内修复；不得改 backend 绕过。最终仍不 commit。

## Required Final Footer

从实际 Kimi Session receipt 获取 ID/source；若确实复用原 session，应仍为
`session_727145b3-694a-4467-8277-60a65dd1b1c5`，否则如实记录新 provider-native
ID 并说明来源。最终响应和更新后的 report 以以下字段结束：

```text
当前 Session ID: <provider-native session_<uuid> | unavailable (reason)>
Session ID 来源: <cli_output | transcript_path | unavailable>
原始输出路径: reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation-task-b.md
本地北京时间: YYYY-MM-DD HH:MM:SS CST
下一步模型: codex_bookkeeper
下一步任务: 复核 Pre-Commit Fix 1、重跑 frontend/full backend 并创建 Task B evidence commit
```

时间来自本地 `date`。不得输出 token、cookie、credential 或 expanded env。完成后
停止并交回 bookkeeper。
