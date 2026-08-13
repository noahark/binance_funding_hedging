# Identity

- task_id: `smooth-open-v1-running-cards-refresh-review-1-claude-glm`
- target_role: `Reviewer`
- target_model: `claude_glm`
- provider: `zhipu_glm`
- status_revision: `48`
- required_skill: `agents/skills/code-reviewer.md`

# Goal

在 fresh Claude-GLM 会话中，对 Kimi 实现的“所有 running 开单任务卡统一 2 秒刷新动态数据”
修复执行正式 Review-1，检查代码、产品口径、测试与前端接线，并给出明确
`ACCEPT（接受）` 或 `REWORK（返工）`。

实现作者为 Kimi（provider `moonshot`），本 Reviewer provider 为 `zhipu_glm`，满足跨
provider 且不得复用任何旧 Reviewer 会话。固定审查区间为：

```text
52eb1ab0de8ab890b4169068e8ef3848c9b5caf7..ad8c6317369e8a643f225cc37f22ad0eb949395b
```

区间中的 `054fbb3` 只含 30 号 dispatch 与 revision 47 `status.json`，是控制上下文，不是产品
交付；实际作者交付为单一提交 `ad8c631`。Bookkeeper 核验提交 `a764f06` 在 delivery 之后，
不进入固定审查区间，只能从 handoff 的 append-only Verification 阅读。

Human 冻结的统一规则：最新任务快照中的所有 `status=running` 开单任务，不区分
immediate/smooth、open/close、方向或日志展开状态，均复用现有共享 2 秒 tick 获取 task-id 动态
数据；非 running 任务只有仍存在且日志已展开时继续刷新，收起后停止；同一 ID 去重。页面首次
加载、刷新、进入任务页和 Start 后都通过同一 `loadHedgeTasks()` 路径立即补齐。不得新增 timer、
端点或后端/交易行为。

本任务完全只读，不授权修复、依赖变更、联网、读取凭证、服务控制、Start gate、真实任务、
订单、commit、push、merge、部署或实盘。当前 `127.0.0.1:8787` 是 Human 管理的 live 服务，
Start gate=true 且尚未加载本修复，禁止触碰。

# Allowed Files

- `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-running-cards-refresh-review-1-claude-glm.handoff.md`（唯一允许写入；create-only）

除此之外全部只读。不得修改源码、测试、计划、既有 evidence/dispatch、`status.json`、
`ACTIVE.json`、`PROJECT_STATE.md`、`.venv/` 或运行时数据，不得 commit，不得调用其他模型。

Bookkeeper create-only 预检：

```text
test ! -e reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-running-cards-refresh-review-1-claude-glm.handoff.md
exit 0（路径不存在，可由本 Reviewer 创建）
```

# Inputs

严格按顺序读取：

