# Task Handoff: frontend-position-balance-display-v1

## Source Report (author-only; immutable after task end)

- task_id: `frontend-position-balance-display-v1`
- role: `Implementer`
- target model: `grok` (provider `xai`)
- stage_id: `2026-08-03-hedge-status-account-refresh-v1`
- created_at: `2026-08-03 20:59:18 CST`
- base_sha: `65bdd8176d7e9757f97886a902932e999919a441`
- delivery_sha: `pending`（Implementer 在包含本件的唯一 delivery commit 之前创建；Bookkeeper 在 delivery commit 后用 `git rev-parse` 解析实际 SHA 写入 `status.json` 与同文件核验块，不回填本字段）

### 任务背景与实际修改范围

实现 Human 已验收的 v4.1 §9 最小前端展示调整。只改三个已决定的显示点，消费已验证后端 positions 字段（`spot_balance` / `spot_balance_value_usdt` / `unified_balance` / `unified_balance_value_usdt`）。不改后端、API 契约、snapshot 夹具、刷新请求/定时器、自动轮询、缓存、订单、借贷写入、Start gate、凭证、服务或部署。

实际改动（均在 Allowed Files 内）：

- `frontend/index.html`：
  1. **抵押额度徽标（§9.1）**：`renderCollateralCapBadge` 从市场表标的单元格移到同一行「借贷状态 / 资产」单元格；仍只一个徽标；注释同步为新位置；判定/颜色/title/排序/过滤/按钮语义不变。
  2. **对冲开单持仓双行余额（§9.2）**：`formatPositionAccountSideLine` + `renderPositionDualBalanceCell` 将「现货余额」列改为两行 `现货: <amount> ≈ <value,2位> U` / `杠杆: …`；仅读 positions row 四字段；amount 缺失 → `—`；有 amount 无 value → `≈ — U`；真 0 显示 0；隐私同时遮蔽 amount 与估值；`cross_margin_borrowed` 仍只在「全仓借款」列。
  3. **时间位置（§9.3）**：`#account-asset-updated-at` 移到标题区 `title-block`，替换固定副标题「行情公开 · 账户需 key 私有只读」；`refresh-meta` 只保留倒计时；新增 `#private-pm-source-time` 于「私有账户」标题下，PM capability 三态（隐藏 / 未就绪 / 北京时间）；PM 行不再出现在概览 body。
- `frontend/self-check.js`：注册新 DOM；抵押额度断言改为借贷状态列（标的列零徽标）；METAL 徽章中性断言不误伤同格 cap danger；PM 时间断言改为标题元素；新增双行余额完整/单侧缺失/value 缺失/真零/未就绪/隐私/不从 snapshot 拼接覆盖；标题区 DOM 位置断言；回归既有 cache-refresh 与 whitelist。
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/frontend-position-balance-display-v1.self-check.txt`：离线 self-check 原始输出。
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/status.json`：仅 `current_task.state` `dispatched` → `reported`。
- 本交接件。

### 关键设计取舍

- **估值后缀 `U`**：按 §9.2 文案使用紧凑 `≈ xx.xx U`，与余额卡片的 `≈ xx USDT` 区分，不重算价格（`formatUsdt2` 仅展示舍入）。
- **不从 snapshot 拼余额**：self-check 故意改 snapshot 余额后重渲染，确认仍用 positions 行字段。
- **更新缓存语义未动**：`onCacheRefresh` / 手动刷新 GET / 零新增定时器路径未改。

### 未完成事项

无阻塞。本任务范围（前端三处展示 + 离线 self-check）已完成。Review-1/review-2、merge、部署、实盘/网络不在本任务授权内。

### 命令与结果（离线，无真实 key/网络/服务）

- `node frontend/self-check.js` → 全部自检通过（含新增 `frontend-position-balance-display-v1` 块与既有回归）。
- 证据：`reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/frontend-position-balance-display-v1.self-check.txt`。

### 仓库内证据路径

