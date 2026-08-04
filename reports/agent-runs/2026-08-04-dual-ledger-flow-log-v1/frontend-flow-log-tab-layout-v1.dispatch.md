Identity:
- task_id: `frontend-flow-log-tab-layout-v1`
- target_role: `Implementer`
- target_model: `grok`
- provider: `xai`
- status_revision: `14`
- required_skill: `agents/skills/senior-developer.md`

Goal

Human 2026-08-04 看了任务 C（真实数据版流水日志）后提出布局调整：**流水日志不再是独立整页视图，改为费率行情页面内的第二个看板**——费率行情页**右上角展示「费率行情 | 流水日志」两个菜单**，同一页面内两个看板切换；侧栏「流水日志」保留为与费率行情/开单任务同级的菜单。功能层（真实 API、20 条、筛选、护栏、隐私）已被 Human 认可「大部分 ok」，**本任务只改布局与导航，不得回退任何功能硬规则**。

**目标形态**：

1. **页内双看板 tab**：在 `#market-view`（费率行情页）内部右上角区域新增「费率行情 | 流水日志」两个 tab 菜单（建议复用/扩展 `.badge-row` 或新增轻量 tab 控件，样式与现有按钮体系一致）。默认激活「费率行情」tab 显示现有内容（私有账户面板 + 市场表）；点「流水日志」tab 切换为流水日志看板（现有 `#flow-log-*` 内容），**同一页面内切换，不隐藏整页/侧栏**。
2. **侧栏导航**：`#nav-flow-log` 保留（与费率行情/开单任务同级）。点击 `#nav-flow-log` → 切换到费率行情页（若不在）并**激活「流水日志」tab**；点击 `#nav-market`（费率行情）→ 激活「费率行情」tab。`#btn-flow-log`（私有账户面板内）行为同 `#nav-flow-log`。
3. **视图机制**：独立整页视图 `#flow-log-view`（`setActiveView('flow-log')`）**移除或降级为 market 视图内的 tab 分支**——目标是不再整体隐藏 `#market-view` 内容；`setActiveView` 其余分支（market/borrow/hedge）行为一字不改。
4. **轮询生命周期**：60 秒轮询随「流水日志 tab 激活」进出——流水日志 tab 激活期间恰好一个 `setInterval(60000)`（仅本地 `GET`），切回「费率行情」tab 或离开费率行情页时 `clearInterval`；不得叠加其他定时器。
5. **保留清单（不得回退）**：§13.7 冻结 DOM id 集合（`flow-log-*` 全部保留；若 `flow-log-view` 容器被移除，其内容元素 id 不变，仅容器层级调整）；真实 `GET /api/private-ledger/flow-log` + `POST /refresh` 数据源；默认最新 20 条与三数字文案；右栏类型筛选零请求；隐私遮蔽 `state.privacyHidden`；护栏三情形 + `pending_tail_ms` 附注 + 空态三态判定（`scheduler_enabled`）；「本次新增/今日累计/区间累计」三口径标注；时间窗 `近7天/近30天/自定义`（请求带参）；`formatBeijing(ms)`；§3.1/§3.2 中文文案；窄屏（≤900px）双栏堆叠。
6. **self-check**：更新为双看板 tab 断言（默认费率行情、切流水日志 tab 发一次 GET、轮询生命周期、nav-flow-log 直达、功能断言全部保留）；fetch mock 覆盖 `GET flow-log` / `POST refresh`。

不改后端、不改契约、不改既有端点调用、不启动服务、不发真实请求、**不得触发真实 `POST /refresh`**（联调与真实拉取由 Human 之后单独主持并授权）、不做下单/借还/划转/gate/凭证/部署/实盘操作。

风险等级：**LOW_RISK**（`AGENTS.md` §8 记录理由：纯前端布局/导航调整，功能层已实现并获 Human 认可，不改后端与契约、无网络资金动作）。交付后 Human 目视确认，随后设计落 v1.4 并进入前后端联调与统一评审（A+B+C，provider 隔离按 §16 勘误裁定）。

Allowed Files

- `frontend/index.html`
- `frontend/self-check.js`
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/frontend-flow-log-tab-layout-v1.handoff.md`（create-only；Bookkeeper 已执行 `test ! -e`（2026-08-04 20:52 CST）：PASS(absent)；按 `agents/roles.md` 的 Task Handoff Evidence Contract 创建唯一交接件）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/frontend-flow-log-tab-layout-v1.selfcheck.txt`（self-check 原始输出）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json`（仅可将本任务 `current_task.state` 从 `dispatched` 改为 `reported`；不得改动任何其他字段）

Inputs

- `AGENTS.md`
- 本 dispatch
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`（Human 布局反馈记录）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json`
- `agents/roles.md` 的 Implementer 章节与 Task Handoff Evidence Contract 章节
- `agents/developer-discipline.md`
- `agents/skills/senior-developer.md`
- `docs/planning/2026-08-04-dual-ledger-flow-log-design.md`（v1.3 §11/§13.2/§13.7——注意本轮布局改为页内 tab，设计 v1.4 待 Human 确认后由 Planner 落定，本任务以本 dispatch 为准）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/frontend-dual-ledger-flow-log-v1.handoff.md`（任务 C 交付事实，本任务的代码基础）
- `frontend/index.html`、`frontend/self-check.js`（C 已改，本任务在其上调整布局）

Acceptance Checks

1. 双看板 tab 成立：费率行情页右上角有「费率行情 | 流水日志」两个菜单；默认「费率行情」；点「流水日志」同页切换看板（页面/侧栏不整体隐藏）；点回「费率行情」恢复市场表；tab 高亮/`aria-current` 同步。
2. 导航一致：`#nav-flow-log` 与 `#btn-flow-log` 点击 → 费率行情页 + 激活「流水日志」tab；`#nav-market` → 激活「费率行情」tab；`setActiveView` 的 market/borrow/hedge 分支行为未变。
3. 功能硬规则零回退：真实 GET/POST、20 条三数字文案、筛选零请求、隐私遮蔽、护栏三情形 + pending_tail + 空态判定表、三口径标注、时间窗、中文文案、窄屏堆叠——全部保留（对照任务 C 的 self-check 断言，除布局相关外不得删除）。
4. 轮询生命周期：流水日志 tab 激活期间恰好一个 60 秒轮询（仅本地 GET）；切回费率行情 tab 或离开费率行情页时 `clearInterval`；无其他新增定时器。
5. `node frontend/self-check.js` 全绿（含双看板 tab 与导航断言），原始输出保存到 `.selfcheck.txt`；零网络真实请求；无 binance 直连。
6. 边界未越：未改后端/契约/既有端点调用、未启动服务、未触发真实 POST refresh、未做实盘操作。
7. 交接件与回执：创建 handoff（Source Report + Human Brief），控制台回执含合规 `[TASK_RESULT v2]` 与三行中文交接；`delivery_sha` 写 `none`（或 `pending` 若被授予提交权）；status 仅将本任务状态改为 `reported`。

Stop

只在 Allowed Files 内修改。创建 handoff 后用其 Human Brief 生成合规 `[TASK_RESULT v2]`；将本任务状态标为 `reported`。不得自行启动 Reviewer/Bookkeeper/后端任务，不得合并、部署或执行任何实盘/网络/凭据/下单操作。完成后停止，等待 Human 目视确认；确认后设计落 v1.4 并进入前后端联调与统一评审。
