# Identity

- task_id: `smooth-open-v1-fix-review-2-grok46`
- target_role: `Reviewer`
- target_model: `grok-4.6`
- provider: `xai`
- status_revision: `36`
- required_skill: `agents/skills/reality-checker.md`

# Goal

在 fresh Grok 4.6 会话中，对平滑开单 V1 第一轮代码返修执行独立 Review-2。固定审查区间为 `9c333cdb58f38f7d19fa8d42b36379abd07baba8..dfd38a6b71e686caf02475aa7954056d670fcead`。不要转述 Implementer 或 Kimi Review-1；须独立核对 Human 已批准需求、实际代码效果、可执行证据、资金/运行风险与发布准备度，给出明确 `ACCEPT` 或 `REWORK`。

实现与修复作者为 `gpt-5.6-sol`（provider `openai`），本 Reviewer 为 `grok-4.6`（provider `xai`），满足与全部实现/修复作者跨 provider。按 Human 最新决定，本包在启动前取代 revision 35 的 Sonnet 5 Review-2；旧 Sonnet packet 未产生 handoff，不得启动或引用为 verdict。

披露：Grok 4.6 曾参与本阶段更早版本产品设计的只读 advisory，但没有撰写当前返修计划或任何实现/修复代码。Human 明确选择其执行本 Review-2；必须使用 fresh 会话，从固定代码和原始证据独立复核，不能把 advisory 观点当作本轮证据或结论。

Human 已接受且本轮不修 L1（Start OFF/stop 与 reserve→dispatch 竞态）、L2（下一 gate 可能不足完整 5 分钟）、L3（行情表重绘复位未提交 threshold）；必须如实列为发布限制，但不得仅因它们返回 `REWORK`。

本任务不授权修改代码/计划/状态、安装 ccxt、联网验证、服务控制、读取凭证、创建任务、下单、commit、push、merge、部署或实盘。

# Allowed Files

- `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-fix-review-2-grok46.handoff.md`（唯一允许写入；create-only）

除创建上述唯一 handoff 外完全只读。不得修改受审内容、既有 evidence、dispatch、`status.json`、`ACTIVE.json`、`PROJECT_STATE.md`；不得调用其他模型或执行外部动作。

Bookkeeper 已执行 create-only 预检：

```text
test ! -e reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-fix-review-2-grok46.handoff.md
exit 0（路径不存在，可由本复核创建）
```

# Inputs

固定受审区间：

- `base_sha`: `9c333cdb58f38f7d19fa8d42b36379abd07baba8`
- `delivery_sha`: `dfd38a6b71e686caf02475aa7954056d670fcead`
- 区间内 `e369a23` 的 dispatch/status 是控制上下文；产品交付主体为 `dfd38a6`

按以下顺序读取：

