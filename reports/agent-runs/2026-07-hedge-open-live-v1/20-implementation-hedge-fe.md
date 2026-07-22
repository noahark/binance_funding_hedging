# 实现报告 — hedge-fe：前端接入真实 hedge-open API（stage 2026-07-hedge-open-live-v1，第一轮）

实现者：Kimi（`kimi-code/kimi-for-coding`，前端域）。
输入依据：`task-hedge-fe-kimi.prompt.md`、`10-design.md`（§10/§11）、
`12-development-breakdown.md`（§3 冻结 API 契约逐字、§5 前端契约、§7 风险点）、
stage-1 基线 `frontend/index.html` + `frontend/self-check.js`。
文件边界：仅 `frontend/index.html`、`frontend/self-check.js`，未触碰任何其他文件
（工作区中的 `backend/**` 改动属于并行任务 hedge-be，非本任务产物）。

## 改动摘要

把 stage-1 开单 fake 引擎（localStorage 任务/账户、假盘口漂移、1s 成交 tick、
前端余额模拟与持仓聚合）整体替换为对 12-breakdown §3 冻结 API 的 `fetch` 调用；
全部 UI（开单列、任务卡、状态筛选、软删除、持仓表、余额不足弹框）保留并改由
后端文档驱动。所有新逻辑留在第一个 `<script>` 块内。

## 交付项 ↔ 代码位置（frontend/index.html）

- §3 API 访问层 `hedgeApi`（镜像 borrowApi 纪律，错误携带 `errorCode`+完整 payload）：
  第一个 script 块「对冲开单（2026-07-hedge-open-live-v1）」段。
- 立即开单创建 `submitHedgeOpen` → `POST /api/hedge-open-tasks`，body 逐字
  `{coin, direction, mode:'immediate', single_amount, target_n}`；
  `insufficient_balance` 按 direction 弹 stage-1 文案 `正向开单 USDT 余额不足` /
  `反向开单现货余额不足`（正文携带后端 `required/available`）；`invalid_field` /
  `invalid_state` 行内报错；非法输入本地拒绝零 POST；`smooth` 入口拒绝。
- 任务动作 `pauseHedgeTask / startHedgeTask / deleteHedgeTask / hedgeFillOnceNow /
  hedgeFillAll` → `POST /api/hedge-open-tasks/<id>/{pause|start|delete|fill-once|fill-all}`，
  共用 `mutateHedgeTask`（打补丁 + 重拉列表与持仓；409 `invalid_state` 就近中文提示）。
- 任务列表 `loadHedgeTasks` → `GET /api/hedge-open-tasks?status=all`（deleted 仅
  all/deleted 返回；五档筛选与计数在前端做，沿用 stage-1 筛选栏 UI）。
- 持仓表 `loadHedgePositions` → `GET /api/hedge-open-positions`，
  `renderHedgePositionsSection` 按 §3.4 Position JSON 字段逐字渲染
  （`position_qty/spot_avg/perp_avg/open_basis_rate/price_pnl/accrued_funding/
  borrow_interest/net_pnl`），嵌入私有面板；标题去掉「本地模拟」。
- 执行徽标 `loadHedgeSettings` / `renderHedgeExecutionStatus` →
  `GET /api/hedge-open-settings`，显示 `executor_mode`（disabled→dry-run / live）
  + `start_gate`（Start 已开启/未开启）+ 调度间隔；新增 `hedge-execution-badge` /
  `hedge-execution-detail` / `hedge-tasks-error` 元素。
- `平滑开单` 按钮保留但 `disabled`，附 `下一轮` 提示（`renderHedgeOpCell`）。
- 任务卡：保留方向/模式/状态徽标、已成功/失败计数、`exposure_alert` 敞口行
  （`leg_exposure` 逐字）、`fail_count>3` 终止行、按钮 disabled 矩阵；
  新增 `q_common` 展示；移除假盘口/开单率行。
- 刷新策略：进入开单视图拉 tasks/positions/settings；快照 60s tick 仅在开单视图
  激活时重拉 tasks/positions（镜像借币 §3.11c，不是执行时钟）；前端无任何开单定时器。
