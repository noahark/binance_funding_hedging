Identity:
- task_id: smooth-open-formal-plan-review-deepseek-v4-pro
- target_role: Reviewer
- target_model: deepseek-v4-pro
- provider: deepseek
- status_revision: 8
- required_skill: agents/skills/code-reviewer.md

Goal

对平滑开单 V1 的 Human 冻结设计与 Opus 5 实施细拆做一次正式、跨 provider、只读计划评审，给出明确 `ACCEPT` 或 `REWORK`。本轮只判断计划能否安全、可执行地进入实现，不评审尚不存在的实现，也不授权创建实现 worktree、安装依赖、连接网络、启动服务、下单、集成、合并或部署。

细拆作者为 Claude Opus 5（provider `anthropic`），本评审为 DeepSeek V4 Pro（provider `deepseek`），满足跨 provider，且 DeepSeek 未参与此前 advisory、细拆或实现。status revision 7 的 Grok 评审包未启动、未产生 handoff，已按 Human 决定在启动前由本包替代；这不是 `REWORK`，不改变 `rework_count`。

Bookkeeper 预核验发现一个必须正式裁定的开放问题：细拆 §5.4 拟在 A 尚未核验时把唯一的 `status.json.current_task` 从 A 覆盖成 B，再以 A 的任务结束 handoff 代替权威状态。`agents/roles.md` 把 `current_task` 定义为唯一活动 packet，handoff 又只能在任务结束时形成，因此这段目前不能被 Bookkeeper 当作已解决。评审必须核对原始规则并裁定；若没有直接规则证据证明其合规，应返回 `REWORK`，要求计划在以下最小方向中明确一种：同一 stage 内顺序 dispatch，或为并行 worktree 建各自独立且可启动核对的 stage/`ACTIVE.json`/`status.json` 记账，再定义不越权的集成收口。不得新增并行数组、第二套状态 schema、临时 ledger 或以 handoff 替代在途状态。

Allowed Files

- `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-formal-plan-review-deepseek-v4-pro.handoff.md`（唯一允许写入；create-only）

除创建上述唯一 handoff 外完全只读。不得修改交付文档、源码、既有 evidence、`status.json`、`ACTIVE.json` 或 `PROJECT_STATE.md`；不得 `git add`、commit、cherry-pick、merge、rebase、push、切换或移动 `HEAD`；不得创建 worktree/分支/stage；不得调用或指派其他模型；不得安装依赖、访问网络/凭证、控制服务或执行任何订单/账户/资产动作。

Bookkeeper 已执行 create-only 预检：

```text
test ! -e reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-formal-plan-review-deepseek-v4-pro.handoff.md
exit 0（路径不存在，可由本评审创建）
```

Inputs

固定受审范围：

- `base_sha`: `0f19beae98b6909c2a5f0a9764f81f71b474a226`
- `delivery_sha`: `b474f4ac28fe9534884c66a664d7fb6365305a6d`
- 主体差异：`git diff 0f19beae98b6909c2a5f0a9764f81f71b474a226..b474f4ac28fe9534884c66a664d7fb6365305a6d -- docs/planning/smooth-open-orders-v1-development-checklist.md`

按以下顺序读取：

