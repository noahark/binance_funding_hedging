# Identity

- task_id: `smooth-open-v1-final-cumulative-review-1-claude-glm`
- target_role: `Reviewer`
- target_model: `claude_glm`
- provider: `zhipu_glm`
- status_revision: `52`
- required_skill: `agents/skills/code-reviewer.md`

# Goal

在全新或 `/clear` 后的 fresh Claude-GLM 会话中，对平滑开单 V1 当前最终产品执行一次**累计正式
Review-1**，弥补 D17–D19 高风险订单改动未被 29 号 Review-1 实际审查的流程缺口，并给出明确
`ACCEPT（接受）` 或 `REWORK（返工）`。

固定累计审查区间：

```text
e955bdd300d214c5c3ad5c1acd629c0d21080165..ad8c6317369e8a643f225cc37f22ad0eb949395b
```

该区间含阶段内 planning、dispatch、status、review evidence 等控制提交；它们只提供上下文，产品
Review-1 聚焦最终 delivery tree 相对原始代码基线的 backend/frontend/requirements/API 契约与测试。
产品实现/修复作者 provider 包括：初始实现及两轮修复 `openai`、D17–D19 修复 `xai`、最终 running
卡刷新修复 `moonshot`。本 Reviewer provider 为 `zhipu_glm`，与全部实现/修复作者不同。

31 号 Claude-GLM Review-1 只审查 `52eb1ab..ad8c631` 的最后一处 Kimi 前端补丁，不能追认其未覆盖的
`bba31ea` D17–D19 订单代码；29 号 Review-1 从未产生 handoff/verdict。必须使用 fresh 会话从累计
固定区间重新审查，不能复用 31 号会话结论。Human 已指定：本累计 Review-1 `ACCEPT` 后，最终
Review-2 由 fresh Opus 5（provider `anthropic`）执行。

Human 已接受并冻结四项限制：设计 §16.1 的 L1/L2/L3，以及实盘观察中“两位开单率等于阈值时页面
没有单独醒目标记”；除非本次固定区间已有证据满足各自重开条件，否则不得以偏好重新判 REWORK。
当前 live 服务已加载产品 delivery `ad8c631`，但本任务只读，不授权访问/控制服务、改 gate、创建
任务、订单、依赖变更、commit、push、merge、部署或实盘。

# Allowed Files

- `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-final-cumulative-review-1-claude-glm.handoff.md`（唯一允许写入；create-only）

除此之外全部只读。不得修改源码、测试、计划、契约、既有 evidence/dispatch、`status.json`、
`ACTIVE.json`、`PROJECT_STATE.md`、`.venv/` 或运行时数据，不得 commit，不得调用其他模型。

Bookkeeper create-only 预检：

```text
test ! -e reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-final-cumulative-review-1-claude-glm.handoff.md
exit 0（路径不存在，可由本 Reviewer 创建）
```

# Inputs

严格按顺序读取：

1. `AGENTS.md`
2. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/32-smooth-open-v1-final-cumulative-review-1-claude-glm.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`，只定位 2026-08-13 smooth live 重启、已接受 L1/L2/L3/两位显示限制、实盘任务及当前发布禁区
5. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json`，核对 revision `52` 与累计固定 SHA
6. `agents/roles.md` 的 Shared Rules、Task Handoff Evidence Contract、Reviewer/Review-1 段
7. `agents/skills/code-reviewer.md`
8. 五份实现者 handoff，按时间读取 Source Report 与 Bookkeeper Verification，但不得把作者结论当审查证据：
   - `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-fullstack-gpt56sol-xhigh.handoff.md`
   - `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-fix-gpt56sol-xhigh.handoff.md`
   - `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-f1-fix-gpt56sol-xhigh.handoff.md`
   - `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-human-validation-fix-grok46.handoff.md`
   - `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-running-cards-refresh-fix-kimi.handoff.md`
9. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-fix-review-2-grok46.handoff.md`，只用其 F1 原始 REWORK 证据核查最终是否关闭
10. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-running-cards-refresh-review-1-claude-glm.handoff.md`，只用其固定范围与 Bookkeeper Verification 理解最后前端补丁证据；不得替代累计审查
11. `docs/planning/smooth-open-orders-v1.md` 的最终 D1–D19、§6、§8–§9、§13、§16–§17
12. `docs/planning/smooth-open-orders-v1-development-checklist.md` 的最终 §12、§15、§17；旧任务拓扑只作历史
13. `docs/api/public-market-contract.md` 的 smooth task、task-id logs、fill-once、fill-all 与 audit 契约
14. 原始固定 diff 与最终产品文件：
   - `git diff --stat e955bdd300d214c5c3ad5c1acd629c0d21080165..ad8c6317369e8a643f225cc37f22ad0eb949395b`
   - `git diff --find-renames e955bdd300d214c5c3ad5c1acd629c0d21080165..ad8c6317369e8a643f225cc37f22ad0eb949395b -- backend frontend requirements.txt docs/api/public-market-contract.md docs/planning/smooth-open-orders-v1.md docs/planning/smooth-open-orders-v1-development-checklist.md`
   - delivery tree 中上述改动生产文件与测试的完整相关函数

不得扫描其他 stage、私有配置、凭证或运行时数据库；不得联网或触碰 `127.0.0.1:8787`。

# Acceptance Checks

1. **累计范围、作者隔离与最终文件集**
   - 累计 base/delivery 可解析且祖先关系成立；最终产品变更仅落在预期 provider、domain/store/service/executor/server、frontend、requirements、测试与 API/planning 权威。
   - 区分控制提交与产品提交，确认产品作者 provider 为 `openai/xai/moonshot`，Reviewer `zhipu_glm` 非自审。
   - D17–D19 必须独立阅读 `bba31ea` 的实际代码与最终 tree，不能引用 31 号窄 Review-1 代替。

2. **公共盘口 provider 与组合根**
   - spot/swap 两个独立 best-bid/ask watcher，共享 key/引用计数；冷启动所有调用者等待同一 ready，失败回滚 refs/task，订阅/释放不与 service `_smooth_lock` 互锁。
   - 持续异常与无效快照有最小等待、无 CPU 热循环；单侧失败不伪造另一侧；stop/release 生命周期闭合。
   - offline 零构造/零订阅；ccxt 缺失时 smooth create 明确 400、immediate 不受影响；`ccxt==4.5.64` 固定依赖与惰性导入边界一致。

3. **gate 数学、身份和次数安全**
   - signed threshold 支持负数和合法超长整数，最终按冻结两位百分点口径比较且严格 `>`；forward/reverse 取腿与分母正确。
   - 两腿一档数量各自覆盖固化 `q_common` 的至少 80%；invalid/stale/断线 fail-closed，但每轮 5 分钟 timeout 按 Human 决定进入立即链。
   - gate seq、deadline、force 标志持久化；market/manual/timeout 只消费同一个 gate；`成交1次` 只 force 当前轮，不直接下单；达到 target 后不能出现第 N+1 单。
   - running→非 running 的三条实际状态写路径正确清 gate，`_apply_task_counters` 豁免不破坏不变量。

4. **订单路径、D15/D16 与既有执行链**
   - smooth create 保留首次 preflight/固化身份、route、`q_common` 与 regular-spot 预划转；每轮放行后不再执行 fresh 联网 preflight。
   - 首轮杠杆设置发生在 subscribe/open gate/首次评估之前，后续 dispatch 不重复设置；放行至两腿 client call 前除原子 `prepare_attempt` 外无新增网络、sleep 或审计 SQL。
   - 两腿保持并发；原 prepare/dispatch/query/settle/单腿暂停链复用；immediate 与 close 没有被 smooth gate/audit 意外拦截或改义。
   - L1/L2/L3 是 Human 接受限制；只有固定证据满足设计列出的重开条件才可重新阻塞。

5. **D17 人工启动与恢复**
   - smooth open create 为 `paused + awaiting_manual_start`，创建后零 worker/provider refs/gate/attempt/order；recovery 不领取。
   - Start 是首次 worker 入口且保持 D16 顺序；未经 Start 的 fill-once 为 409，不能绕过 Human；Start 不重复 preflight/预划转。
   - immediate create、两段式 close 与既有按钮状态不被误改。

