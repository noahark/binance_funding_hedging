# Identity

- task_id: `smooth-open-v1-d17-d19-review-1-claude-glm`
- target_role: `Reviewer`
- target_model: `claude_glm`
- provider: `zhipu_glm`
- status_revision: `46`
- required_skill: `agents/skills/code-reviewer.md`

# Goal

在 fresh Claude-GLM 会话中，对 Grok 4.6 实现的 D17–D19 做正式 Review-1，检查代码、公共契约、测试与跨层接缝，并给出明确 `ACCEPT（接受）` 或 `REWORK（返工）`。

实现作者为 Grok 4.6（provider `xai`），本 Reviewer provider 为 `zhipu_glm`，满足跨 provider 且不得复用实现会话。固定审查区间为：

```text
a55a673664ee3cf6b2a177774d7ba40890a2d4b3..bba31ea519c9831b38256918d8854f4c20d58aad
```

区间中的 `f19f5c0` 只含 28 号 dispatch 与 revision 45 `status.json`，是控制上下文，不是产品交付；实际作者代码提交是 `f19f5c0a661947a253dfb4d0705f183839ec0b69..bba31ea519c9831b38256918d8854f4c20d58aad`。Bookkeeper 核验提交 `8e98672` 在 delivery 之后，不进入固定审查区间，只能从 handoff 的 append-only Verification 阅读。

Review-1 聚焦三项 Human 已冻结的实际效果：smooth 创建暂停且 Start 后才执行；动态盘口只在 running 卡出现但展开日志继续刷新；同一次放行盘口和 gate→两腿订单客户端调用的延迟可审计，且审计不增加下单前阻塞、不改变订单结果。

本任务完全只读，不授权修复、依赖变更、联网、读取凭证、服务控制、Start gate、真实任务、订单、commit、push、merge、部署或实盘。当前 `127.0.0.1:8787` 仍是 Human 管理的旧代码进程，禁止触碰。

# Allowed Files

- `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-d17-d19-review-1-claude-glm.handoff.md`（唯一允许写入；create-only）

除此之外全部只读。不得修改源码、测试、契约、planning、既有 evidence、dispatch、`status.json`、`ACTIVE.json`、`PROJECT_STATE.md`、`.venv/` 或运行时数据，不得 commit，不得调用其他模型。

Bookkeeper create-only 预检：

```text
test ! -e reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-d17-d19-review-1-claude-glm.handoff.md
exit 0（路径不存在，可由本 Reviewer 创建）
```

# Inputs

严格按顺序读取：

1. `AGENTS.md`
2. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/29-smooth-open-v1-d17-d19-review-1-claude-glm.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`，只定位 2026-08-13 smooth 页面验收事实、当前运行服务禁区及 L1/L2/L3 接受限制
5. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json`，核对 revision `46` 与固定 SHA
6. `agents/roles.md` 的 Shared Rules、Task Handoff Evidence Contract、Reviewer 段
7. `agents/skills/code-reviewer.md`
8. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-human-validation-fix-grok46.handoff.md`，读取 Source Report 与 Bookkeeper Verification；不得把作者结论当审查证据
9. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-d17-d19-plan-review-kimi.handoff.md`，只用于冻结 D17–D19 计划边界
10. `docs/planning/smooth-open-orders-v1.md` 的 D12、D15–D19、§6.5–§6.6、§8、§13、§16–§17
11. `docs/planning/smooth-open-orders-v1-development-checklist.md` 的 §15；§1–§14 为历史
12. 原始固定 diff：
    - `git diff --stat a55a673664ee3cf6b2a177774d7ba40890a2d4b3..bba31ea519c9831b38256918d8854f4c20d58aad`
    - `git diff --find-renames a55a673664ee3cf6b2a177774d7ba40890a2d4b3..bba31ea519c9831b38256918d8854f4c20d58aad -- backend/hedge_open_tasks/domain.py backend/hedge_open_tasks/executor.py backend/hedge_open_tasks/store.py backend/hedge_open_tasks/service.py backend/services/live_hedge_executor.py frontend/index.html frontend/self-check.js backend/tests/test_smooth_api.py backend/tests/test_smooth_gate_worker.py backend/tests/test_live_hedge_executor.py backend/tests/test_hedge_service.py backend/tests/test_frontend_field_binding.py docs/api/public-market-contract.md`
13. 为理解直接调用关系，可只读上述文件在 delivery tree 的完整相关函数；不得扫描无关历史 stage、运行时数据库或私有配置

# Acceptance Checks

1. **范围、身份与交付完整性**
   - 固定区间、作者提交、Bookkeeper source SHA、一个 delivery commit 和 14 个作者路径可复现；产品变更路径全部在 Implementer Allowed Files。
   - 28/27 号 dispatch、revision 45 status、server/provider/scheduler/live client/preflight/requirements/schema 均无作者 diff。Review 必须基于固定 SHA，不使用 moving HEAD。

2. **D17 人工启动边界**
   - 仅 smooth open create 原子落 `paused + awaiting_manual_start`；响应可启动，且 create 不启动 worker、provider refs、gate、attempt 或 dispatch。恢复流程不会领取未首次启动的 paused 卡。
   - `成交1次` 在首次 Start 前返回 `409 start_required`，不能绕过 Human；`post_start → worker` 是唯一入口，D16 顺序仍为杠杆设置成功后再订阅/open gate/evaluate/prepare/dispatch，且不会形成重复 worker。
   - create 阶段首次 preflight、固化身份/数量/route、regular-spot forward 预划转仍在原位置且 Start 不重复；immediate create 仍 running，close 与既有 paused-create 语义不被误改。

