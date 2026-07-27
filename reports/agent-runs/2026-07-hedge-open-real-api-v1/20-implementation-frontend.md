# Task B 实现报告 — Frontend Hedge Open Real API v1

实现者：Kimi（frontend owner，按 `task-B-kimi.prompt.md` 执行）。
分支：`stage/2026-07-hedge-open-real-api-v1`（HEAD `66ef35f`，实现期间未 commit）。
范围：仅已批准 Hedge Open Real API v1 的中文前端增量展示。未改 backend、
status.json、70-handoff.md、docs 或任何其他路径；未 git commit；未调用/转派任何
其他模型会话。

## 1. 实际改动文件

- `frontend/index.html`（+159 行）
- `frontend/self-check.js`（+179 行）

说明：工作区中 `backend/hedge_open_tasks/domain.py` 存在非本会话产生的改动
（Task A 后端实现的并行在途工作），本会话未读取需求之外也未改动任何
`backend/**` 文件；该文件不在本报告 diff 范围内。

## 2. 实现内容（对照 prompt 五项要求）

### 2.1 增量展示（要求 1）

- 任务卡（`renderHedgeTaskCard`）新增一行计数：`已调度 X 组 · 已受理 Y 组 ·
  连续提交失败 Z / 暂停阈值 T`，对应 §3.4 的 `scheduled_attempt_count` /
  `accepted_pair_count` / `consecutive_submission_failures` /
  `failure_pause_threshold`；`pause_reason` 存在时追加一行
  `暂停原因：<中文标签>`（`consecutive_submission_failure` →「连续提交失败达到
  阈值」，未知取值原样展示）。旧 `leg_exposure`、旧 success/fail 行保持不变
  （advisory 兼容）。
- 固定基础数量（单次币量）、计划次数（目标次数）、有效 `q_common`（公共网格量）、
  任务状态徽标、Start/executor 状态徽标均为既有渲染，保持原样。
- 新增「尝试时间线」区块（开单任务页内 `#hedge-attempt-list`）：每条 attempt
  渲染第 N 组、方向（正向/反向）、`pair_outcome` 徽标（已受理/已确认失败/
  查询中，未知原样）、关联任务币种（task_id → 任务卡 coin，解析不到则原样
  task_id）、`ts`、`q_common`、残差 `residual`，以及两腿各自的
  `order_id` / `client_order_id` / `status` / `cumulative_base_qty` /
  `cumulative_quote_amt` / `avg_price`，现货腿另带 `fee_amount`/`fee_asset`。
- 数据源为既有 `GET /api/hedge-open-logs?limit=100`（路由表不变，§3.4 称
  per-attempt 文档「surfaced under the existing logs/fills read」）。
  `extractHedgeAttempts` 对信封宽容：扫描 `attempts` / `fills` / `logs` /
  `entries` 数组，条目自身或其 `payload` 为 attempt 形状（含 `attempt_seq` /
  `pair_outcome` / `spot` / `perp` 对象之一）即采纳，其余日志条目忽略；
  不发明任何字段。
- 加载时机：进入开单任务视图时拉取一次并先用缓存渲染一帧；任务变更
  （`mutateHedgeTask`）后随任务列表/持仓一起重拉。无新增前端定时器。

### 2.2 Decimal 原样与优雅降级（要求 2）

- 新增 `hedgeText(v)`：十进制字符串/计数 `String(v)` 原样展示，不经过
  JavaScript 浮点；`null`/`undefined`/`''` 降级为 `—`。所有新字段（任务计数、
  两腿全部数值、residual、q_common、订单号、时间戳）均走该路径。
- 旧字段（`single_amount`、旧 `q_common` 行、持仓表）沿用既有
  `formatMockPrice(hedgeNum(...))`，未改动。
- 降级验证：完全不含 real-api-v1 新字段的旧任务文档渲染为逐项 `—`、无
  `暂停原因` 行、不抛错；attempt 缺 `perp` 腿或腿内字段缺失时该腿/该项渲染
  `—`；logs 503 显示错误横幅、保留缓存、不崩溃（均有自检断言）。

### 2.3 self-check 扩展（要求 3）

- mock：新增 `hedgeLogsGetResponse` 响应槽与 `/api/hedge-open-logs` GET 分支
  （默认 200 空 logs）；`mockHedgeTask` 默认字段补齐 §3.4 五个新字段；新增
  `mockHedgeAttempt` 工厂（Decimal 全为字符串，含 fee/avg_price/residual）。
- DOM ID registry：新增 `hedge-attempt-list`、`hedge-attempts-error`。
- fetch 同源白名单新增 `^/api/hedge-open-logs\?`，方法白名单新增 logs GET。
- 新增断言块 84/85/86：任务卡新字段渲染与旧文档降级；时间线取数路由、两腿
  字段逐字（断言 `0.36210000`、`120.70000000`、`0.00000100`、`-0.00010000`
  等字面量，任何浮点重排都会失败）、payload 内嵌兼容、非 attempt 日志忽略、
  缺腿降级、关联任务币种标签；空态与 503 错误横幅。
- 既有断言块编号「84. 开单 API 全部同源」顺延为 87，内容未改。

### 2.4 无 Binance 直连（要求 4）

