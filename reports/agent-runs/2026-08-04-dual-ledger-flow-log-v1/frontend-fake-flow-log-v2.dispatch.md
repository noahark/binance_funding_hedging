Identity:
- task_id: `frontend-fake-flow-log-v2`
- target_role: `Implementer`
- target_model: `grok`
- provider: `xai`
- status_revision: `8`
- required_skill: `agents/skills/senior-developer.md`

Goal

v1 的 FAKE 流水日志原型（`frontend-fake-flow-log-v1`，嵌入版）已交付并经 Human 查看。Human 提出两点新要求，本任务在 v1 基础上修订：

**1. 流水日志改为独立展示页（Human 2026-08-04 拍板）**：
- 不再嵌入 `#market-view` 内「私有账户面板之后、市场表之前」。改为像 **借币任务（`#nav-borrow-tasks` / `#borrow-task-view`）与开单任务（`#nav-hedge-tasks` / `#hedge-task-view`）** 那样的**独立视图页**：侧栏 `nav` 新增「流水日志」导航按钮（建议 id `nav-flow-log`），点击切换到干净独立视图（建议 id `#flow-log-view`，复用既有 `setActiveView` 视图切换机制与样式）；与「费率行情」可来回切换，nav 高亮与 `aria-current` 同步。
- 私有账户面板 `panel-actions` 里的 `#btn-flow-log` 保留，点击行为改为**切换到流水日志独立视图**（不再是就地展开面板）；`aria-expanded`/`aria-controls` 语义随视图切换调整（可改绑 `#flow-log-view`）。
- v1 已注册的 §13.7 冻结 DOM id 集合**必须全部保留**（`flow-log-panel` 如作为容器 id 保留，其层级从「市场表前嵌入」改为「独立视图内容」；`#flow-log-*` 子元素 id 全部不变），self-check 相应调整视图断言。

**2. 两栏明细默认展示最新 20 条（Human 2026-08-04 拍板）**：
- fake 数据每栏造 **≥ 20 条**（时间倒序），渲染时默认展示**最新 20 条**；在栏头或状态条注明「显示最近 20 条」。fake 阶段不做分页/加载更多（如顺手实现「加载更多」也允许，但必须默认 20 条且零网络）。

**保留 v1 全部展示硬规则**（只允许为独立视图与新条数做必要调整，不得回退）：
- 常驻「演示数据（FAKE）——非真实账户流水」标识；
- `private-ledger/v2` 假数据形状（`scheduler_enabled`、`last_run`、`coverage.by_source/gaps/pending_tail_ms/complete`、`delta`、`today`、两栏 rows/summary）；
- 护栏文案三情形（起点截断 / 区间空洞 / 空态判定表）+ `pending_tail_ms` 常驻附注；**空结果绝不允许呈现为「这段时间没有流水」**；
- 增量区块（基准时刻标题、按币种/按(类型,币种)+资金费按合约、`delta.complete=false` 不显示数字）；
- 三口径各自标注（本次新增按入库时间 / 今日累计按发生时间 / 区间累计按时间窗）；
- 右栏类型筛选纯前端零请求（`FUNDING_FEE`+`COMMISSION` 默认开）；
- 隐私遮蔽联动 `state.privacyHidden`（金额/汇总/增量 `****`，时间/类型/币种/`symbol` 可见）；
- 时间窗 `近7天/近30天/自定义`、`formatBeijing(ms)`、§3.1/§3.2 中文文案表；
- 窄屏（≤900px）双栏上下堆叠。

不改后端、不改任何既有端点调用、不连币安/无网络、不启动服务、不做下单/借还/划转/gate/凭证/部署/实盘操作。

风险等级：**LOW_RISK**（`AGENTS.md` §8 记录理由：纯前端 UI 原型迭代，仍为假数据、无真实资金语义；视图切换复用既有 `setActiveView` 机制，不新增契约）。交付后一次独立 final review（跨 provider，与 xai 不同）加 Human 目视确认。

Allowed Files

- `frontend/index.html`
- `frontend/self-check.js`
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/frontend-fake-flow-log-v2.handoff.md`（create-only；Bookkeeper 已执行 `test ! -e`（2026-08-04 15:10 CST）：PASS(absent)；按 `agents/roles.md` 的 Task Handoff Evidence Contract 创建唯一交接件）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/frontend-fake-flow-log-v2.selfcheck.txt`（self-check 原始输出）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json`（仅可将本任务 `current_task.state` 从 `dispatched` 改为 `reported`；不得改动任何其他字段）

Inputs

- `AGENTS.md`
- 本 dispatch
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`（含 Human 方向变更与本次两点决策记录）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json`
- `agents/roles.md` 的 Implementer 章节与 Task Handoff Evidence Contract 章节
- `agents/developer-discipline.md`
- `agents/skills/senior-developer.md`
- `docs/planning/2026-08-04-dual-ledger-flow-log-design.md`（§11、§13.2、§13.7；**注意**：设计当前仍是「嵌入 `#market-view`」布局，本次 Human 决策「独立页」以本 dispatch 与 PROJECT_STATE 为准，设计定稿更新待 Human 确认后由 Planner 统一落 v1.3）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/frontend-fake-flow-log-v1.handoff.md`（v1 交付事实，含 Bookkeeper Verification）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/frontend-fake-flow-log-v1.selfcheck.txt`
- `frontend/index.html`、`frontend/self-check.js`（v1 已改，本任务在其上修订）

Acceptance Checks

1. 独立视图成立：侧栏 `nav` 出现「流水日志」入口；点击后切换到干净独立视图（不显示市场表/私有账户面板内容），再点「费率行情」可切回；nav 高亮/`aria-current` 同步；`#btn-flow-log` 点击切换到该视图。
2. 视图切换复用既有机制（`setActiveView` 或同模式），未破坏借币任务/开单任务/费率行情三个既有视图的切换行为。
3. 每栏默认展示最新 20 条（时间倒序），并注明「显示最近 20 条」；fake 数据每栏 ≥ 20 条。
4. v1 全部展示硬规则保持：FAKE 标识、`private-ledger/v2` 字段、护栏三情形 + `pending_tail_ms`、增量区块、三口径标注、右栏筛选零请求、隐私遮蔽、时间窗、窄屏堆叠；§13.7 冻结 DOM id 集合全部保留并注册。
5. `node frontend/self-check.js` 全绿（含新增视图切换与 20 条断言），原始输出保存到 Allowed Files 中的 `.selfcheck.txt`；零网络请求（可静态 grep 确认无 `fetch(` 到 `/api/private-ledger/`、无 binance 直连）；无新增定时器。
6. 边界未越：未改后端、未改既有端点调用、未改市场表/借币/开单页行为、未启动服务、未做实盘操作。
7. 交接件与回执：创建 handoff（Source Report + Human Brief），控制台回执含合规 `[TASK_RESULT v2]` 与三行中文交接；`delivery_sha` 写 `none`（或 `pending` 若被授予提交权）；status 仅将本任务状态改为 `reported`。

Stop

只在 Allowed Files 内修改。创建 handoff 后用其 Human Brief 生成合规 `[TASK_RESULT v2]`；将本任务状态标为 `reported`。不得自行启动 Reviewer/Bookkeeper/后端任务，不得合并、部署或执行任何实盘/网络/凭据/下单操作。完成后停止，等待 Bookkeeper 组织 Human 目视 v2 面板；Human 确认后才恢复后端 A → B → C 真实开发。
