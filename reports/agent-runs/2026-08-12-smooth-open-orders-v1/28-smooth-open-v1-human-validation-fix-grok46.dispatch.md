# Identity

- task_id: `smooth-open-v1-human-validation-fix-grok46`
- target_role: `Implementer`
- target_model: `grok-4.6`
- provider: `xai`
- status_revision: `45`
- required_skill: `agents/skills/minimal-change-engineer.md`

# Goal

Human 因 gpt-5.6-sol 额度不足，明确授权改由 Grok 4.6 实现本包。旧 `27-smooth-open-v1-human-validation-fix-gpt56sol-xhigh.dispatch.md` 从未启动、未产生 handoff 或实现提交，现仅作为历史控制记录；本文件是唯一活动实现包。

在唯一 worktree `/Users/ark/Desktop/ai code/funding_hedging-smooth-v1`、唯一分支 `smooth/v1-fullstack` 上实现 Human 页面验收后的 D17–D19：

1. smooth open 创建后为 `paused + awaiting_manual_start`，Human 点击任务卡“启动”后才启动 worker、公共盘口订阅、gate 与订单流程；
2. 仅 `running` smooth 卡显示动态盘口块，其他状态保留阈值、基础字段、按钮、错误原因及已展开 attempt/腿日志刷新；
3. 持久化产生本轮放行结论的同一次盘口快照，并以 monotonic 微秒记录 gate 放行到两腿各自开始调用订单客户端的分段耗时，不为审计增加下单前阻塞。

Kimi 跨 provider 计划复核已 `ACCEPT` 并经 Bookkeeper 核验。本任务固定实现基线为 `a55a673664ee3cf6b2a177774d7ba40890a2d4b3`。`rework_count=4` 保持不变：模型改派是 Human 的 pre-start 路由决定，不是一次新返工。

保持 create 阶段首次完整 preflight、固化身份/数量/route 与 regular-spot forward 预划转；保持 D15、D16、两腿并发、`prepare_attempt` 原子门、查单/结算/单腿暂停链以及 immediate/close 语义。形成一个本地 delivery commit；不 push、不 merge、不重启、不操作当前服务、不创建真实任务、不下单。

# Allowed Files

仅允许修改：

- `backend/hedge_open_tasks/domain.py`
- `backend/hedge_open_tasks/executor.py`
- `backend/hedge_open_tasks/store.py`
- `backend/hedge_open_tasks/service.py`
- `backend/services/live_hedge_executor.py`
- `frontend/index.html`
- `frontend/self-check.js`
- `backend/tests/test_smooth_api.py`
- `backend/tests/test_smooth_gate_worker.py`
- `backend/tests/test_live_hedge_executor.py`
- `backend/tests/test_hedge_service.py`
- `backend/tests/test_frontend_field_binding.py`
- `docs/api/public-market-contract.md`
- `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-human-validation-fix-grok46.handoff.md`（唯一新建、create-only）

Bookkeeper create-only 预检：

```text
test ! -e reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-human-validation-fix-grok46.handoff.md
exit 0（路径不存在，可由本任务创建）
```

其他文件全部只读。特别禁止修改 `backend/app/server.py`、`backend/services/best_bid_ask_provider.py`、scheduler、live client、preflight provider、`requirements.txt`、数据库 schema、planning、既有 evidence、dispatch、`status.json`、`ACTIVE.json`、`PROJECT_STATE.md`、运行时数据库与 `.venv/`。不得新增端点、timer、watcher、重试器、锁或状态机。若 Allowed Files 不足，创建 blocked handoff 后停止，不得自行扩权。

# Inputs

严格按顺序读取：

