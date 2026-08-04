Identity:
- task_id: `plan-revise-dual-ledger-flow-log-v1`
- target_role: `Planner`
- target_model: `opus5`
- provider: `anthropic`
- status_revision: `4`
- required_skill: `agents/skills/software-architect.md`

Goal

计划评审（`plan-review-dual-ledger-flow-log-v1`，deepseek 只读）对设计定稿 v1.1 与三份实现 dispatch 给出 **REWORK** verdict，F1–F6 全部 `in-range` 且附可执行修改要求。本任务按评审发现修订设计文档与 A/B 两份实现 dispatch，使契约语义自洽、可进入实现。**不写业务代码**。评审 REWORK 按 `AGENTS.md` §8 不触 `rework_count`。

**必须落实的六项发现（评审 F1–F6，全部须落回文档）**：

- **F1 事务粒度矛盾**：§13.5「任一页失败 → 该栏本次 run 记 error 且该栏不写库、另一栏不受影响」与 §14 规则 5「明细 + run 记录 + ledger_meta 同一事务、失败整体回滚、只留 error」字面冲突。按评审推荐修订：run 记录始终写（含两栏 status/error 短码）；仅成功栏产生明细写入；成功栏明细 + coverage 更新 + run 记录在同一事务；失败栏零明细。
- **F2 `consecutive_failure_count` 无数据源**：§13.2 `last_run` 与 §15.3 要求该字段，但 §14 `flow_refresh_runs` 无此列。按评审推荐：service 按 run 表最近连续 error 记录实时计数，**不新增列**（避免 A 建表与 B 读数脱节）。
- **F3 基准口径不一致**：A 的 dispatch 验收 4「最近 N 次成功 scheduled run」与设计 §15.4「倒数第二次成功 scheduled/startup_catchup run」不一致。统一为含 `startup_catchup`；`delta.complete` 判定（≥2 次成功 run）同步；评审 O7（§15.4 措辞与 baseline 定义不一致）并入本条修订。
- **F4 coverage 内部空洞无法表达**：>30 天停机截断场景下 `coverage_start_ms` 不变、标不连续，但 §13.2 `coverage` 仅 `start_ms/end_ms/complete` 三字段、规则 7 只按 `window.start < coverage.start` 触发 false，空洞内查询误报「无流水」。统一 `complete` 语义：窗口内覆盖不连续（含 `window.start < coverage.start` 或存在未回补空洞）即 `false`；前端必须提示（C 已按 §13.7 渲染，若需调整 C 的判定依据，仅在设计里写明、不动 C packet，除非评审确认必须）。
- **F5 空库空态形状未冻结**：首次启动 / 私有通道未启用 / 从未成功 run 时 `GET flow-log` 的 `last_run` / `coverage` / `delta` 取值未定义（首次展开即 GET 是必走路径）。冻结空态契约：`last_run: null`、`coverage: {"start_ms": null, "end_ms": null, "complete": false}`、`delta.complete: false`，并在 §13.2 写明前端三态（该时间窗无记录 / 上次刷新失败 / 私有通道未启用）的判定依据。
- **F6 两项未定义语义**：(a) manual run 成功是否更新 `coverage_end`；(b) `truncated=true` 时已拉到的页是否部分入库。按评审推荐写死：manual 成功同样更新 coverage（`kind` 记为 manual）；`truncated` 时该栏**整栏回滚不提交明细**并置 `truncated=true`，避免 coverage 前移制造空洞。

**评审观察项建议一并处理**（低成本、不扩大范围）：O1（>3h 晚到且发生时间早于 `coverage_end-3h` 的记录永久丢失且无检测——写入 §17.4 已知代价）；O2（§16「零重叠」措辞 vs 三份 packet 都含 `status.json` 的事实——注明 status.json 语义例外）；O3（A 的 handoff 应列明 `store`/`domain` 公开函数签名，供 B 消费——写入 A 的 dispatch Stop/Inputs 要求）；O4（汇总显式 `localcontext()`——写入 A 验收或 §14 规则）；O5（`GET flow-log` 响应 `Cache-Control: no-store`——写入 B dispatch 验收）；O8（左栏 40 页上限余量，借款量增长可能触顶——§17.4 一句说明即可）。O6（时钟回拨低概率观察）可只在 §17.4 记一句或不处理。

**修订纪律**：

