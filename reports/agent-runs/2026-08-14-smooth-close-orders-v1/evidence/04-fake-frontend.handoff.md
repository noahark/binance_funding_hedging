# Task Handoff: 04-fake-frontend

## Source Report (author-only; immutable after task end)

- task_id: 04-fake-frontend
- role: Implementer
- target_model: grok-4.6 / provider xai
- stage_id: 2026-08-14-smooth-close-orders-v1
- created_at: 2026-08-14 16:23:40 CST
- base_sha: 56e0dba17f863d3c2af7f9c45ae0bb81018c5196
- delivery_sha: pending
- status_revision: 6
- parent_head_at_start: 57662af9e1158923ea7eaf7e8021ac80401b410b

### Scope

实现平滑平仓 V1 的前端 fake 样式预览。唯一权威是 `reports/agent-runs/2026-08-14-smooth-close-orders-v1/04-fake-frontend-spec.md`。只改 `frontend/index.html`，并创建本 handoff。未改后端、未新增产品文件、未启动服务、未创建任务、未下单。

### What changed

1. **私有持仓平仓列**：在既有「立即平仓」按钮前插入 `[平滑平仓] [0.05] %`，与单次平仓币量 / 计划尝试次数并存。立即平仓按钮的 class、文案、`data-hedge-close` 与提交路径未改。
2. **确认弹框**：`data-hedge-close-smooth` 走独立 pending kind `hedge_close_style_preview`。回显币种、方向、单次平仓币量、计划尝试次数、滑点阈值，并写明比较的是当前方向平仓率。确认后只弹出「样式预览、不执行」，不调用建卡 / 启动 / 暂停 / 删除 / 成交1次 / 闸门。
3. **五种静态样式卡**：插在开单任务页 `hedge-tasks-panel`、真实 `hedge-task-list` **之外**（避免污染既有 self-check 对列表 innerHTML 的断言）。形态为：未备料/已暂停（启动可点）、备料中（启动文案「备料中…」且启动/暂停/删除/成交1次全灰）、备料失败/已暂停（既有中文原因「平仓现货余额检查/划转失败…」）、运行中已备料（动态盘口 + 成交1次可点）、立即平仓对照（备料状态「每轮实时校验」，无盘口块）。平滑卡无「立即成交所有」。
4. **运行中平滑卡盘口块**：两列标题为正向/反向**平仓率**，不含「开单率」。正向列高亮并标「本任务判定」，价格组为现货买一 + 合约卖一；反向列为合约买一 + 现货卖一。含带符号百分比、两腿一档覆盖与 80% 达标、轮次、倒计时、等待原因「等待当前方向平仓率严格大于阈值」、固化阈值 0.05%。

可点 fake 控件用 `data-hedge-close-smooth` / `data-smooth-close-style-preview`，不用 `data-hedge-action` 或 `data-hedge-task-id`，因此不会进入既有任务动作绑定。阈值框 Enter 只 `preventDefault`，无新 `setInterval`/`setTimeout`，无外部依赖。

### Checks

```text
node frontend/self-check.js
```

结果：进程退出码 0，输出以「全部自检通过」结束。该套件覆盖立即平仓真实 POST、平滑开单真卡、借币/还款/划转、闸门与同源白名单；本次 diff 为纯新增行（222 insertions / 0 deletions），既有立即开单、平滑开单、立即平仓、借币、还款、划转路径无删改。

### Not done (by spec)

- 不接后端、不冻结 API 字段名。
- 不做真实输入校验与提交。
- 不做动画、响应式或主题。
- 未 push、未 merge、未切分支。

### Required Reading for the Next Task

- 读取路径及顺序：`reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/04-fake-frontend.handoff.md`；`reports/agent-runs/2026-08-14-smooth-close-orders-v1/status.json`；`frontend/index.html`；`reports/agent-runs/2026-08-14-smooth-close-orders-v1/04-fake-frontend-spec.md`
- 执行：Bookkeeper 核验本 handoff 与当前 stage 分支交付提交，解析 `delivery_sha`，将任务标为 verified
- 关卡：核验通过后由 Human 做页面验收；验收通过后再启动后端 P1，不得把本次静态样式当成可执行平仓
- 不能假设的事实：后端平滑平仓尚未实现；本次卡片是静态 HTML，不进 `state.hedgeTasks`、不随筛选变化、不会发出任何任务动作请求

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: 04-fake-frontend
执行结果: completed（完成）
结果摘要: 仅改 frontend/index.html：持仓列加平滑平仓与 0.05 阈值，确认回显平仓率且确认后不发请求；开单任务页插入五张静态样式卡（未备料/备料中全灰/备料失败/运行中盘口/立即对照）。无新定时器、无新依赖。
产物: [frontend/index.html, reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/04-fake-frontend.handoff.md]
检查结果: [pass 身份 revision 分支与 HEAD 匹配；pass 只改 Allowed Files；pass node frontend/self-check.js 全部自检通过；pass fake 走独立 pending 且确认后零请求；pass 立即开单/平滑开单/立即平仓/借币/还款/划转路径零删改；pass 无新定时器与外部依赖；pass 五形态与平仓语义盘口（无开单率、无立即成交所有）；pass 当前 stage 分支本地提交且未 push/merge]
阻塞项: [none]
本地北京时间: 2026-08-14 16:23:40 CST
下一步模型: gemini-3.1-pro（Bookkeeper，核验本次实现回执）
下一步任务: 读取：reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/04-fake-frontend.handoff.md；reports/agent-runs/2026-08-14-smooth-close-orders-v1/status.json；frontend/index.html；reports/agent-runs/2026-08-14-smooth-close-orders-v1/04-fake-frontend-spec.md；执行：核验 handoff 与交付提交并解析 delivery_sha；关卡：核验通过后由 Human 做页面验收，通过后再启动后端 P1。
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)
- source_sha256: f5a5742eed074e62e4302f47e804c5c9ad9a6303faf870868a3a589ba9160010
- 核验时间: 2026-08-14 16:35:00 CST
- 核对 status revision: 6
- 依据: Human 页面验收已通过。Planner 复核边界确认：只改了 frontend/index.html 与自身 handoff，纯新增无删除，新增代码中 fetch、XMLHttpRequest、setInterval、/api/ 出现次数均为 0，未 push。按 AGENTS.md §8 判定本任务为 LOW_RISK（前端样式预览零真实请求，无后端改动及任何安全性副作用），不需要 Review-1 + Review-2。
- 后续状态: 验证通过（verified）。LOW_RISK 评审豁免，已推进至 05-backend-p1 的 dispatch。
