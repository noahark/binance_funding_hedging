# Identity

- task_id: `smooth-open-v1-f1-review-1-kimi`
- target_role: `Reviewer`
- target_model: `kimi`
- provider: `moonshot`
- status_revision: `39`
- required_skill: `agents/skills/code-reviewer.md`

# Goal

在 fresh Kimi 会话中，对平滑开单 V1 的 F1 修复执行独立 Review-1。固定审查区间为 `e74f3d5cf20f9f980ef023ed35a9c40ff3b8b174..5d65a96b8c0435297c1511c228cec9a6d38df4b8`；其中 `14d8029` 是 dispatch/status 控制上下文，产品修复主体为 `5d65a96`。实现者为 `gpt-5.6-sol`（provider `openai`），本 Reviewer 为 fresh `kimi`（provider `moonshot`），满足跨 provider 与非作者隔离。

只裁定 Grok Review-2 F1 是否被正确关闭：真实 `BestBidAskProvider` 与 service `_smooth_lock` 的订阅互锁、失败后 worker 异常退出。Human 要求本轮先过 Review-1，再安装 ccxt 并做页面验收；不得用此前 Kimi 对旧交付的 Review-1 `ACCEPT` 替代本轮独立审查。

Human 已接受且本轮冻结 L1/L2/L3、D15/D16 与其他既有发布限制；不得顺手把它们重新判为本轮 F1 返工。Review-1 只读，不授权安装 ccxt、联网、控制服务、读取凭证、创建任务、下单、commit、push、merge、部署或实盘。

# Allowed Files

- `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-f1-review-1-kimi.handoff.md`（唯一允许写入；create-only）

除此之外完全只读。不得修改产品代码、测试、既有 evidence、dispatch、`status.json`、`ACTIVE.json`、`PROJECT_STATE.md` 或 `.venv/`，不得调用其他模型。

Bookkeeper create-only 预检：

```text
test ! -e reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-f1-review-1-kimi.handoff.md
exit 0（路径不存在，可由本 Review-1 创建）
```

# Inputs

严格按顺序读取：

1. `AGENTS.md`
2. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/25-smooth-open-v1-f1-review-1-kimi.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json`，核对 revision `39`、本 task 与固定 SHA
6. `agents/roles.md` 的 Shared Rules、Task Handoff Evidence Contract、Reviewer/Review-1 段
7. `agents/skills/code-reviewer.md`
8. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-fix-review-2-grok46.handoff.md`，读取 F1 原始证据、修复要求与 Bookkeeper `verified-rework`
9. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-f1-fix-gpt56sol-xhigh.handoff.md`，实现声明只作待验证输入，以 Bookkeeper Verification 固定提交
10. 用固定 SHA 的 `git diff`/`git show` 完整阅读 `backend/hedge_open_tasks/service.py`、`backend/tests/test_smooth_gate_worker.py`；按需只读 `backend/services/best_bid_ask_provider.py` 的 subscribe/release/watch/notify 生命周期、store pause/gate 清理与 worker 退出路径

启动必须核对 handoff 不存在、工作树只有本 Reviewer 创建 handoff 前应为干净、`.venv` 中 ccxt 未安装。不得用移动 HEAD 代替固定提交；当前 HEAD 的后续 Bookkeeper 控制提交不属于产品交付。

# Acceptance Checks

1. **F1 根因关闭**：固定 delivery 中，`_ensure_smooth_subscriptions` 不得持 `_smooth_lock` 调用任何 provider `subscribe/release`；真实 provider 首次立即回调不能再造成 5 秒互锁。独立运行真实 `HedgeOpenTaskService + BestBidAskProvider +` 零网络立即 bookTicker 回归，确认 1 秒内两侧 watcher/ref 与 task 登记完成。
2. **并发与引用生命周期**：独立检查两次并发 ensure、部分订阅失败、另一调用先登记、正常 worker 释放等当前代码路径。确认只保留每侧一个有效 ref，无重复登记、泄漏、双释放或异常吞没；发现须给固定代码链或可执行证据，不能只报抽象竞态。
3. **失败收口**：订阅失败必须由 `_wait_for_smooth_gate` 捕获，复用既有 `_pause_task_local/pause_task` 使任务 paused、gate 清空、零 attempt、零 executor dispatch，worker 退出；修复源后 `post_start` 可恢复订阅。中文错误须明确公共盘口订阅失败且未发单。
4. **冻结边界**：验证只改 `service.py` 与 `test_smooth_gate_worker.py`，未触碰 provider/store/domain/server/frontend/executor/preflight/requirements。L1/L2/L3、D15/D16、immediate/close/fill/次数/prepare/dispatch/query/settlement 语义不因本补丁发生变化；这些 Human 接受项不得仅凭旧风险返回 REWORK。
5. **测试质量**：新增测试必须调用真实 provider，不得只用同步 `_Market`；时间断言应能在旧代码稳定变红、在修复后稳定通过，并清理线程/数据库。 independently run F1 三项至少 10 次，检查无偶发失败或残余线程。
6. **回归证据**：独立复跑 worker 专项、专项组合、核心、executor、前端 self-check/字段绑定和全后端。全后端只允许已证实的 `public_ip_service.py` 白名单单一既存失败；任何新增失败阻塞。检查 `git diff --check`、ccxt 未安装及禁止文件零 diff。
7. **范围分类与 verdict**：每条发现按 `AGENTS.md` §8 分类并给证据。无 `in-range` 阻塞则 `ACCEPT`；`REWORK` 必须提供最小可执行修复要求。不得修改代码或把安装/联网缺失冒充代码缺陷。
8. **交接**：创建唯一 handoff，包含完整 Source Report、Required Reading、Human Brief 和 marker；使用固定 SHA；返回合规 `[TASK_RESULT v2]`，明确 `评审结论: ACCEPT（接受） | REWORK（返工）`、`问题记录`、`修复要求`。`ACCEPT` 只允许 Bookkeeper 推进 Human 已授权的依赖安装与页面验收准备，不等于 Review-2、合并、部署或实盘接受。

# Stop

完成独立 Review-1、唯一 handoff 和正式 verdict 后停止。不得修改受审代码/状态、安装依赖、联网、控制服务、读取凭证、创建任务、下单、commit、push、merge、部署或实盘。最后一个非空白输出必须是 `[/TASK_RESULT]`。
