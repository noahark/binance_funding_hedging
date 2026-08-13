# Identity

- task_id: `smooth-open-v1-running-cards-refresh-fix-kimi`
- target_role: `Implementer`
- target_model: `kimi`
- provider: `moonshot`
- status_revision: `47`
- required_skill: `agents/skills/minimal-change-engineer.md`

# Goal

修复 Human 在 D17–D19 页面验收中实测确认的任务卡刷新缺陷。当前后端公共盘口已是
`live`，但浏览器刷新会清空仅存在内存的 `hedgeLogExpanded`；前端随后只为“已展开日志”
任务请求 task-id 日志，导致仍在运行的平滑任务卡长期误报“现货/合约 数据不完整”。

Human 已把产品口径扩展为统一规则：**所有 `status=running` 的开单任务卡，不区分
`mode`、`task_type`、方向或日志展开状态，均须复用现有共享 2 秒 tick 获取最新任务快照和
task-id 动态数据；非运行任务只有日志已展开时继续刷新，收起后停止。**页面首次加载、刷新、
进入开单任务页或 Start 成功后的第一次 `loadHedgeTasks()` 也必须立即补齐全部 running 任务
的 task-id 数据，不能先长期显示伪“数据不完整”。

只修现有前端刷新选择与回归测试：不新增 timer、端点、后端轮询、WebSocket 订阅、状态层、
锁、重试器或配置；不修改盘口、gate、下单、结算、按钮和日志展开语义。task-id 日志 GET 是
本地只读投影，不能触发交易所私有请求或订单行为。

29 号 Claude-GLM Review-1 包从未产生 handoff 或 verdict，已被本次 Human 页面验收发现取代，
只保留为历史控制记录，不得执行或修改。固定实现基线为
`52eb1ab0de8ab890b4169068e8ef3848c9b5caf7`。本次是既有交付物的新一轮修复，
`rework_count=5`；Human 已明确本次重任务不限制 fix 次数，因此不受原三轮上限阻止。

# Allowed Files

仅允许修改：

- `frontend/index.html`
- `frontend/self-check.js`
- `backend/tests/test_frontend_field_binding.py`
- `docs/planning/smooth-open-orders-v1.md`（只同步 D12/D18 的统一 2 秒刷新口径）
- `docs/planning/smooth-open-orders-v1-development-checklist.md`（只追加本修复的范围与验收）
- `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-running-cards-refresh-fix-kimi.handoff.md`（唯一新建、create-only）

Bookkeeper create-only 预检：

```text
test ! -e reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-running-cards-refresh-fix-kimi.handoff.md
exit 0（路径不存在，可由本任务创建）
```

其他文件全部只读。特别禁止修改 backend、API、provider、scheduler、数据库 schema、
`requirements.txt`、既有 evidence/dispatch、`status.json`、`ACTIVE.json`、`PROJECT_STATE.md`、
运行时数据库和 `.venv/`。不得新增依赖、timer、缓存层、事件总线或刷新状态机；不得为了命名
顺手重构无关函数。若范围不足，创建 blocked handoff 后停止，不得自行扩权。

# Inputs

严格按顺序读取：

