Identity:
- task_id: smooth-open-targeted-plan-rereview-deepseek-v4-pro
- target_role: Reviewer
- target_model: deepseek-v4-pro
- provider: deepseek
- status_revision: 12
- required_skill: agents/skills/code-reviewer.md

Goal

对 Opus 5 的平滑开单 V1 定向计划返修做一次**窄范围只读复核**，只判断上一轮 R1/R2/R3 是否关闭、新的单 Implementer 任务是否可执行、Human 冻结语义是否保持，并返回明确 `ACCEPT` 或 `REWORK`。这不是重新做一轮完整设计评审，也不是 Review-1/Review-2；已在上一轮接受且本轮未改变的设计不重开。

返修作者为 Claude Opus 5（provider `anthropic`），本复核为 DeepSeek V4 Pro（provider `deepseek`），满足跨 provider。你是上一轮 R1/R2/R3 的发现者，允许核对自己的修复要求是否满足，但必须基于固定提交和原始代码事实重新验证。本轮不授权实现、worktree/分支创建、依赖安装、联网、服务控制、下单、合并或部署。

Allowed Files

- `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-targeted-plan-rereview-deepseek-v4-pro.handoff.md`（唯一允许写入；create-only）

除创建上述唯一 handoff 外完全只读。不得修改计划、源码、既有 evidence、`status.json`、`ACTIVE.json` 或 `PROJECT_STATE.md`；不得 `git add`、commit、cherry-pick、merge、rebase、push、切换或移动 `HEAD`；不得创建 worktree/分支/stage；不得调用其他模型；不得安装依赖、访问网络/凭证、控制服务或执行行情/订单/账户/资产动作。

Bookkeeper 已执行 create-only 预检：

```text
test ! -e reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-targeted-plan-rereview-deepseek-v4-pro.handoff.md
exit 0（路径不存在，可由本复核创建）
```

Inputs

固定受审范围：

- `base_sha`: `2e5902347c5f0ac81638c67dc7a1bf20a9141ac9`
- `delivery_sha`: `8c2cce629a0688440836f07e3d089c35acbadd65`
- 计划主体差异：`git diff 2e5902347c5f0ac81638c67dc7a1bf20a9141ac9..8c2cce629a0688440836f07e3d089c35acbadd65 -- docs/planning/smooth-open-orders-v1-development-checklist.md`

按以下顺序读取：

