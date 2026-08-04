Identity:
- task_id: `plan-dual-ledger-flow-log-v1`
- target_role: `Planner`
- target_model: `codex`
- provider: `openai`
- status_revision: `1`
- required_skill: `agents/skills/task-planner.md`

Goal

把 Human 于 2026-08-04 提出的两个新需求落实为可实现的 stage 计划与实现 dispatch 包。本任务只做规划与设计定稿，**不写业务代码**：

1. **费率行情页按钮调整**（Human 已拍板语义）：`#btn-privacy`（显示金额/隐藏金额）从私有账户面板标题栏右侧 `panel-actions` 移到「私有账户」标题文字右侧紧邻处（`panel-title` 内）；原 `panel-actions` 位置新增「流水日志」按钮（打开双栏流水日志）。
2. **流水日志功能**：双栏流水日志——左栏 sapi `GET /sapi/v1/margin/interestHistory`，右栏 papi `GET /papi/v1/um/income`（全类型：资金费、手续费、划转、已实现盈亏等），双栏按时间倒序。设计权威：`docs/planning/2026-08-04-dual-ledger-flow-log-design.md`（当前为草案，待你定稿）。

Planner 须：

- 定稿设计文档：逐条处理 §7 六个开放问题（右栏默认筛选、时间默认窗、左栏未结展示、symbol/任务过滤、本地缓存、CSV 导出），给出推荐默认值，并明确标注**需 Human 拍板的产品决策点**（时间默认窗、缓存方案、汇总口径）；确认 §2 已拍板方向不变（双栏分源、sapi+papi、展示层时间倒序、按币种分列禁止混加）。
- 拆分为可安全分离的实现任务（建议 backend 与 frontend 两个任务）：backend 任务 = `private_client.py` 白名单新增 + fetcher + HTTP 契约/schema + 离线 pytest；frontend 任务 = 按钮调整 + 双栏日志面板 + self-check。任务文件边界不得重叠，接口契约双向对齐。
- 明确风险判定与流程：本功能涉及资金流水/PnL/账务含义展示，按 `AGENTS.md` §8 属 `HIGH_RISK`，**实现开始前须安排一次独立跨 provider 只读计划评审**（verdict 返回 Planner，不触 `rework_count`）；评审模型须与实现作者和计划作者跨 provider。
- 产出实现 dispatch 包：每个实现任务一个 dispatch 文件（Bookkeeper dispatch 形状：Identity/Goal/Allowed Files/Inputs/Acceptance Checks/Stop），含具体文件边界与可执行验收命令。
- 不得实现业务代码、不得评审自己的计划、不得启动任何模型终端、不得执行实盘/网络/凭据/下单操作。

Allowed Files

- `docs/planning/2026-08-04-dual-ledger-flow-log-design.md`（设计定稿）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/plan-dual-ledger-flow-log-v1.handoff.md`（create-only；Bookkeeper 已执行 `test ! -e`，结果为通过；按 `agents/roles.md` 的 Task Handoff Evidence Contract 创建唯一交接件）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json`（仅可将本任务 `current_task.state` 从 `dispatched` 改为 `reported`；不得改动任何其他字段）
- 新建 `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/<task-id>.dispatch.md`（下一实现任务的 packet；写入前自行执行 `test ! -e` 预检并记录结果）

Inputs

- `AGENTS.md`
- 本 dispatch
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json`
- `agents/roles.md` 的 Planner 章节与 Task Handoff Evidence Contract 章节
- `agents/skills/task-planner.md`
- `docs/planning/2026-08-04-dual-ledger-flow-log-design.md`（草案）
- `reports/api-samples/2026-08-borrow-interest-history-recon-v1/20260804T0008Z/recon.md`
- `reports/api-samples/2026-08-um-income-funding-recon-v1/20260804T0015Z/recon.md`
- `frontend/index.html`、`frontend/self-check.js`（需求 1 落点：`#btn-privacy` 位于 `frontend/index.html:1127-1133` 私有账户面板 `panel-actions`；self-check 只断言按钮 id、不断言父元素）
- `backend/services/private_client.py`（白名单落点：现有 `("GET", "/papi/v1/margin/marginInterestHistory")` 白名单，缺 sapi interestHistory 与 papi um/income）

Acceptance Checks

1. 设计文档定稿同时覆盖两个需求：需求 1（按钮移动 + 流水日志按钮入口）与需求 2（双栏、左 sapi interestHistory / 右 papi um/income 全类型、时间倒序、按币种分列汇总、右栏默认 FUNDING_FEE+COMMISSION）均有对应章节；§7 开放问题逐条给出推荐默认值，需 Human 拍板的产品决策点明确列出。
2. 任务拆分可安全分离：backend 与 frontend 任务 Allowed Files 不重叠，接口契约（新只读端点及其响应形状）双向对齐；每个任务含可执行验收命令（pytest / self-check）。
3. 需求 1 计划明确：`#btn-privacy` 移入 `panel-title` 内标题旁、新「流水日志」按钮（如 `#btn-flow-log`）置于原 `panel-actions`；现有 self-check 断言不因移动失效，并补充新按钮断言。
4. 安全与流程：仅只读 GET 新接口，沿用 `binance_signing` 与私有只读通道；白名单新增确认为 `GET /sapi/v1/margin/interestHistory` + `GET /papi/v1/um/income`；HIGH_RISK 计划评审已列入实现前流程；无下单/借还/划转/改 gate/凭证操作。
5. 产出实现 dispatch 包：backend 与 frontend 各一份（或按拆分数量），格式符合 Bookkeeper dispatch 形状，含 preflight 记录。
6. 交接件与回执：创建 handoff（Source Report + Human Brief），控制台回执含合规 `[TASK_RESULT v2]`；`delivery_sha` 写 `none`（本任务无交付代码提交）；`下一步模型` 指向 `status.json.bookkeeper`（bookkeeper1）；status 仅将本任务状态改为 `reported`。

Stop

只在 Allowed Files 内修改；不得触碰 `backend/`、`frontend/` 业务代码，不得评审自己的计划，不得启动任何模型终端，不得执行实盘/网络/凭据/下单操作。计划、决策点与实现 dispatch 包就绪后停止，等待 Human 确认计划与启动下一任务。