1. `AGENTS.md`
2. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/23-smooth-open-v1-fix-review-2-grok46.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json`，核对 revision `36`、本 task_id 与固定 SHA
6. `agents/roles.md` 的 Shared Rules、Task Handoff Evidence Contract、Reviewer/Review-2 段
7. `agents/skills/reality-checker.md`
8. `docs/planning/smooth-open-orders-v1.md` 的 D15、D16、§6.5、§16，以及 Human 冻结的原始平滑开单验收语义
9. `docs/planning/smooth-open-orders-v1-development-checklist.md` 的活动 §12
10. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-repair-plan-review-deepseek-v4-pro-r2.handoff.md`，只作已接受计划与 Human 决策边界
11. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-fix-gpt56sol-xhigh.handoff.md` 与 `smooth-open-v1-fix-review-1-kimi.handoff.md`，只作待独立验证的交付/Review-1 声明，不得替代源码和测试核对
12. 用固定 SHA 的 `git diff`/`git show` 完整阅读 12 个产品/测试文件；按需只读 store、preflight provider、executor、snapshot、server 组合根和相关既有回归，禁止用移动 HEAD 代替固定树

# Acceptance Checks

1. **需求到实际效果**：从用户视角独立证明五项必修真实生效：并发冷启动不会形成假订阅；offline 绝不触达公共 WS；合法超长阈值被接受而非法格式拒绝；持续故障不自旋且可及时关闭；暂停/删除/终态但仍存在且展开的任务日志继续刷新。不能只看测试名或计划文字。
2. **成交关键路径**：独立追踪 market/manual/timeout 三种放行，从 WebSocket 评估到真实两腿提交。确认 smooth 首轮杠杆设置严格早于订阅/gate/首次滑点，失败时零订阅/零 gate/零 attempt/零订单；放行后不再执行 fresh preflight、杠杆、网络读取或 sleep，只复用固化值，经既有 `prepare_attempt` 原子复核后立即进入原异步两腿链。
3. **资金与次数语义**：确认 create-task 首次 preflight、regular_spot 预划转、缺腿/1000x 拒绝仍在；immediate/close 的 fresh preflight 与杠杆时机未被改变；第 N 轮、`成交1次`、market/manual 竞态、次数硬上限、查单/结算/单腿暂停没有旁路或多单风险。若代码证据与 Human 接受的 D15 代价冲突，按实际效果裁定。
4. **provider 真实生命周期**：从线程、event loop、ready、future、state/refcount、release、cancel、close/join 全链检查并发/异常时序。重点判断修复是否引入死锁、5 秒卡死、引用泄漏、watcher 未取消、旧 generation 冒充 fresh 或通知风暴；只有满足 `AGENTS.md` §1 的当前证据才能据此阻塞。
5. **前端真实体验**：任务卡原有字段、错误原因和日志按钮未丢；动态盘口与日志刷新复用唯一 2 秒 tick；收起/任务消失停止；没有新增 timer；L3 仍是已接受限制且未被误修。确认测试验证实际 DOM/函数调用条件，不是只匹配字符串。
6. **故障与重启行为**：区分已修缺陷、L1/L2/L3 接受限制和既有运行特性。明确说明：停机时间仍计入 5 分钟、过期 gate 恢复可能 timeout；D16 首轮未调度重启可幂等设杠杆；没装 ccxt 时 smooth 创建 400 且其他功能不受影响。不要把明确接受的风险重新判返工。
7. **证据独立性**：至少独立复跑专项、核心、executor、前端 self-check/字段绑定；可按风险补充或复跑全后端。唯一白名单失败只有在 `public_ip_service.py` 与测试相对 base 零 diff、引入提交早于 base 时才分类 `pre-existing-independent`；任何新失败阻塞。检查禁止文件、ccxt 未安装与固定提交证据，不采信作者摘要。
8. **发布准备度分层**：分别裁定“代码可进入 Human 合并决策”“可安装生产依赖”“可重启加载”“可做真实公共 WS 验证”“可创建首个真实平滑任务”。后四项仍须 Human 单独授权，且缺少真实 BestBidAskProvider 公共 WS 连通证据不能被离线测试冒充。给出最小上线前/上线后观察项与回退边界，但不得执行动作。
9. **阶段活文档**：指出本交付收尾时需同步的 `docs/` 活文档与 `PROJECT_STATE.md` 事实，由 Bookkeeper 在 stage completion 承担；只有文档缺失会导致当前操作安全误导时才可阻塞，不要让纯收尾文档工作替代代码 verdict。
10. 每条发现按 `AGENTS.md` §8 分为 `in-range`、`pre-existing-independent` 或 `pre-existing-release-critical` 并附证据。新假设场景满足 §1 Scenario Admission。L1/L2/L3 只能作为 Human 接受限制报告。无 `in-range` 阻塞则 `ACCEPT`；`REWORK` 必须给出最小可执行修复要求。
11. 创建唯一 handoff，完整 Source Report、Required Reading、Human Brief、marker；使用固定 SHA。返回合规 `[TASK_RESULT v2]`，明确 `评审结论: ACCEPT（接受） | REWORK（返工）`、`问题记录`、`修复要求`。`ACCEPT` 不授权任何发布或实盘动作。

# Stop

完成独立 Review-2、创建唯一 handoff 并返回结果后停止。最后一个非空白输出必须是 `[/TASK_RESULT]`。不得修改受审内容或状态，不得安装依赖、联网、控制服务、读取凭证、创建任务、下单、提交、合并、推送或部署。