1. `AGENTS.md`
2. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/28-smooth-open-v1-human-validation-fix-grok46.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`，只定位 2026-08-13 smooth 页面验收事实、当前运行服务禁区与既有接受限制
5. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json`
6. `agents/roles.md` 的 Shared Rules、Task Handoff Evidence Contract、Implementer 段
7. `agents/developer-discipline.md`
8. `agents/skills/minimal-change-engineer.md`
9. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-d17-d19-plan-review-kimi.handoff.md`，读取已核验的 `verified-accept`；其中指向 27 号 gpt 包的路径已被 Human 本次改派取代
10. `docs/planning/smooth-open-orders-v1.md`，只读 D12、D15–D19、§6.5–§6.6、§8、§13、§16–§17
11. `docs/planning/smooth-open-orders-v1-development-checklist.md`，只把 §15 的产品范围与验收当权威；模型/包名由本次 Human 改派和本 dispatch 覆盖
12. Allowed Files 中的生产文件与测试；只为调用接缝可窄读其直接依赖，不得扫描无关历史阶段或运行时数据库

启动必须核对：

- `pwd` 精确为上述 worktree，分支为 `smooth/v1-fullstack`，工作树干净；
- status revision 为 `45`，task/model/provider/skill 与本包一致，`base_sha=a55a673664ee3cf6b2a177774d7ba40890a2d4b3`、`delivery_sha=null`、`rework_count=4`；
- 固定 base 是当前 HEAD 的祖先；base 之后、实现开始前只能有 Bookkeeper 创建的本 dispatch 与 revision 45 状态控制改动，产品代码必须零 diff；把启动时 HEAD 记为 `control_tip_sha`；
- Grok 只执行本 28 号包，绝不执行或沿用 27 号 gpt 包的身份、handoff 路径或 revision；
- handoff 路径不存在；
- 当前 `.venv` 已由 Human 为页面验收授权安装 `ccxt==4.5.64`，本任务不得安装、卸载或修改环境；全部测试使用 fake/离线接缝，禁止真实网络；
- `127.0.0.1:8787` 仍是 Human 管理的旧代码进程且 Start gate=true；不得探测私有接口、控制服务、改 gate 或触碰真实任务。

任一身份、状态、基线、工作树或 handoff 预检不一致，即创建 blocked handoff 并停止。

# Acceptance Checks

1. **D17：创建只建卡，Human Start 才执行**
   - 仅对 `mode=smooth && task_type=open` 的既有 INSERT 使用 `initial_status=paused`、`initial_pause_reason=awaiting_manual_start`；把 reason 中文改为任务通用的“任务首次执行必须点击启动”。
   - 删除 smooth create 末尾的 auto-`ensure_worker`。创建响应为 paused、Start 可用；创建后零 worker、provider refs、gate、attempt、executor dispatch/订单，recovery 不领取。
   - `_require_fillable` 对尚未首次 Start 的 smooth 返回 `409 start_required`，`成交1次` 不得绕过 Human。`post_start → worker` 是唯一启动路径，顺序保持 `D16 杠杆 → subscribe/open gate → evaluate → prepare → dispatch`。
   - create 阶段首次完整 preflight、缺腿/1000x 拒绝、身份/数量/route 固化和 regular-spot forward USDT 预划转原位置、原结果且只执行一次；Start 不重做。immediate 行为逐值不变。

2. **D18：动态盘口只属于 running 卡**
   - 所有 smooth 状态在基础区显示固化“滑点阈值”；动态 `smoothExtras` 只在 `task.mode === 'smooth' && task.status === 'running'` 生成。
   - paused/done/stopped/deleted 卡不得出现 `hedge-smooth-market-*`、连接状态、正/反向价格与数量、覆盖率、gate 轮次或倒计时；running 卡保留现有完整动态块。
   - 启动成功继续自动展开和 GET 日志。任务存在且日志已展开时，non-running 卡的 attempt/腿日志继续由共享 2 秒 tick 刷新；不新增 timer、不让前端计算 gate、不影响 immediate。

3. **D19：同次 gate 快照，不二次读行情**
   - `_wait_for_smooth_gate` 产生 market/manual/timeout 放行结论的同一次评估，同时形成 audit：gate seq、reason、direction、threshold、spot/perp 原始 Decimal 一档和各自 `received_at_us`、spread、两腿 coverage/pass、无效快照的 null/状态、放行 wall-clock 与 monotonic 时刻。
   - 放行后不得再次调用 provider `latest()`，不得用成交均价反推盘口。manual/timeout 在行情无效时仍保持原放行语义并如实记录当次可得状态。
   - 同一个可选 audit 载体沿 `_worker_round → _dispatch_one_for_task → AttemptContext → LiveHedgeExecutor` 传递；`AttemptContext` 新字段 optional，immediate/close/既有构造点不传时行为不变。

4. **D19：计时准确且无新增下单前阻塞**
   - 相对时间只用 monotonic 微秒，以 gate pass 为零点；wall clock 只标放行。记录 service dispatch、组参完成、`prepare_attempt` 开始/提交、executor 入口/返回、两线程各自启动、两腿各自 `order_client_call_started`/`returned`、线程完成和 join/return，并计算相邻阶段及 gate→各腿 call-start。
   - 每腿使用独立局部时间字典，join 后合并；负值或倒序由测试失败暴露，不在生产静默修正。
   - `order_client_call_started` 位于凭证检查和 route 选择之后、对应 `post_spot_order` / `post_margin_order` / `post_um_order` 调用之前；只表示客户端调用开始，不宣称网络包已离开机器。client 返回后立即打点，UM confirm/query 不混入 call-start。
   - gate pass 到两腿各自 call-start 前，除原 `prepare_attempt` 外不得新增 SQL、网络、sleep、print、同步日志或锁；不得恢复 fresh preflight、二次滑点复核或杠杆设置。

5. **审计只观测，不参与业务**
   - `executor.dispatch` 返回后立即 best-effort `append_log(kind='smooth_dispatch_audit', attempt_id=attempt_uuid)`，之后才继续既有 raw persistence/resolve/query/settlement；append 异常完全吞掉，不改变 verdict、resolve、次数、任务状态或单腿处置。
   - store 只增加 `list_logs_for_task_kind(task_id, kind)` 窄查询，不改 schema/gate/状态迁移。task-id 日志 GET additive 返回 `smooth_dispatch_audits=[log_to_doc(...)]`；无记录为 `[]`，有记录按时间/ID 稳定排序，Decimal 为字符串。
   - immediate/close 不创建 smooth audit。audit 不含 API key、signature、完整私有 URL、凭证或私有原始响应；前端不新增延迟面板。

6. **确定性回归必须能变红**
   - D17：smooth create paused、零执行资源；recovery 不领取；fill-once 409；Start 后单 worker且 D16/F1 顺序保持；regular-spot 预划转 create 一次、Start 零次；immediate 不变。
   - D18：paused 有 threshold/可用 Start、无动态块；running 动态块完整；running→paused 后动态块消失但展开日志继续刷新；immediate 不受影响。
   - D19：provider 首次通过后改变盘口，audit 仍是旧快照且 `latest()` 次数不增加；market/manual/timeout 各覆盖。fake monotonic 精确断言阶段顺序与差值；prepare、线程、某腿 client 的可控延迟只增长对应段。
   - spy store 证明首笔 audit SQL 晚于两腿 call-start 和 executor return；append 抛错时业务完全相同；阻塞 spot client 不妨碍 perp 进入自身 client，证明两腿仍并发；二次读盘口、POST 前写 audit、混入 UM confirm、串行两腿或波及 immediate/close 均须使测试变红。

7. **回归、文件范围与交付**

```bash
.venv/bin/python -m pytest backend/tests/test_smooth_api.py \
  backend/tests/test_smooth_gate_worker.py backend/tests/test_live_hedge_executor.py \
  backend/tests/test_hedge_service.py backend/tests/test_frontend_field_binding.py -q
