Identity:
- task_id: `frontend-cache-refresh-v1`
- target_role: `Implementer`
- target_model: `grok`
- provider: `xai`
- status_revision: `5`
- required_skill: `agents/skills/senior-developer.md`

Goal

实现已批准 v4 设计的前端接线，只消费已交付后端 `8b624f7` 的 JSON；不修改后端、契约、任务状态或刷新调度。Human 已明确授权 Grok 执行此前端任务。新增右上角「更新缓存」按钮，调用 `POST /api/public-market/cache-refresh`；按 200 complete/partial/not_attempted、失败与 202 queued 如实提示，并仅在完成响应后手动执行现有 `loadApi()` 和 `loadHedgePositions()`。不得为任务状态变更新增前端轮询、SSE、WebSocket 或自动刷新。

原有私有账户聚合时间移到右上角刷新倒计时下一行；私有账户不可读取提示必须继续留在面板内。账户区域显示后端 `source_checked_at` 的北京时间：统一/现货用单源，PM capability 存在时在概览区上方显示 PM 时间，对冲持仓用 UM+统一+现货的最早时间；缺源显示未就绪，不能以剩余源时间伪造完整时间。`price_map` 不占账户区域标题，按钮 partial 信息负责指出它未更新。

Allowed Files

- `frontend/index.html`
- `frontend/self-check.js`
- `frontend/fixture/public-market-snapshot.json`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/frontend-cache-refresh-v1.handoff.md`（create-only；Bookkeeper 已执行 `test ! -e`，结果为通过；按 `agents/roles.md` 的 Task Handoff Evidence Contract 创建唯一交接件）
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/frontend-cache-refresh-v1.self-check.txt`（测试输出）
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/status.json`（仅可将本任务 `current_task.state` 从 `dispatched` 改为 `reported`；不得改动任何其他字段）

Inputs

- `AGENTS.md`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/frontend-cache-refresh-v1.dispatch.md`
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/status.json`
- `agents/roles.md` 的 Implementer 与 Task Handoff Evidence Contract 章节
- `agents/developer-discipline.md`
- `agents/skills/senior-developer.md`
- `docs/planning/hedge-status-account-refresh-v4.md`
- `reports/agent-runs/2026-08-03-hedge-status-account-refresh-v1/evidence/backend-cache-refresh-v1.handoff.md`
- `frontend/index.html`、`frontend/self-check.js`、`frontend/fixture/public-market-snapshot.json`

Acceptance Checks

1. 页面新增「更新缓存」按钮；点击即禁用并显示 loading，向 POST 发送请求；请求结束、失败或 202 后恢复可点；不改变既有「手动刷新」的 GET 含义。
2. complete 只提示“刷新周期已完成”并依次调用 `loadApi()`、`loadHedgePositions()`；partial/未尝试/失败/202 不夸大为账户完整更新，且不新增自动轮询。
3. 右上角在刷新倒计时下显示旧聚合「账户资产更新时间」；私有账户面板内仍能显示“私有账户未读取”，两者不复用同一 DOM 文案职责。
4. 固定五 key `source_checked_at` 以 `Asia/Shanghai` 格式显示；单源、多源最早时间、PM 三态（capability 不存在隐藏／存在但 null 未就绪／有时间显示）和缺源不退化均正确。
5. fixture 与前端 self-check 覆盖 complete/partial 显示、北京时间、缺源、PM capability 与私有账户不可读；运行保存的离线 self-check 通过。不得启动服务、使用网络、凭证或实盘操作。

Stop

只在 Allowed Files 内修改。创建交接件后，以其中 Human Brief 的内容生成合规 `[TASK_RESULT v2]`；将 status 的本任务状态改为 `reported`。在一次 delivery commit 中提交允许的前端文件、fixture、测试输出、status 与交接件；交接件的 `delivery_sha` 写 `pending`。不要自行启动 Reviewer、Bookkeeper、部署或任何实盘/网络操作。