- self-check 输出：`reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/frontend-position-balance-display-v1.self-check.txt`
- 本交接件：`reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/frontend-position-balance-display-v1.handoff.md`

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/frontend-position-balance-display-v1.handoff.md`
  2. `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/status.json`
  3. `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/frontend-position-balance-display-v1.dispatch.md`
  4. `docs/planning/hedge-status-account-refresh-v4.md`（§9）
  5. `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/frontend-position-balance-display-v1.self-check.txt`
  6. `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/backend-position-balance-display-v1.handoff.md`
- 执行：Bookkeeper 核验本任务（`base_sha`/`delivery_sha`、status revision、handoff 同文件 SHA-256 边界、引用证据路径与可复现 `node frontend/self-check.js`），并把本任务推进为 `verified` 或拒收。
- 关卡：Bookkeeper 通过则解析 `delivery_sha`；后端+前端均 verified 后按 stage 路由进入跨 provider review（Grok/xai 实现的 review-1 须用不同 provider）。
- 不能假设的事实：本任务未做实盘/网络/凭证/部署；未改后端；`delivery_sha` 在本件为 `pending`；无自动轮询/SSE/WebSocket 变更。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: frontend-position-balance-display-v1
执行结果: completed（完成）
结果摘要: v4.1§9 前端三处：抵押额度徽标迁至借贷状态列；持仓现货余额双行消费四字段；账户时间进标题区、PM 时间在私有账户标题下。离线 self-check 全过。未改后端/刷新/订单。
产物: [frontend/index.html, frontend/self-check.js, reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/status.json, reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/frontend-position-balance-display-v1.handoff.md, reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/frontend-position-balance-display-v1.self-check.txt]
检查结果: [pass 抵押额度已满/未知仅在借贷状态列，标的列无徽标；三态/title/零排序过滤按钮影响保留, pass 现货余额列两行精确消费 spot/unified amount+value_usdt；独立缺失/≈—U/真零/隐私/未就绪；借款列不变；不从 snapshot 拼, pass account-asset-updated-at 在标题区且替换固定副标题；refresh-meta 仅倒计时；PM 三态在私有账户标题下、概览无重复, pass 更新缓存 POST/手动刷新 GET/loading/完成后重读与零自动轮询语义未变, pass node frontend/self-check.js 全部通过并存盘；无服务/网络/凭证/实盘]
阻塞项: [none]
本地北京时间: 2026-08-03 20:59:18 CST
下一步模型: codex（Bookkeeper，只读核验本任务）
下一步任务: 读取：reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/frontend-position-balance-display-v1.handoff.md、reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/status.json、reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/frontend-position-balance-display-v1.dispatch.md、docs/planning/hedge-status-account-refresh-v4.md、reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/frontend-position-balance-display-v1.self-check.txt、reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/backend-position-balance-display-v1.handoff.md；执行：Bookkeeper 核验 base_sha/delivery_sha、同文件 handoff SHA-256 边界、引用证据与可复现 node frontend/self-check.js，并把本任务推进为 verified 或拒收；关卡：Codex 核验通过且前后端均 verified 后，由 Human 决定进入跨 provider review-1（Grok/xai 实现须不同 provider）
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- verified_at: `2026-08-03 21:06:23 CST`
- source_sha256: `c7b443a3b8701a540851be95c3a5b02e0ea258afe0de8774c694fbcb1e1f0b9f` (`7948` bytes before the sole marker)
- status_revision_checked: `10`; source task was `reported` and only its permitted `dispatched` → `reported` transition occurred.
- base_sha verified: `65bdd8176d7e9757f97886a902932e999919a441`; delivery_sha resolved: `7f965f8282c989625a80dfde0be96b0e008cafab`; the base is an ancestor of delivery.
- scope verified: delivery changes exactly `frontend/index.html`, `frontend/self-check.js`, this task's handoff/self-check evidence, and its permitted `status.json` transition. No backend, API contract, fixture, refresh path, order, credential, deployment, or live-operation file changed.
- implementation verified: the collateral-cap badge moved once into the existing borrow-status/asset cell; the positions balance cell consumes only the four delivered row fields and leaves `cross_margin_borrowed` in its own column; aggregate and PM source times occupy their approved unique DOM locations while their existing time semantics remain intact.
- evidence verified: `node frontend/self-check.js` was independently rerun; it ended `全部自检通过`, and `node frontend/self-check.js | diff -u reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/frontend-position-balance-display-v1.self-check.txt -` returned exact equality. The check is offline and made no network, credential, service, or live-operation call.
- result: verified. Backend and frontend v4.1 deliveries are both verified; a single provider-isolated Review-1 packet now covers their complete fixed product range before Review-2.
