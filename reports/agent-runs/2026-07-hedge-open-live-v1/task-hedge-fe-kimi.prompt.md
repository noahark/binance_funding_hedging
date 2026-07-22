===== DISPATCH RECEIPT =====
status: done
target_model: kimi/kimi-code-for-coding
adapter_cmd: kimi --model kimi-code/kimi-for-coding -p "$(cat reports/agent-runs/2026-07-hedge-open-live-v1/task-hedge-fe-kimi.prompt.md)"
executor: human_operator
started_at: 2026-07-22T23:45:00+08:00
completed_at: 2026-07-23T01:05:00+08:00
session_id: unavailable:Kimi CLI runtime did not expose a provider-native session ID; bookkeeper recorded the human-operator execution window
outputs: reports/agent-runs/2026-07-hedge-open-live-v1/20-implementation-hedge-fe.md; reports/agent-runs/2026-07-hedge-open-live-v1/60-test-output.txt
next_dispatch: bookkeeper R4 reconciliation (R4-fix-1) + evidence commit + review-1 (Claude-GLM)
===== END RECEIPT =====

[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于
   claude-glm -p、kimi -p、codex exec、grok）。需要其他模型时，输出
   ESCALATED 及原因并停止。
2. 禁止编造未实际执行的命令结果或未实际读取的文件内容；你写下的每一条
   执行记录都必须对应你本会话内真实发生的动作。
3. 你的实现依据只能是本 prompt 列出的 raw artifact 路径与你自己实际读取的
   文件。

# 任务 hedge-fe：前端接入真实 hedge-open API（stage 2026-07-hedge-open-live-v1，第一轮）

你是 hedge-fe 唯一实现者（Kimi，前端域）。把 stage 1 的**开单 fake 引擎**替换为
对真实后端 API 的调用。你**只消费下面冻结的 API 契约**（12-breakdown §3），
不依赖后端内部实现——按契约即可与后端并行开发（self-check 用 mock API 验证）。

## 先读这些（权威规格，按此实现，不要臆造）
- `reports/agent-runs/2026-07-hedge-open-live-v1/10-design.md`（尤其 §10 API 契约、
  §11 前端接线）
- `reports/agent-runs/2026-07-hedge-open-live-v1/12-development-breakdown.md`
  （**§3 冻结 API 契约（逐字消费）**、§5 前端契约、§7 风险点）
- stage 1 现有前端（你要改的基线）：`frontend/index.html`（开单列、开单任务页卡片、
  状态筛选、软删除、持仓表、余额弹框、fake 引擎）+ `frontend/self-check.js`。

## 允许修改的文件（硬边界，越界即无效）
- `frontend/index.html`
- `frontend/self-check.js`

## 禁止
- 改 `backend/**`、`docs/**`、`reports/**` 等任何其他文件。任何新依赖/框架/
  第二个 `<script>` 块。任何真实外部网络请求（self-check 用同源 mock）。

## 必须精确实现的冻结契约
1. **消费 §3 API 逐字**：端点路径、请求体字段（`coin/direction/mode/
   single_amount/target_n`）、响应 Task/Fill/Position JSON 字段名、错误码
   （`insufficient_balance`→按 direction 弹 stage-1 文案 `正向开单 USDT 余额不足`/
   `反向开单现货余额不足`；`invalid_field`；`invalid_state`）。
2. **替换 fake 引擎为真实调用**：`立即开单` → `POST /api/hedge-open-tasks`；
   任务页卡片/筛选/软删除/`成交1次`/`立即成交所有`/`暂停`/`启动` → 对应
   `/api/hedge-open-tasks/<id>/*` 端点；持仓表 → `GET /api/hedge-open-positions`；
   任务列表 → `GET /api/hedge-open-tasks?status=`。
3. `平滑开单` 按钮**保留但 disabled**，加 `下一轮` 提示（本轮无 ws）。
4. **执行状态徽标**读 `GET /api/hedge-open-settings` 的 `executor_mode`+
   `start_gate`（显示 dry-run / live + Start 状态）。
5. Task/Fill/`deleted` 软删除/持仓聚合展示沿用 stage 1；`exposure_alert` 状态
   要能渲染（单腿敞口）。
6. 全部新逻辑留在**第一个** `<script>` 块内（self-check 解析它）。

## 自测命令（必须真实运行并全绿）
```
node frontend/self-check.js
```
- 保留现有全部 `[PASS]`，新增断言（12-breakdown §5）：mock §3 API（同源）后的
  任务创建/生命周期、软删除、持仓从 positions 端点渲染、`平滑开单` disabled、
  `exposure_alert` 渲染、余额不足弹框两路径、**零新增跨域 fetch**。无真实网络。

## R10 收尾（逐条照做后停下）
1. 运行自测命令，把**完整输出**贴到
   `reports/agent-runs/2026-07-hedge-open-live-v1/60-test-output.txt`。
2. 写实现报告到
   `reports/agent-runs/2026-07-hedge-open-live-v1/20-implementation-hedge-fe.md`：
   改动摘要、交付项↔代码位置、契约符合性自查、自测结果、已知限制、AGENTS.md
   「Output Footer」六行（时间戳用本地 `date`，Session ID 看不到写 unavailable+
   原因）。
3. **不要** commit、不要改 status.json、不要启动/转派其他模型、不要越边界。
   完成后停下，交 bookkeeper 收证据、R4 diff 核对、串行 commit、算指纹、调度
   review-1（Claude-GLM）。
