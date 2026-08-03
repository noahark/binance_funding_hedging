# Task Handoff: frontend-cache-refresh-v1

## Source Report (author-only; immutable after task end)

- task_id: `frontend-cache-refresh-v1`
- role: `Implementer`
- target model: `grok` (provider `xai`)
- stage_id: `2026-08-03-hedge-status-account-refresh-v1`
- created_at: `2026-08-03 19:42:02 CST`
- base_sha: `dab29be5e9ce3dfca47101615225775d8a1c7954`
- delivery_sha: `pending`（Implementer 在包含本件的唯一 delivery commit 之前创建；Bookkeeper 在 delivery commit 后用 `git rev-parse` 解析实际 SHA 写入 `status.json` 与同文件核验块，不回填本字段）

### 任务背景与实际修改范围

实现已批准设计 `docs/planning/hedge-status-account-refresh-v4.md` 的前端接线，只消费已交付后端 `8b624f7` 的 JSON（`POST /api/public-market/cache-refresh` 的 `{published, account_panels}` 与 snapshot / hedge-open-positions 的固定五 key `source_checked_at`）。不修改后端、契约、任务状态钩子或刷新调度。Human 已明确授权 Grok 执行此前端任务。

实际改动（均在 Allowed Files 内）：

- `frontend/index.html`：
  - 右上角在「手动刷新」旁新增「更新缓存」按钮；点击禁用并显示 loading，`POST /api/public-market/cache-refresh`；按 200 complete / partial / not_attempted、published=false / HTTP 失败、202 queued 如实提示；仅 complete/partial/not_attempted 在结果处理后手动依次调用既有 `loadApi()` 与 `loadHedgePositions()`；202 与失败不新增轮询/SSE/WebSocket/自动刷新；「手动刷新」仍只走 GET `loadApi()`。
  - 原私有面板副标题聚合时间移至 `#refresh-countdown` 下一行 `#account-asset-updated-at`，文案为「账户资产更新时间」（读 `checked_at`，回退 `valuation.priced_at`）；私有账户不可读提示仅留在面板 body，与右上角不复用同一 DOM 文案职责。
  - 账户区域显示 `source_checked_at` 北京时间（`Asia/Shanghai`）：统一/现货单源；对冲持仓取 UM+统一+现货最早时间，任一 null 显示未就绪且不伪造；PM capability 三态（不存在隐藏 / 存在但 null 未就绪 / 有时间显示）；`price_map` 不占账户标题。
- `frontend/fixture/public-market-snapshot.json`：为 `private_account` 增加固定五 key `source_checked_at` 样例。
- `frontend/self-check.js`：注册新 DOM、mock `POST /api/public-market/cache-refresh`、注入 design fixture 的五 key、更新原副标题断言、新增 complete/partial/not_attempted/失败/202、北京时间、缺源、PM 三态、私有未读分离与零自动轮询覆盖；同源白名单允许 cache-refresh POST。
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/frontend-cache-refresh-v1.self-check.txt`：离线 self-check 原始输出。
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/status.json`：仅把本任务 `current_task.state` 从 `dispatched` 改为 `reported`。
- 本交接件。

### 关键设计取舍（供核验）

- **只消费已交付后端 JSON**：POST 响应仅有 `published` + `account_panels`（无失败源列表）；partial 提示「部分账户或估值源未更新」并以页面 `source_checked_at` 为证据，不编造脱敏源名。
- **无任务状态前端联动**：不为 running→非 running 新增轮询/SSE/自动重拉；状态钩子已在后端，本任务不接。
- **PM capability 启发式**：前端无独立 capability 标志；以 `pm_account.source` / 核心 PM 字段 / `source_checked_at.pm_account` 判定可见性，覆盖隐藏 / 未就绪 / 有时间三态；self-check 显式构造三种 fixture。
- **聚合时间 vs 源时间**：右上角旧聚合字段与账户区「数据源更新时间」文案分离；多源缺任一源绝不取剩余源最早时间冒充完整。

### 未完成事项

无阻塞。本任务范围（前端按钮、时间展示、fixture、离线 self-check）已完成。Review-1/review-2、merge、部署、实盘/网络操作均不在本任务授权内。

### 命令与结果（离线，无真实 key/网络/服务）

- `node frontend/self-check.js` → 全部自检通过（含新增 `frontend-cache-refresh-v1` 块与既有回归）。
- 证据：`reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/frontend-cache-refresh-v1.self-check.txt`。

### 仓库内证据路径

- self-check 输出：`reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/frontend-cache-refresh-v1.self-check.txt`
- 本交接件：`reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/frontend-cache-refresh-v1.handoff.md`

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/frontend-cache-refresh-v1.handoff.md`
  2. `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/status.json`
  3. `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/frontend-cache-refresh-v1.dispatch.md`
  4. `docs/planning/hedge-status-account-refresh-v4.md`
  5. `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/frontend-cache-refresh-v1.self-check.txt`
- 执行：Bookkeeper 核验本任务（`base_sha`/`delivery_sha`、status revision、handoff 同文件 SHA-256 边界、引用证据路径与可复现离线 `node frontend/self-check.js`），并把本任务推进为 `verified` 或拒收。
- 关卡：Bookkeeper 通过则解析 `delivery_sha` 并按 stage 路由进入跨 provider review-1；未通过则在同文件追加拒收 `Bookkeeper Verification` 块。
- 不能假设的事实：本任务未做实盘/网络/凭证/部署；未改后端；`delivery_sha` 在本件为 `pending`；任务状态变更不触发前端自动刷新（按设计）。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: frontend-cache-refresh-v1
执行结果: completed（完成）
结果摘要: 前端接入更新缓存：POST cache-refresh 按钮与 complete/partial/not_attempted/失败/202 如实提示；右上角聚合账户时间；账户区 source_checked_at 北京时间与缺源/PM 三态；离线 self-check 全过。无自动轮询。
产物: [frontend/index.html, frontend/self-check.js, frontend/fixture/public-market-snapshot.json, reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/status.json, reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/frontend-cache-refresh-v1.handoff.md, reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/frontend-cache-refresh-v1.self-check.txt]
检查结果: [pass 更新缓存按钮 loading/恢复；POST cache-refresh；手动刷新仍 GET, pass complete 提示并 loadApi+loadHedgePositions；partial/not_attempted/失败/202 不夸大完整更新且无自动轮询, pass 右上角账户资产更新时间与面板内私有未读分离, pass source_checked_at 五 key 北京时间；单源/多源最早/缺源未就绪/PM 三态正确；price_map 不占账户标题, pass fixture 含五 key；离线 node frontend/self-check.js 全部通过（含新增块与回归）, pass 未改后端/契约/状态；未启服务/网络/凭证/实盘]
阻塞项: [none]
本地北京时间: 2026-08-03 19:42:02 CST
下一步模型: codex（Bookkeeper，只读核验本任务）
下一步任务: 读取：reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/frontend-cache-refresh-v1.handoff.md、reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/status.json、reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/frontend-cache-refresh-v1.dispatch.md、docs/planning/hedge-status-account-refresh-v4.md、reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/frontend-cache-refresh-v1.self-check.txt；执行：Bookkeeper 核验 base_sha/delivery_sha、同文件 handoff SHA-256 边界、引用证据与可复现 node frontend/self-check.js，并把本任务推进为 verified 或拒收；关卡：Codex 核验通过后由 Human 决定是否进入跨 provider review-1（Grok/xai 实现的 review-1 须用不同 provider）
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->