1. `AGENTS.md`；
2. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/06-smooth-open-formal-plan-review-deepseek-v4-pro.dispatch.md`；
3. `reports/agent-runs/ACTIVE.json`；
4. `PROJECT_STATE.md`；
5. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json`，核对 revision `8`、本 task_id 与固定 SHA；
6. `agents/roles.md` 的 Shared Rules、Task Handoff Evidence Contract、Reviewer 段；为裁定 §5.4 与 §8.1，再读 Bookkeeper 段的 Minimal State、Task State、SHA Discipline、Required Behavior；
7. `agents/skills/code-reviewer.md`；
8. 用 `git show b474f4ac28fe9534884c66a664d7fb6365305a6d:docs/planning/smooth-open-orders-v1-development-checklist.md` 读取受审细拆；
9. 用 `git show 0f19beae98b6909c2a5f0a9764f81f71b474a226:docs/planning/smooth-open-orders-v1.md` 读取 Human 冻结设计；
10. `docs/planning/ccxt-bookticker-recon-2026-08-13.md` 与 `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/ccxt-bookticker-recon-claude-glm.handoff.md`；
11. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/01-advisory-design-reviews.md`（只作历史输入，不作本轮 verdict）；
12. 仅为核对细拆所述真实调用链与文件边界，按需只读固定 base 树中的 `backend/domain/snapshot.py`、`backend/hedge_open_tasks/domain.py`、`backend/hedge_open_tasks/store.py`、`backend/hedge_open_tasks/service.py`、`backend/hedge_open_tasks/scheduler.py`、`backend/app/server.py`、`backend/tests/test_hedge_purity.py`、`backend/tests/test_hedge_cycle_core.py`、`frontend/index.html`、`frontend/self-check.js`。

不得扫描无关阶段、运行时数据、仓库外文件或移动中的历史；代码事实以固定 SHA 的 `git show`/`git diff` 为准。

Acceptance Checks

- pass: 逐条区分 Human 已冻结产品决定与 Opus 实现选择；不因偏好重开 `bookTicker/watchBidsAsks`、signed threshold 严格 `>`、两腿各 80%、每轮 5 分钟、timeout 回退立即链、当前 gate 专属 `成交1次`、两腿复用既有异步执行链。
- pass: 裁定 A/B 并行、C 后置、D 后置的真实依赖是否成立，核对所有 Allowed Files、现有测试文件、共享 fixture、schema/API owner 和组合根；不能靠猜测接口、兼容层、双实现或第五个协调框架换并行。
- pass: 对 §5.4 单 `current_task` 作明确 verdict。必须引用 `AGENTS.md`/`agents/roles.md` 的直接规则，说明 handoff 能否替代仍在执行的 A 的权威状态；不能只说“Bookkeeper 后面记住即可”。若不合规，给出不新增 schema 的可执行改稿要求，并说明 A/B 是否仍可真并行。
- pass: 核对 §8.1 的角色与授权：计划一面称 C 为唯一集成者，一面又让 Bookkeeper 建分支并 cherry-pick A/B。判断这是否使 Bookkeeper 越过记账职责、是否属于须 Human 明确授权的 merge/integration；若有冲突，给出唯一 owner 和启动顺序的最小修订。
- pass: 核对“三个 Human 终端/三个启动文稿”与 A/B/C/D 四包是否自洽：D 是同一 Claude-GLM 终端后置复用还是缺失的第四正式 packet，何时冻结 API、何时生成 dispatch/status，不能让前端针对猜测字段实施。
- pass: 核对跨任务契约是否真的冻结到足够消费：`MarketKey` native/unified symbol 映射、spot/swap client ownership、同 key refcount、每 key/每 client watcher 关系、`latest` 的 `None`/非-live 二选一、raw `b/B/a/A` Decimal、generation、contractSize==1 断言、1000x 继续封禁、close/join、`on_change` 线程边界。任何留给 A 自选但会影响 C 的行为都必须判明 owner 与测试契约。
- pass: 核对依赖边界：`requirements.txt` 的唯一 owner 和 `ccxt==4.5.64` pin 是否与 Human 设计一致；在实现/评审环境完全不安装 ccxt、只靠惰性 import 与 fake source，是否足以验证默认 CCXT adapter 与锁定版本真实兼容。若不足，修订要求必须把“隔离开发验证”和“生产 `.venv` 安装”分开，后者仍须 Human 单独授权，且不得在本评审执行安装或联网。
- pass: 核对 provider 不可用语义：新建 smooth 返回 400、既有持久化 smooth task 在重启后是否仍能凭已保存 deadline/force 走 timeout/manual、何时 fail-closed、何时允许绕过行情条件；不得出现“任务创建已拒绝但同一任务仍可 timeout/manual”的含混表述。
- pass: 核对 gate 事务与所有旁路：`open_smooth_gate`、`force_smooth_gate`、`prepare_attempt(expected_gate_seq, pass_reason)`、计数递增与 gate 清理同事务，能否封住 market/manual/timeout 三方竞态、10/10 第 11 单、dry-run tick、非 live fill-once、fill-all、pause/delete、Start gate、重启/PREPARED 恢复；`set_task_status` 是否真是所有非-running 状态迁移的唯一收口。
- pass: 核对等待模型为 `Condition + wake_version` 且不忙循环、不丢唤醒、不复用 `_stop_events`；六类唤醒源与现有 worker/pause/delete/stop 行为有固定代码证据，停机 wall-clock 计入窗口但不绕过既有安全门。
- pass: 核对开单率和覆盖率的单位、方向、精度与展示：复用 `compute_opening_spread_pct` 的两位量化后再严格比较是否就是 Human 要求，覆盖分母 `task.q_common` 与两腿盘口 raw qty 是否同量纲，forward/reverse 取价/取量是否一致，OKX 等非 1 contractSize 不得被误泛化。
- pass: 核对 A 的 11 项 P1、B/C/D 的命令和最终 R1-R10 能在不连真实 WS、不发订单的环境中形成可执行验收；不接受“CCXT 应该会自动重连/close”或只测自写 fake、不触达实际 adapter seam 的循环论证。
- pass: 核对现有 immediate 创建/fill-once/fill-all、close、dry-run tick、市场页 REST 开单率、executor/query/settlement 路径的零回归边界，且 smooth 的解除冻结、所有旁路封口和前端按钮行为在同一可审交付内闭合。
- pass: 检查 Planner 原 dispatch 的全部验收项，特别是“恰好三个有界实现包”“独立 worktree/branch/stage 不共享 `ACTIVE.json`/`status.json`”“一个 owner 的 integration/cherry-pick”是否真的满足；不能因文档自称完成而判 pass。
- pass: 新假设场景遵守 `AGENTS.md` §1 Scenario Admission，附当前代码路径、外部契约或具体并发/单位证据及本轮实际影响。计划评审发生在实现前，`REWORK` 不递增 `rework_count`。
- pass: 在唯一 handoff 中按 Task Handoff Evidence Contract 写完整 Source Report、Required Reading、Human Brief、marker，`base_sha`/`delivery_sha` 使用本 packet 的固定值；返回合规 `[TASK_RESULT v2]`，并给出明确 `评审结论: ACCEPT | REWORK`、`问题记录`、`修复要求`。`REWORK` 的每条要求必须可直接交给 Planner 改稿；`ACCEPT` 也不授权实现、依赖安装、服务控制、集成、部署或实盘。

Stop

完成固定范围的只读计划评审、创建唯一 handoff、返回合规中文 `[TASK_RESULT v2]` 后停止。最后一个非空白输出必须是 `[/TASK_RESULT]`。不得修改受审内容或状态，不得准备/启动实现任务，不得创建 worktree/分支/stage，不得安装依赖或访问网络，不得连接公共/私有行情，不得控制服务，不得下单、集成、合并、推送或部署。