1. `AGENTS.md`
2. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/30-smooth-open-v1-running-cards-refresh-fix-kimi.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`，只定位 `2026-08-13` smooth 任务卡刷新误报、当前运行服务禁区与既有接受限制
5. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json`
6. `agents/roles.md` 的 Shared Rules、Task Handoff Evidence Contract、Implementer 段
7. `agents/developer-discipline.md`
8. `agents/skills/minimal-change-engineer.md`
9. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-human-validation-fix-grok46.handoff.md`，只读取 D18 当前实现与已核验交付边界
10. `docs/planning/smooth-open-orders-v1.md`，只读 D12、D18 与页面刷新相关段落
11. `docs/planning/smooth-open-orders-v1-development-checklist.md`，只读 D18 及当前页面验收相关段落
12. Allowed Files 中的源文件与测试，只为直接调用关系窄读相邻函数，不扫描其他 stage、运行时数据库或私有配置

启动必须核对：

- `pwd` 精确为 `/Users/ark/Desktop/ai code/funding_hedging-smooth-v1`，分支为 `smooth/v1-fullstack`，tracked 工作树干净；
- status revision 为 `47`，task/model/provider/skill 与本包一致；`base_sha=52eb1ab0de8ab890b4169068e8ef3848c9b5caf7`、`delivery_sha=null`、`rework_count=5`；
- 固定 base 是当前 HEAD 的祖先；base 之后、实现开始前只能有 Bookkeeper 创建的本 dispatch 与 revision 47 状态控制提交，产品代码必须零 diff；记录启动时 `control_tip_sha`；
- 29 号旧 Review-1 handoff 与本任务 handoff 均不存在；只执行本 30 号包；
- 当前 `127.0.0.1:8787` 是 Human 管理的 live 服务，Start gate=true，且可能存在真实运行任务；不得联网探测、控制服务、改 gate、访问私有接口或触碰真实任务；
- `.venv` 已有 Human 授权安装的依赖，本任务不得安装、卸载或修改环境；全部测试使用现有 fake/离线接缝。

任一身份、状态、基线、工作树、服务禁区或 handoff 预检不一致，即创建 blocked handoff 并停止。

# Acceptance Checks

1. **统一的 2 秒刷新资格**
   - 当 `state.activeView === 'hedge-tasks' && state.hedgeTab === 'tasks'` 时，复用现有 `EXECUTION_POLL_MS` tick 调用现有任务刷新路径；不得新增 `setInterval`。
   - 每轮先读取 `GET /api/hedge-open-tasks?status=all`，使当前标签页能发现由本页、刷新恢复或其他标签页造成的 running/非 running 状态变化。
   - task-id 日志刷新集合必须是“最新任务快照中的全部 `status === 'running'` 任务 ID”与“仍存在且日志已展开的任务 ID”的去重并集。
   - 选择条件只能依赖任务存在、`status` 和展开状态，不得按 `mode`、`task_type`、方向或 smooth 字段过滤；running immediate/open/close 与 running smooth 同等刷新。

2. **首次加载与页面刷新不再误报**
   - `loadHedgeTasks()` 得到最新任务列表后，在渲染任务卡前为上述并集完成 task-id 日志 GET；页面首次加载、浏览器刷新、进入任务页和 Start 后都走同一条路径。
   - running smooth 即使 `hedgeLogExpanded` 为空，也能从同源响应写入 `state.hedgeTaskLogs[id].smoothMarket`，卡片展示真实连接、价量、开单率、覆盖率和等待原因。
   - 禁止伪造“已连接”或用任务列表字段拼盘口；接口失败沿用现有错误/上次缓存行为，不修改 gate 或下单。

3. **非运行和展开语义保持**
   - paused/done/stopped/deleted 且日志收起的任务不请求 task-id 日志；已展开且任务仍存在的非运行任务继续每 2 秒刷新 attempt/腿日志。
   - running 任务日志收起只隐藏日志表，不停止动态数据请求；展开/收起按钮、表格、错误回显和 D18“只有 running smooth 卡渲染动态盘口块”保持不变。
   - 同一任务同时满足 running 与 expanded 时每轮只能请求一次 task-id 日志；任务不存在时不请求。

4. **无新增运行和交易副作用**
   - `setInterval(() =>` 数量保持现有值，刷新频率继续使用 `EXECUTION_POLL_MS`；不得创建第二个 2 秒 timer。
   - 前端轮询只调用既有只读任务列表与 task-id 日志端点；不得调用 Start/Pause/Fill、私有账户、行情订阅或订单端点。
   - 不修改 backend、WebSocket/provider 生命周期、D15/D16/D17/D19、五分钟 gate、成交一次、immediate/close、两腿并发或审计语义。

5. **可变红回归**
   - self-check 从 `hedgeLogExpanded` 空集合模拟整页刷新：后端返回一个 running smooth，第一次 `loadHedgeTasks()` 必须请求其 task-id 日志并把卡片渲染为两侧已连接及真实价量；删除 running 并集逻辑时测试必须变红。
   - 同轮至少包含 running smooth、running immediate、running close、paused-expanded、paused-collapsed，并断言前四类按规则请求、paused-collapsed 不请求、任一 ID 不重复。
   - 共享 tick 在任务页每轮先刷新任务列表，再按最新状态选择 task-id 日志；切到其他 view 或日志 tab 时保持现有不刷新任务卡规则。
   - Python 静态接线测试确认 running 选择不含 `mode`/`task_type` 特判、非运行展开仍保留、timer 数量不增加。

6. **文档、回归与交付**
   - 仅在两份 Allowed planning 文件中把旧“只有展开日志才刷新”的口径改为本 dispatch 的统一规则；不改其他设计决策或历史 verdict。
   - 至少运行：

```bash
node frontend/self-check.js
.venv/bin/python -m pytest backend/tests/test_frontend_field_binding.py -q
.venv/bin/python -m pytest backend/tests/test_smooth_api.py backend/tests/test_smooth_gate_worker.py \
  backend/tests/test_hedge_service.py backend/tests/test_hedge_api.py -q
git diff --check
```

   - 任何新失败不通过，不删断言、不跳测试。以 `control_tip_sha..delivery_sha` 核验作者文件集只能是 Allowed Files 子集加唯一 handoff；29 号旧包、revision 47 status 与既有 evidence 必须 byte-identical。
   - 创建唯一 handoff，author 区写 `base_sha=52eb1ab0de8ab890b4169068e8ef3848c9b5caf7`、`delivery_sha=pending`、`control_tip_sha`，映射修改、测试、禁止范围和剩余风险。提交 Allowed Files 与 handoff 为一个新增本地 delivery commit；不 amend、不 push、不 merge。
   - Human Brief 返回合规 `[TASK_RESULT v2]`；`下一步模型` 为 `Bookkeeper（codex）`；`下一步任务` 必须要求读取唯一 Kimi handoff，核验 source SHA-256、文件范围、提交与测试并固定新 `base_sha..delivery_sha`；关卡为通过后准备 fresh、跨 provider Review-1，Human 页面复验后再走 fresh Review-2。

# Stop

遇到身份/状态/基线不一致、handoff 已存在、控制文件被改、必须修改禁止文件、测试需要真实网络，
或修复会触碰 backend、provider、gate、订单、按钮行为、新 timer/端点/依赖时，创建 blocked handoff 后
停止，不猜测、不扩权。

完成最小前端修复、文档同步、全部测试、唯一 handoff 和一个 delivery commit 后输出 Human Brief 并
停止。不得自行启动 Reviewer、修改状态、安装依赖、联网、读取凭证、控制服务、改 Start gate、创建
任务、下单、push、merge、部署或实盘。