1. `AGENTS.md`；
2. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/08-smooth-open-targeted-plan-rereview-deepseek-v4-pro.dispatch.md`；
3. `reports/agent-runs/ACTIVE.json`；
4. `PROJECT_STATE.md`；
5. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json`，核对 revision `12`、本 task_id 与固定 SHA；
6. `agents/roles.md` 的 Shared Rules、Task Handoff Evidence Contract、Reviewer 段；为 R1/R3 只按需读 Bookkeeper 段；
7. `agents/skills/code-reviewer.md`；
8. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-formal-plan-review-deepseek-v4-pro.handoff.md`；
9. 用 `git show 8c2cce629a0688440836f07e3d089c35acbadd65:docs/planning/smooth-open-orders-v1-development-checklist.md` 读取返修稿；
10. 用 `git show 2e5902347c5f0ac81638c67dc7a1bf20a9141ac9:docs/planning/smooth-open-orders-v1.md` 对照 Human 冻结语义；
11. 只为核对 R2，读取固定 base 树中的 `backend/hedge_open_tasks/store.py`：`set_task_status`、`_apply_task_counters`、`pause_task`、`stop_task_fatal`、`prepare_attempt`，以及 `backend/hedge_open_tasks/service.py`：`_pause_task_local`、`_stop_task_fatal_preflight`、`_dispatch_one_for_task`、`_worker_round`；
12. 只为核对 O2，读取固定 base 树中的 `backend/tests/test_hedge_purity.py`。

固定范围中的 dispatch/status 属控制上下文，不是计划交付主体。不得扫描无关阶段、运行时数据、仓库外文件或移动中的历史。

Acceptance Checks

- pass: **R1 定向关闭检查**：活动方案只有 `smooth-open-v1-fullstack-gpt56sol-xhigh` 一个 implementation task、一个 worktree/branch、一个 `current_task`、一个 handoff、一个 delivery commit；旧 A/B/C/D、四 worktree、并行 ledger 和多终端文稿已明确作废；没有用结束后的 handoff 替代仍在途任务状态，也没有新增状态数组或第二 schema。
- pass: **R2 路径穷举检查**：固定 base 的 task status UPDATE 是否确为 `set_task_status`、`pause_task`、`stop_task_fatal`、`_apply_task_counters` 四个函数家族；前三条在写命中时于各自事务内清三个 gate 列是否能封住原发现；条件写未命中时不清理是否保持既有防复活语义。
- pass: **R2 第四路径豁免检查**：`_apply_task_counters` 只在 attempt 已由 `prepare_attempt` 创建并清 gate 后结算，且未决 pair 阻止下一 gate 建立，因此不重复清理是否成立；§4.2.4 第 4 条断言是否足以守住该不变量。返修稿把其 UPDATE 行记为 `1192`，固定 base 中 `self._conn.execute`/SQL 字符串实际约在 `1193/1194`；这是一处已知的非语义行号漂移，按函数、SQL 与调用链裁定，不得仅为该行号返回 `REWORK`。
- pass: **R2 回归检查**：六条测试必须覆盖系统 pause 后同一未调度 seq 重开完整 5 分钟、fatal stop、Human/worker 非-running 状态、结算不变量、条件 UPDATE 竞争未命中、immediate 零变化；若第 5 条使用终态任务，测试必须以非空 sentinel 或受控竞态证明“调用前值保持”，不能以本来就是 NULL 的值形成空断言。
- pass: **R3 定向关闭检查**：Bookkeeper 只核验/记账/固定 SHA/备 review dispatch，不建分支、不 cherry-pick、不 merge；唯一 Implementer 直接在唯一分支形成 delivery commit，不再存在第二集成 owner。
- pass: **单任务可执行性**：§3.2 Allowed Files 联集覆盖 provider、gate/store、worker/API、前端、依赖清单、测试与唯一 handoff；§3.3 禁止文件保护既有实盘提交/查单/结算、scheduler 和开单率权威；四个 checkpoint 只是一个 task 内顺序，不形成第二 dispatch 或额外 commit。
- pass: **状态权限清晰性**：实现 dispatch 最终以 Allowed Files 为准。返修稿当前把 `status.json` 列为禁止改动，因此允许 Bookkeeper 按规则直接从 `dispatched` 核验到 `verified`；§3.6 与启动文稿中“实现者只能/可改为 reported”的上限描述不得被解释成实际写权限。仅当此处会令任务无法按 Harness 收口时才 `REWORK`，并给出最小的单一口径修订。
- pass: **验收充分性**：§3.5、§4.2.4、§5、§7.2 的命令和断言可在未安装 ccxt、无网络、fake provider/fake clock/record executor 下运行；不得依赖真实 5 分钟、真实 WebSocket 或真实订单。禁止文件确有零 diff 检查。
- pass: **冻结语义无回归**：`bookTicker/watchBidsAsks` 一档、signed threshold 严格 `>`、两腿各 80%、每轮 5 分钟、timeout 回退既有立即链、`成交1次` 仅放行当前 gate、两腿异步提交并同步等返回、单腿/查单/结算复用立即链均保持；不得因单 owner 改写资金语义。
- pass: **O1/O2/O3 定向关闭检查**：`latest` 只有一个明确返回/有效性语义；provider 放 `services/` 的理由与 `_LIVE_MODULE_RE`/注入 seam 相符；生产 provider 缺失、新建 smooth 400、既有 smooth 的 timeout/manual 和测试 fake provider 四种边界不含混。
- pass: `requirements.txt` 的创建属于本次实现者范围；未来依赖变更必须由获 dispatch 的 Implementer 修改、Bookkeeper 只核验。若返修稿“此后由 Bookkeeper 维护”会实际授权 Bookkeeper 改依赖文件，给出最小修订要求；不要为纯维护者措辞重开产品设计。
- pass: 不重开上一轮已接受且返修未改变的完整 provider 架构、精度公式、UI 产品选择或未来交易所扩展。任何新阻塞场景必须满足 `AGENTS.md` §1 Scenario Admission，给出当前证据和本交付实际影响。
- pass: 在唯一 handoff 中按 Task Handoff Evidence Contract 写完整 Source Report、Required Reading、Human Brief、marker；`base_sha`/`delivery_sha` 使用本 packet 固定值；返回合规 `[TASK_RESULT v2]` 与明确 `评审结论: ACCEPT | REWORK`、`问题记录`、`修复要求`。`REWORK` 只列本次定向范围内可执行修复；计划复核不改变 `rework_count`。`ACCEPT` 不授权实现或任何外部动作。

Stop

完成 R1/R2/R3、单任务范围和冻结语义的定向只读复核，创建唯一 handoff并返回结果后停止。最后一个非空白输出必须是 `[/TASK_RESULT]`。不得修改受审内容或状态，不得准备/启动实现，不得创建 worktree/分支，不得安装依赖或联网，不得控制服务、下单、提交、集成、合并、推送或部署。