.venv/bin/python -m pytest backend/tests/test_hedge_store.py backend/tests/test_hedge_api.py \
  backend/tests/test_hedge_task_local.py backend/tests/test_hedge_review2_regressions.py \
  backend/tests/test_hedge_leverage.py backend/tests/test_hedge_cycle_core.py \
  backend/tests/test_hedge_cycle_close.py backend/tests/test_hedge_purity.py -q
.venv/bin/python -m pytest backend/tests -q
node frontend/self-check.js
git diff --check
```

   - 全后端仅允许基线前的 `backend/tests/test_private_client.py::test_urlopen_only_in_designated_http_clients` 单一既存失败，并以 Git 证明其触发文件相对本实现零 diff。任何新失败不通过，不改断言、不跳测试。
   - 以启动时 `control_tip_sha..delivery_sha` 核验作者文件集：只能是 Allowed Files 子集加唯一 handoff。28 号 dispatch 与 revision 45 status 是 base 后既有控制上下文，必须 byte-identical；27 号旧包也不得修改。
   - 同步 `docs/api/public-market-contract.md` 的 paused-create 与 additive `smooth_dispatch_audits` 契约；不扩写其他活文档。
   - 创建唯一 handoff，author 区记录 `base_sha=a55a673664ee3cf6b2a177774d7ba40890a2d4b3`、`delivery_sha=pending`、`control_tip_sha`，逐条映射 D17–D19、文件范围、测试、冻结边界与剩余风险。只提交 Allowed Files 与 handoff，形成一个新增本地 delivery commit，不 amend、不 push、不 merge。
   - Human Brief 返回合规 `[TASK_RESULT v2]`；`下一步模型` 为 `Bookkeeper（codex）`；`下一步任务` 要求读取唯一 Grok handoff，核验 source SHA-256、允许文件、提交与全部测试并固定 `base_sha..delivery_sha`；关卡为通过后准备 fresh、跨 provider Review-1，Human 再决定是否重启页面复验，最后仍须 fresh Review-2。

# Stop

遇到身份/状态/基线不一致、handoff 已存在、控制文件被改、必须修改禁止文件、无法以零网络回归证明，或实现会触碰 D15/D16、L1/L2/L3、immediate/close、preflight、provider、scheduler、server、live client、schema/新端点时，创建 blocked handoff 后停止，不猜测、不扩权。

完成最小实现、全部测试、唯一 handoff 和一个 delivery commit 后输出 Human Brief 并停止。不得自行启动 Reviewer、修改状态、安装/卸载依赖、联网、读取凭证、控制服务、改 Start gate、创建任务、下单、push、merge、部署或实盘。