6. **D19 同次快照与延迟审计**
   - market/manual/timeout audit 来自产生放行结论的同一次 provider 读取，放行后没有第二次 `latest()` 或以成交价反推。
   - monotonic 相对时序覆盖 gate、组参、prepare、executor、两线程、两腿 client call start/return、join/return；两腿局部 marks 无共享竞态或串腿。
   - audit 在 executor 返回后 best-effort 落既有 log，失败不改变订单业务；immediate/close 不写 smooth audit，API additive 返回且不泄露凭证。
   - Human 实盘 SHELLUSDT 证据应与代码解释一致：量化 `0.05 == threshold 0.05` 未过，后续同次快照 `0.15` market pass；gate→两腿 client call 约 4.523/4.893ms，两腿 accepted_pair。

7. **任务卡、统一刷新与 Human 接受展示限制**
   - 未 running 的 smooth 卡只显示 threshold/基础字段/按钮/错误/日志，不显示盘口块；running 卡显示真实连接、两方向一档价量、开单率、覆盖率、轮次与等待原因。
   - task tab 的共享 2 秒 tick 先刷新 task list，再刷新“所有 running ∪ 仍存在且 expanded”的去重 task-id 集合；无 mode/task_type/方向特判、无新 timer，页面刷新后 running smooth 不再因空展开状态长期误报 incomplete。
   - 非 running 收起停止，展开继续 drain/settle 日志；running 收起仍更新动态数据。
   - Human 已接受“显示 `+0.05%` 但严格等于阈值仍未通过”的醒目性限制；只验证 wait reason/pass 语义诚实，不要求本轮改 UI 或 gate。

8. **回归、契约与发布边界**
   - 重点验证错误实现会使测试变红：provider 冷启动/互锁/热循环/offline、合法超长 threshold、gate 竞态与次数、D15/D16 顺序、D17 paused-create、D19 二次读/前置 SQL/两腿串行、running 刷新并集。
   - 独立运行：

```bash
.venv/bin/python -m pytest backend/tests/test_best_bid_ask_provider.py \
  backend/tests/test_smooth_gate_store.py backend/tests/test_smooth_gate_worker.py \
  backend/tests/test_smooth_api.py backend/tests/test_hedge_domain.py \
  backend/tests/test_live_hedge_executor.py backend/tests/test_hedge_service.py \
  backend/tests/test_frontend_field_binding.py backend/tests/test_service_health.py -q
.venv/bin/python -m pytest backend/tests/test_hedge_store.py backend/tests/test_hedge_api.py \
  backend/tests/test_hedge_task_local.py backend/tests/test_hedge_review2_regressions.py \
  backend/tests/test_hedge_leverage.py backend/tests/test_hedge_cycle_core.py \
  backend/tests/test_hedge_cycle_close.py backend/tests/test_hedge_purity.py -q
.venv/bin/python -m pytest backend/tests -q
node frontend/self-check.js
git diff --check e955bdd300d214c5c3ad5c1acd629c0d21080165..ad8c6317369e8a643f225cc37f22ad0eb949395b
```

   - 已知全后端 `public_ip_service.py:47` 白名单失败只有在以 Git 证明引入早于累计 base 且本交付零 diff 后，才能分类 `pre-existing-independent`；不同失败或归因不成立必须报告。
   - 核对 API 契约与最终代码一致；Review-1 ACCEPT 不授权合并、push、部署、服务控制或实盘。

9. **发现分类、verdict 与交接**
   - 按 `AGENTS.md` §1/§8 为每条发现提供当前证据、实际影响和
     `in-range | pre-existing-independent | pre-existing-release-critical` 分类；新假设须过 Scenario Admission。
   - 任一累计范围内资金/订单、并发、生命周期、契约、真实接线或关键测试缺口 → `REWORK`，给最小可执行修复要求；无 in-range 阻塞 → `ACCEPT`。
   - 创建唯一 handoff，含 immutable Source Report、Required Reading、Human Brief 与 marker；Reviewer
     `base_sha`/`delivery_sha` 写本包累计固定 SHA，不得写 pending。Human Brief 返回合规
     `[TASK_RESULT v2]` 与正式评审闭合字段。

# Stop

完成累计固定范围 Review-1、必要测试、唯一 handoff和明确 verdict 后停止。不得自行修代码、改状态、
安装/卸载依赖、联网、读取凭证、控制服务、改 Start gate、创建任务、下单、commit、push、merge、部署
或实盘。

`ACCEPT` 返回 Bookkeeper 核验，随后才准备 Human 已指定的 fresh Opus 5 Review-2；`REWORK` 返回
Bookkeeper 处理。不得由本 Reviewer 启动 Opus 5 或把 Review-1 结论冒充 Review-2。
