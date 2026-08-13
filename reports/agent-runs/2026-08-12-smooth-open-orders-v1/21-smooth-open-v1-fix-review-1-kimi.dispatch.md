# Identity

- task_id: `smooth-open-v1-fix-review-1-kimi`
- target_role: `Reviewer`
- target_model: `kimi`
- provider: `moonshot`
- status_revision: `34`
- required_skill: `agents/skills/code-reviewer.md`

# Goal

在 fresh Kimi 会话中，对平滑开单 V1 第一轮代码返修做跨 provider Review-1，固定审查 `9c333cdb58f38f7d19fa8d42b36379abd07baba8..dfd38a6b71e686caf02475aa7954056d670fcead`，给出明确 `ACCEPT` 或 `REWORK`。

实现作者为 `gpt-5.6-sol`（provider `openai`），本 Reviewer 为 Kimi（provider `moonshot`），满足跨 provider。Review-1 检查代码、契约、测试与接缝，不重做产品决策。Human 已接受且本轮明确不修 L1（Start OFF/stop 竞态）、L2（下一 gate 可能不足完整 5 分钟）、L3（行情表重绘复位未提交 threshold）；不得以这三项判 `REWORK`。

本任务不授权修改代码/计划/状态、安装 ccxt、联网、控制服务、读取凭证、创建任务、下单、commit、push、merge、部署或实盘。

# Allowed Files

- `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-fix-review-1-kimi.handoff.md`（唯一允许写入；create-only）

除创建上述唯一 handoff 外完全只读。不得修改受审代码、测试、计划、既有 evidence、dispatch、`status.json`、`ACTIVE.json`、`PROJECT_STATE.md`；不得调用其他模型或执行外部动作。

Bookkeeper 已执行 create-only 预检：

```text
test ! -e reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-fix-review-1-kimi.handoff.md
exit 0（路径不存在，可由本复核创建）
```

# Inputs

固定受审区间：

- `base_sha`: `9c333cdb58f38f7d19fa8d42b36379abd07baba8`
- `delivery_sha`: `dfd38a6b71e686caf02475aa7954056d670fcead`
- 主体提交：`dfd38a6b71e686caf02475aa7954056d670fcead`；区间内 `e369a23` 仅为本任务 dispatch/status 控制上下文

严格按顺序读取：