3. **D18 页面真实接线**
   - smooth threshold 在所有状态的基础信息中保留；连接状态、正反向开单率、两腿价量、覆盖率、gate 轮次/倒计时只在 `status=running` 渲染。
   - paused/done/stopped/deleted 卡没有动态盘口 DOM，但按钮、错误原因与展开 attempt/腿日志仍保留；running→paused 后共享 2 秒 tick 仍刷新已展开日志。没有新增 timer、前端 gate 计算或 immediate 布局回归。

4. **D19 同次 gate 快照与三种放行原因**
   - market/manual/timeout 的 audit 都来自产生该放行结论的同一次 provider 读取；放行后没有第二次 `latest()`，没有用成交均价反推，raw Decimal/received_at/spread/coverage/pass/无效状态/gate identity 均如实序列化。
   - manual/timeout 在盘口不完整时仍遵循原放行规则；audit 只观察，不重新成为 gate。可选 audit context 不影响 immediate/close 或既有 `AttemptContext` 调用点。

5. **D19 下单前无新增阻塞与计时准确性**
   - gate pass 到两腿各自订单客户端调用前，除既有 `prepare_attempt` 外没有新增 SQL、网络、sleep、同步 print/log 或锁；没有恢复 fresh preflight、二次滑点复核或杠杆设置。
   - monotonic 相对时间与 wall-clock 事件时间用途分离；service、prepare、executor、两线程、两腿各自 call-start/call-return、thread complete、join/return 边界齐全，差值计算无串腿、共享可变嵌套字典竞态、负值掩盖或单位错配。
   - `order_client_call_started` 位于凭证/route 确认后、真实 `post_*_order` 调用前，只声称客户端调用开始；UM confirm/query 不被混进“开始下单”耗时。两腿仍并发，慢 spot 不阻止 perp 进入客户端调用。

6. **审计持久化、读取契约与失败隔离**
   - `smooth_dispatch_audit` 仅在 executor 返回后 best-effort 写既有 log；写失败不改变 dispatch verdict、raw persistence、resolve/query/settlement、次数、任务状态或单腿处置。
   - `list_logs_for_task_kind` 是参数化、task+kind 窄查询，排序稳定，不改 schema/gate/状态。task-id GET additive `smooth_dispatch_audits` 对旧/未放行任务为 `[]`，Decimal 为字符串。
   - audit 不泄露 API key、signature、完整私有 URL、凭证或私有原始响应；immediate/close 不写 smooth audit。`docs/api/public-market-contract.md` 与实际 API 一致。

7. **测试质量与独立复跑**
   - 逐项确认测试在错误实现时会变红：create auto-worker、fill-once 绕过、Start 重划转、non-running 动态块、日志停刷、二次 latest、POST 前 audit SQL、append 异常改业务、两腿串行、UM confirm 错计、immediate 被波及。
   - 至少独立复跑：

```bash
.venv/bin/python -m pytest backend/tests/test_smooth_api.py \
  backend/tests/test_smooth_gate_worker.py backend/tests/test_live_hedge_executor.py \
  backend/tests/test_hedge_service.py backend/tests/test_frontend_field_binding.py -q
.venv/bin/python -m pytest backend/tests/test_hedge_store.py backend/tests/test_hedge_api.py \
  backend/tests/test_hedge_task_local.py backend/tests/test_hedge_review2_regressions.py \
  backend/tests/test_hedge_leverage.py backend/tests/test_hedge_cycle_core.py \
  backend/tests/test_hedge_cycle_close.py backend/tests/test_hedge_purity.py -q
node frontend/self-check.js
git diff --check a55a673664ee3cf6b2a177774d7ba40890a2d4b3..bba31ea519c9831b38256918d8854f4c20d58aad
```

   - 可按风险决定是否复跑全后端。Bookkeeper 已复跑为 `1890 passed, 1 failed`；唯一失败的 `public_ip_service.py:47` 由 `git blame` 固定到基线前 `73f525d4` 且本区间零 diff。若确认该证据，分类 `pre-existing-independent`，不单独导致 REWORK；若发现不同失败或归因不成立，必须报告。

8. **Verdict、发现分类与交接**
   - 按 `AGENTS.md` §1/§8 对每条发现提供当前证据、实际影响和 `in-range | pre-existing-independent | pre-existing-release-critical` 分类；风格偏好、无证据假设或 Human 已接受的 L1/L2/L3 不得判 REWORK。
   - 任一 in-range 资金/订单、并发、契约、接线或关键测试缺口 → `REWORK`，给最小可执行修复要求。无 in-range 阻塞 → `ACCEPT`；观察可记录但不得扩张交付。
   - 创建唯一 handoff，包含 immutable Source Report、Required Reading、Human Brief、marker；reviewer `delivery_sha` 必须写固定 `bba31ea...`，不得写 pending。Human Brief 返回合规 `[TASK_RESULT v2]` 以及正式评审闭合字段。

# Stop

完成固定区间 Review-1、必要测试、唯一 handoff 和明确 verdict 后停止。不得自行修代码、改状态、启动下一个 Reviewer、安装/卸载依赖、联网、读取凭证、控制服务、改 Start gate、创建真实任务、下单、commit、push、merge、部署或实盘。

`ACCEPT` 只允许 Bookkeeper 核验后向 Human 汇报是否可以重启继续页面复验；当前未授权重启。页面复验后仍须 fresh Review-2。`REWORK` 返回 Bookkeeper，由 Human 已允许的修复流程处理。