- 文案：市场表头 title、开单任务页副标题/横幅更新为「后端持久化、浏览器不调度/
  不模拟/不签名/不请求 Binance」；移除全部 fake/本地模拟表述与死代码
  （RNG、假盘口、fake 账户、localStorage 持久化、`computeHedgePositions`、
  `hedgeEngineTick` 及 `.hedge-book-lines` CSS）。

## self-check（frontend/self-check.js）

- 新增 §3 路由 mock（同源）：`POST/GET /api/hedge-open-tasks(?status=)`、
  `POST /api/hedge-open-tasks/<id>/{pause|start|delete|fill-once|fill-all}`、
  `GET /api/hedge-open-settings`、`GET /api/hedge-open-positions`；
  默认种子（空列表/空持仓/disabled 设置）保证启动加载 200；`mockHedgeTask`
  携带 §3.2 冻结字段名（含 `q_common/position_side_mode/leg_exposure`）。
- 断言块 77–84 重写为 API 版：操作列（平滑 disabled+下一轮、立即可点、推荐高亮）、
  创建 POST 冻结 body + 创建后重拉 `?status=all` + 非法输入零 POST +
  `invalid_field` 行内 + smooth 拒绝、`insufficient_balance` 弹框两路径逐字、
  五动作冻结路由 + 状态推进 + 软删除筛选与导航徽标、`exposure_alert` 渲染 +
  累计失败 >3 终止 + 按钮矩阵 + `invalid_state` 409 就近报错、持仓从 positions
  端点渲染（含 `accrued_funding` 逐字）+ 空态、执行徽标 dry-run/live + Start、
  开单 API 零跨域。
- 块 76 白名单更新：fetch 同源白名单加入 §3 开单路由、方法白名单（列表/设置/
  持仓 GET，创建/动作 POST）、localStorage 白名单收紧为仅隐私键；定时器白名单
  不变（60000/1000/2000，开单零前端定时器）。
- 既有全部 `[PASS]`（市场表、抽屉、借币任务/日志/调度/执行控制）原样保留并通过。

## 契约符合性自查

- 端点路径、请求体字段（`coin/direction/mode/single_amount/target_n`）、Task
  字段名（含 round-2 新增三字段）、错误码三分支（`insufficient_balance` 按
  direction 两文案逐字 / `invalid_field` / `invalid_state`）均按 §3 逐字消费。✓
- 持仓使用 §3.4 `accrued_funding`（非 stage-1 fake 的 `funding_accrued`）。✓
- Fill JSON（§3.3）本轮前端不直接消费（任务卡计数取 Task 文档，持仓取 positions
  端点），无字段名假设。✓
- 无新依赖、无第二个 `<script>` 块、无真实外部网络请求（self-check 全 mock）。✓
- 无 websocket/平滑门控（下一轮）、无 repay/close、无新的前端定时器。✓

## 自测结果

```
node frontend/self-check.js
exit=0，108 个 [PASS]，0 个 [FAIL]，结尾「全部自检通过」
```

完整输出已追加至 `reports/agent-runs/2026-07-hedge-open-live-v1/60-test-output.txt`
（hedge-be pytest 输出之后，带 `===== hedge-fe (Kimi) 自测 =====` 分隔头）。

## 已知限制

- 列表固定拉 `?status=all` 前端筛选（为保留 stage-1 五档筛选计数 UI）；任务量
  大时可改为逐筛选拉取，契约已支持。
- `single_amount/target_n` 以 number 上送（沿 stage-1 冻结形状）；若后端要求十进制
  字符串，属契约澄清项，需在 review 中确认。
- 持仓/任务为显示级缓存：快照 60s tick 才后台刷新（视图激活时），动作后即时重拉；
  非实时，本轮无 ws 属预期。
- `invalid_state` 409 提示为通用中文文案（后端错误体无 detail 字段）。
- hedge-be 的 `backend/**` 与 fixtures 未由本任务验证；联调以 §3 契约为缝。

当前 Session ID: 4a912c95-c1cb-4cb7-82f5-e21357b341c0
Session ID 来源: transcript_path（kimi-code session 目录路径）
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-v1/60-test-output.txt
本地北京时间: 2026-07-23 00:53:44 CST
下一步模型: bookkeeper（claude-opus-4-8）收证据 → review-1 Claude-GLM（人类操作员派发）
下一步任务: bookkeeper 收证据、R4 diff 核对、串行 commit、算指纹、调度 review-1