- 只修订评审点名的文件：设计文档（§13.2/§13.5/§14/§15.2/§15.4 及相关章节）与 A、B 两份 dispatch。**不开放 C**（frontend packet）——若修订中发现必须动 C 才能闭环，停止并回报 Bookkeeper/评审确认，不得自行扩大范围。
- 保持「三个任务之间的唯一对齐点」原则：契约语义先在设计冻结，A/B/C 的 dispatch 措辞随后对齐；不得让实现任务的验收标准与设计互相矛盾。
- 修订记录表追加一行（注明「v1.2，计划评审 REWORK 后修订，F1–F6」）；草案 §1–§10 原文仍不得改写。

Allowed Files

- `docs/planning/2026-08-04-dual-ledger-flow-log-design.md`（修订 §13.2/§13.5/§14/§15.2/§15.4 及受影响章节；追加修订记录行）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/backend-ledger-store-fetch-v1.dispatch.md`（对齐 F1/F2/F3/F4/F5/F6 涉及 A 的部分：事务模型、`consecutive_failure_count` 来源、基准口径含 startup_catchup、空态建表无关但 store 查询语义、truncated 整栏回滚；验收 4 措辞）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/backend-ledger-schedule-api-v1.dispatch.md`（对齐 B 部分：run 记录事务、coverage 更新语义、manual/truncated 行为、空态响应形状、Cache-Control）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/plan-revise-dual-ledger-flow-log-v1.handoff.md`（create-only；Bookkeeper 已执行 `test ! -e`（2026-08-04 13:10 CST）：PASS(absent)；按 `agents/roles.md` 的 Task Handoff Evidence Contract 创建唯一交接件）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json`（仅可将本任务 `current_task.state` 从 `dispatched` 改为 `reported`；不得改动任何其他字段）

Inputs

- `AGENTS.md`
- 本 dispatch
- `reports/agent-runs/ACTIVE.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/status.json`
- `agents/roles.md` 的 Planner 章节与 Task Handoff Evidence Contract 章节
- `agents/skills/software-architect.md`
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/plan-review-dual-ledger-flow-log-v1.handoff.md`（**必读**：F1–F6 原文、修改要求、O1–O8 观察、Q1–Q7 分析）
- `docs/planning/2026-08-04-dual-ledger-flow-log-design.md`（§11–§18，修订对象）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/backend-ledger-store-fetch-v1.dispatch.md`、`backend-ledger-schedule-api-v1.dispatch.md`（修订对象；C 仅作只读参考）
- `reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/plan-dual-ledger-flow-log-v1.handoff.md`（原 Planner 交付事实与勘误）
- 两份 recon（`reports/api-samples/2026-08-*-recon-v1/.../recon.md`，只读证据）

Acceptance Checks

1. F1–F6 逐条修订且与评审「修改要求」一致；修订后设计 §13.2/§13.5/§14/§15.2/§15.4 与 A/B dispatch 之间无自相矛盾（特别是：事务模型、`consecutive_failure_count` 来源、基准含 startup_catchup、coverage `complete` 语义、空态形状、manual/truncated 语义）。
2. A/B/C 三个任务对齐点仍然单一（设计为权威）：修订后的设计章节与三份 dispatch 的措辞一致；C packet 未被动过（除确需经 Bookkeeper/评审确认外）。
3. 空态契约冻结（F5）明确写入设计 §13.2：`last_run: null`、`coverage: {start_ms: null, end_ms: null, complete: false}`、`delta.complete: false`，并给出前端三态判定依据。
4. 修订记录表追加 v1.2 行；草案 §1–§10 原文未改写。
5. 评审观察项按 Goal 处理：O1/O2/O3/O5 落进文档或 packet（O4 进 A 验收或 §14、O8 进 §17.4）；O6 可不处理或一句记录。
6. 交接件与回执：创建 handoff（Source Report + Human Brief），控制台回执含合规 `[TASK_RESULT v2]` 与三行中文交接；`delivery_sha` 写 `none`（本任务为文档修订，产物留在工作树交 Bookkeeper 封存——若你选择提交，须在 handoff 写明实际 SHA）；status 仅将本任务状态改为 `reported`。
7. 不越界：未写业务代码、未启动任何模型终端、未执行实盘/网络/凭据操作、未动 C packet。

Stop

只在 Allowed Files 内修改；不得触碰 `backend/`、`frontend/` 业务代码与 C packet；不得评审自己的修订（修订后按 §17.3 重出计划评审，或经 Human 认可缩小至修订增量，由 Bookkeeper 另派）；不得启动任何模型终端。修订完成并创建交接件后停止，等待 Human 转交 Bookkeeper 封存并安排重评审。