1. `AGENTS.md`
2. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/21-smooth-open-v1-fix-review-1-kimi.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json`，核对 revision `34`、本 task_id 与固定 SHA
6. `agents/roles.md` 的 Shared Rules、Task Handoff Evidence Contract、Reviewer/Review-1 段
7. `agents/skills/code-reviewer.md`
8. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-fix-gpt56sol-xhigh.handoff.md`，以 Bookkeeper Verification 固定 delivery、测试复跑与既存失败裁定为准
9. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-repair-plan-review-deepseek-v4-pro-r2.handoff.md`，读取已通过的返修计划边界
10. `docs/planning/smooth-open-orders-v1.md` 的 D15、D16、§6.5、§16
11. `docs/planning/smooth-open-orders-v1-development-checklist.md` 的活动 §12
12. 用 `git diff 9c333cdb58f38f7d19fa8d42b36379abd07baba8..dfd38a6b71e686caf02475aa7954056d670fcead -- <path>` 逐个通读 12 个受审生产/测试文件的完整 diff；需要理解接缝时用 `git show <固定 SHA>:<path>` 读取完整函数及只读的 `store.py`、preflight provider、snapshot、executor 与相关禁止测试，不得使用移动 HEAD 代替固定树

受审产品文件：

- `backend/services/best_bid_ask_provider.py`
- `backend/hedge_open_tasks/domain.py`
- `backend/hedge_open_tasks/service.py`
- `backend/app/server.py`
- `frontend/index.html`
- `frontend/self-check.js`
- `backend/tests/test_best_bid_ask_provider.py`
- `backend/tests/test_smooth_gate_worker.py`
- `backend/tests/test_smooth_api.py`
- `backend/tests/test_hedge_domain.py`
- `backend/tests/test_frontend_field_binding.py`
- `backend/tests/test_service_health.py`

# Acceptance Checks

1. **范围与回归边界**：确认产品 diff 只含上述 12 个文件，禁止文件零 diff；L1/L2/L3 未被顺手修改。immediate、close、fill-once/fill-all、store gate/次数上限、executor/query/settlement 语义无意外变化。区间内 dispatch/status 是控制上下文，不因其内容对代码交付判阻塞。
2. **并发启动与订阅原子性**：审查 `BestBidAskProvider.start/subscribe/_watch` 的锁、thread/loop/ready/task 生命周期，确保所有并发调用者等待同一个就绪结果，启动失败不留下可见 watcher/ref，单 key 只建一个 watcher，不死锁、不丢异常。审查 `_ensure_smooth_subscriptions` 两侧全成才登记、部分成功 release 回滚、后续可重试，不能留下 timeout 前一直无真实盘口的僵尸订阅。
3. **失败循环与关闭**：异常和无效 snapshot 都有简单固定最小等待且由 cancellation/close 立即打断；无指数退避/重试状态机/新配置；`close()`、release、refcount、线程 join 和 async task 清理没有泄漏或竞态回归。
4. **offline 与 threshold 契约**：offline 必须在组合根零构造 provider/零线程/零订阅，非 offline + 缺 ccxt 的原 400 不变。threshold 对合法正负 30/100 位整数保真并 API 201，`-0/.05` 规范化正确；格式非法才 400，不引入长度上限、科学记数放行、Unicode/空白意外放行或 Decimal context 依赖。
5. **D16 杠杆前移**：live smooth 首轮杠杆在任何 subscribe/gate 恢复或建立/首次行情评估前完成；失败时零订阅、零 gate、零 attempt、零订单并沿用暂停原因；首轮可幂等重试、后续轮次不重复。`_dispatch_one_for_task` 对 smooth 不再设置，但 immediate 与 close 原位置/条件不变。
6. **D15 放行后零联网**：market/manual/timeout 都只读建卡固化 `q_common`、position mode、snapshot/route；不再调用 fresh preflight、杠杆、sleep 或其他联网/等待，再经既有 `prepare_attempt` 原子复核进入原 `_dispatch_live`。核对 frozen route 读取、request 构造、缺字段/坏 snapshot 行为不会无意绕过本地硬门；create-task 初次 preflight、regular_spot 预划转、缺腿/1000x 拒绝和 immediate/close fresh preflight 均保留。
7. **前端日志刷新**：任务存在且展开时，running/paused/deleted/done/stopped 均沿用唯一共享 2 秒 tick 刷新；收起或任务消失才停；没有新增 timer，也没有触碰 L3 的 threshold capture selector。测试必须覆盖真实调用条件，不只是字符串断言。
8. **测试证据**：独立复跑至少专项 250、核心 352、executor 75、frontend self-check + 字段绑定 13，并按风险选择补充测试；全后端可以复跑。唯一已知失败若仍是 `test_private_client.py::test_urlopen_only_in_designated_http_clients` 命中 `public_ip_service.py`，且两文件相对 base 零 diff、引入提交早于 base，则分类 `pre-existing-independent`、不阻塞；任何新失败阻塞。
9. 每条发现按 `AGENTS.md` §8 标注 `in-range` / `pre-existing-independent` / `pre-existing-release-critical` 并附证据。新假设场景须满足 §1 Scenario Admission。若无 `in-range` 阻塞，返回 `ACCEPT`；`REWORK` 必须给出最小、可执行修复要求。不要因为偏好、未来扩展或 L1/L2/L3 判返工。
10. 创建唯一 handoff，完整写 Source Report、Required Reading、Human Brief、marker；使用固定 `base_sha`/`delivery_sha`，返回合规 `[TASK_RESULT v2]` 和明确 `评审结论: ACCEPT（接受） | REWORK（返工）`、`问题记录`、`修复要求`。`ACCEPT` 不授权 Review-2、合并、安装、联网或实盘。

# Stop

完成固定范围 Review-1、创建唯一 handoff 并返回结果后停止。最后一个非空白输出必须是 `[/TASK_RESULT]`。不得修改受审内容或状态，不得启动 Review-2，不得安装依赖、联网、控制服务、读取凭证、创建任务、下单、提交、合并、推送或部署。