1. `AGENTS.md`
2. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/31-smooth-open-v1-running-cards-refresh-review-1-claude-glm.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`，只定位 2026-08-13 running smooth 刷新误报的实测事实、当前 live 服务禁区与既有接受限制
5. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json`，核对 revision `48` 与固定 SHA
6. `agents/roles.md` 的 Shared Rules、Task Handoff Evidence Contract、Reviewer 段
7. `agents/skills/code-reviewer.md`
8. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-running-cards-refresh-fix-kimi.handoff.md`，读取 Source Report 与 Bookkeeper Verification；不得把作者结论当评审证据
9. `docs/planning/smooth-open-orders-v1.md` 的 D12、D18、§8.4、§16.2、§17
10. `docs/planning/smooth-open-orders-v1-development-checklist.md` 的 §17；§1–§16 仅在直接引用时窄读
11. 原始固定 diff：
    - `git diff --stat 52eb1ab0de8ab890b4169068e8ef3848c9b5caf7..ad8c6317369e8a643f225cc37f22ad0eb949395b`
    - `git diff --find-renames 52eb1ab0de8ab890b4169068e8ef3848c9b5caf7..ad8c6317369e8a643f225cc37f22ad0eb949395b -- frontend/index.html frontend/self-check.js backend/tests/test_frontend_field_binding.py docs/planning/smooth-open-orders-v1.md docs/planning/smooth-open-orders-v1-development-checklist.md`
12. 为理解直接调用关系，可只读上述文件在 delivery tree 的完整相关函数；不得扫描其他 stage、运行时数据库、私有配置或网络

# Acceptance Checks

1. **身份、固定区间与文件范围**
   - 固定 range、Bookkeeper source SHA、`control_tip_sha=054fbb3`、一个 delivery commit `ad8c631` 可复现。
   - 作者文件恰为五个 Allowed 源/测试/计划文件与唯一 handoff；30/29 号 dispatch、revision 47 status、ACTIVE、PROJECT_STATE、backend 产品代码、provider、API、schema、依赖均无作者 diff。
   - 评审必须使用固定 SHA，不以 moving HEAD 或当前 live 页面替代。

2. **统一刷新集合正确**
   - `loadHedgeTasks()` 先取得最新 `status=all` 快照，再以全部 `task.status === 'running'` ID 与仍存在的 expanded ID 构造去重并集，并只对该集合请求 task-id 日志。
   - running 资格不含 `mode`、`task_type`、方向、smooth 字段或展开状态特判；running smooth/immediate/open/close 均覆盖。
   - 非 running 且展开的任务继续刷新，非 running 且收起、或任务已不存在时不请求；running 与 expanded 重叠时每轮恰一次。

3. **首次加载、页面刷新与共享 tick 接线**
   - 页面启动、进入开单任务页、任务 mutation/Start 后调用的既有 `loadHedgeTasks()` 都在最终渲染前补拉 running task-id 数据；刷新清空 `hedgeLogExpanded` 时 running smooth 仍能显示后端真实 `smooth_market`，不伪造连接状态。
   - `refreshExpandedRunningHedgeLogs()` 只在 `activeView=hedge-tasks && hedgeTab=tasks` 复用现有 `EXECUTION_POLL_MS` tick，先刷新任务列表再按最新状态选日志；其他 view/tab 不轮询任务卡。
   - 没有新增 timer、重复 timer、端点、缓存层或前端 gate；`setInterval(() =>` 数量仍为 `4`。

4. **既有 UI 和业务边界零回归**
   - D18 保持：只有 running smooth 卡渲染盘口动态块；非 running smooth 保留 threshold、按钮、错误和日志但隐藏动态块。
   - running 日志收起只隐藏表格、不停止动态数据；非 running 展开仍可看 drain/settle，按钮、fill-once 额外 GET、attempt/腿日志和错误回显未被破坏。
   - 新轮询只访问既有只读任务列表与 task-id 日志端点；不触碰 WebSocket/provider、gate、D15–D19 下单审计、立即/平滑执行、平仓、两腿并发或订单路径。

5. **测试能够阻止错误实现**
   - self-check 真正从空展开状态证明 running smooth 首次 load 请求日志并显示两侧连接与真实价量；删除 running 并集时测试会红。
   - 同轮 running smooth、running immediate、running close、paused-expanded、paused-collapsed 的请求集合与去重有动态断言，而不只是字符串存在性。
   - running 收起、paused 收起、paused 展开、其他 view/tab 以及 timer 数量均有回归；Python 静态断言不因注释文本产生假通过。

6. **独立复跑与 verdict**
   - 至少独立运行：

```bash
node frontend/self-check.js
.venv/bin/python -m pytest backend/tests/test_frontend_field_binding.py -q
.venv/bin/python -m pytest backend/tests/test_smooth_api.py backend/tests/test_smooth_gate_worker.py \
  backend/tests/test_hedge_service.py backend/tests/test_hedge_api.py -q
git diff --check 52eb1ab0de8ab890b4169068e8ef3848c9b5caf7..ad8c6317369e8a643f225cc37f22ad0eb949395b
```

   - 按 `AGENTS.md` §1/§8 为每条发现提供当前证据、实际影响与
     `in-range | pre-existing-independent | pre-existing-release-critical` 分类。Human 已确认的统一
     轮询负载属于产品要求，不得仅凭偏好判 REWORK；若发现当前实现在既有规模下有可复现的功能或
     资金影响，仍按证据裁定。
   - 任一 in-range 接线、刷新资格、重复请求、timer、契约或关键测试缺口 → `REWORK` 并给最小可执行
     修复要求。无 in-range 阻塞 → `ACCEPT`。
   - 创建唯一 handoff，包含 immutable Source Report、Required Reading、Human Brief 与 marker；
     Reviewer `delivery_sha` 写固定 `ad8c6317369e8a643f225cc37f22ad0eb949395b`，不得写 pending。
     Human Brief 返回合规 `[TASK_RESULT v2]` 与正式评审闭合字段。

# Stop

完成固定区间 Review-1、必要测试、唯一 handoff 和明确 verdict 后停止。不得自行修代码、改状态、
安装/卸载依赖、联网、读取凭证、控制服务、改 Start gate、创建真实任务、下单、commit、push、merge、
部署或实盘。

`ACCEPT` 只允许 Bookkeeper 核验后向 Human 汇报是否重启继续页面复验；当前未授权重启。页面复验
后仍须 fresh Review-2。`REWORK` 返回 Bookkeeper，按 Human 已允许的修复流程处理。