- 前端未新增任何签名/调度/外部请求逻辑；最终无泄漏证明块（fetch 同源白名单、
  零 Binance/外域、定时器白名单 60000/1000/2000、localStorage 仅隐私键）
  全部通过。执行徽标仍为只读投影，UI 无任何可暗示前端自行开启 live 的入口。

### 2.5 节拍事实仅作文案（要求 5）

- 未实现 scheduler/smooth/WebSocket。时间线只渲染后端权威数据；immediate
  「每卡每秒一组、多卡可同秒」仅体现在既有横幅文案与数据展示上。

## 3. 实际执行命令与原样结果摘要

```text
$ node frontend/self-check.js
...（前置 borrow/市场块全部 [PASS]）
[PASS] 开单操作列两输入两按钮、平滑开单 disabled+下一轮、立即开单可点、推荐方向按费率符号高亮
[PASS] 立即开单创建：POST 冻结 body、创建后重拉 ?status=all、非法输入零 POST、invalid_field 行内报错、smooth 拒绝
[PASS] insufficient_balance 弹框两路径：正向 USDT / 反向现货 stage-1 文案逐字、不建任务
[PASS] 任务生命周期：pause/start/fill-once/fill-all/delete 冻结路由 + 状态推进 + 软删除筛选与导航徽标
[PASS] exposure_alert 渲染 + 累计失败 >3 终止 + 按钮 disabled 矩阵 + invalid_state 409 就近报错
[PASS] 持仓表从 GET /api/hedge-open-positions 渲染（§3.4 字段逐字）+ 空态
[PASS] 执行徽标：executor_mode disabled→dry-run / live + start_gate Start 状态
[PASS] 任务卡 real-api-v1 新字段：调度/受理/连续失败/阈值渲染 + 暂停原因 + 旧文档逐项降级 —
[PASS] attempt 时间线：logs 取数 + 两腿字段逐字渲染 + payload 内嵌兼容 + 非 attempt 忽略 + 缺腿降级
[PASS] attempt 时间线降级：空态 + 503 错误横幅 + 恢复
[PASS] 开单 API 全部同源、零跨域 fetch
[PASS] fetch 同源白名单（含开单 §3 路由）、零 Binance/外域、零新任务定时器、localStorage 白名单（仅隐私键）

全部自检通过
```

退出码 0。

## 4. mock / DOM 覆盖

- mock 路由：`/api/hedge-open-logs`（GET，默认 200 `{logs: [], next_cursor: null}`）。
- mock 工厂：`mockHedgeTask`（+5 个 §3.4 字段）、`mockHedgeAttempt`（§3.4 全字段）。
- DOM registry：`hedge-attempt-list`、`hedge-attempts-error`。
- 白名单：fetch 同源 + 方法白名单均覆盖 logs GET。

## 5. 字段缺失时的降级行为

| 缺失项 | 行为 |
| --- | --- |
| 任务五个新计数/阈值字段 | 逐项渲染 `—`，无暂停原因行 |
| `pause_reason` | 不渲染该行 |
| `pair_outcome` 为 null | 徽标 `—`（muted） |
| `pair_outcome` 未知取值 | 原样文本，muted 徽标 |
| `spot`/`perp` 腿缺失 | 该腿整行字段渲染 `—` |
| 腿内字段缺失（如 `order_id`、fee） | 该项 `—`；fee 缺失则整段省略 |
| `task_id` 无法关联任务 | 原样 task_id 文本 |
| logs 503 | 错误横幅 + 保留上次缓存，不崩溃 |
| logs 为空 | 「暂无尝试记录」空态 |

## 6. 未解决问题 / 风险

- §3.4 冻结了 per-attempt 字段名，但「surfaced under the existing logs/fills
  read」的信封形状未逐字节冻结。前端因此对信封做了宽容提取（四个候选数组 +
  payload 内嵌）。若 Task A 实际落地形状不同（如独立键名或不同分页参数），
  时间线会退化为空态而非报错；集成阶段需按 A 的真实落库形状复核
  `extractHedgeAttempts` 的候选键。
- attempt 文档无 `task_id` 时无法关联任务卡，只能原样展示；冻结字段表未含
  `task_id`，此处按 logs 条目级 `task_id`（既有 `log_to_doc` 已有该字段）
  关联，属读取既有字段而非发明。
- 旧 `leg_exposure` 文案「任务已暂停」与新合同「单腿敞口不阻断调度」存在语义
  张力；§3.4 明确旧字段保留为 advisory，本任务未改该既有文案，是否修订由
  review 裁定。
- `?limit=100` 只取第一页；超出 100 条的更早 attempt 不展示（无「加载更多」），
  如需分页为后续增量。

## 7. git diff 概要

```text
 frontend/index.html    | 159 ++++++++++++++++++++++++++++++++++++++++++-
 frontend/self-check.js | 179 ++++++++++++++++++++++++++++++++++++++++++++++++-
 2 files changed, 334 insertions(+), 4 deletions(-)
```

（工作区另有 `backend/hedge_open_tasks/domain.py` 的非本会话改动，不属于
Task B。）未 commit；按 dispatch 要求停止，等待 bookkeeper。

当前 Session ID: unavailable（Kimi CLI 未向本会话暴露 provider-native Session ID）
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/20-implementation-frontend.md
本地北京时间: 2026-07-23 20:50:26 CST
下一步模型: bookkeeper
下一步任务: collect Task B report, reconcile frontend/backend integration, and run integration evidence
