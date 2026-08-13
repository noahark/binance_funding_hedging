# Identity

- task_id: `smooth-open-v1-d17-d19-plan-review-kimi`
- target_role: `Reviewer`
- target_model: `kimi`
- provider: `moonshot`
- status_revision: `43`
- required_skill: `agents/skills/code-reviewer.md`

# Goal

在 fresh Kimi 会话中，对 Human 页面验收后新增的 D17–D19 做一次跨 provider、窄范围、只读计划复核，给出明确 `ACCEPT` 或 `REWORK`。本任务不重审 CCXT/provider/F1 或整个平滑开单 V1，只判断以下返修计划是否最小、可实现、可测，并且没有为了审计反过来增加放行到下单的延迟：

1. smooth 新建为 paused，Human 点击任务卡“启动”后才进入 worker/订阅/gate/订单；
2. 只有 running smooth 卡显示动态盘口，非 running 卡仍保留基础信息和展开 attempt 日志刷新；
3. 用同一次 gate 快照和 monotonic 分段时间解释“放行→两腿各自调用订单客户端”的延迟，不恢复 fresh preflight 或二次滑点复核。

计划增量作者为当前 Codex（provider `openai`）；Reviewer 为 Kimi（provider `moonshot`），满足跨 provider。固定计划区间为 `bae72f6c76545424d90aae97a4f872381bc2c303..fea5e34485750372179aeff36987a5a52dbf68d3`。`bae72f6` 是页面验收事实/状态基线，`fea5e34` 只改两份 planning 文件。

本复核不授权实现、安装/卸载依赖、联网、读取凭证、控制当前服务、改 Start gate、创建任务、下单、commit、push、merge、部署或实盘。当前 127.0.0.1:8787 仍运行旧交付，严禁触碰。

# Allowed Files

- `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-d17-d19-plan-review-kimi.handoff.md`（唯一允许写入；create-only）

除此之外完全只读。不得修改 planning、源码、测试、既有 evidence、dispatch、`status.json`、`ACTIVE.json`、`PROJECT_STATE.md`、`.venv/` 或运行时数据，不得调用其他模型。

Bookkeeper create-only 预检：

```text
test ! -e reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-d17-d19-plan-review-kimi.handoff.md
exit 0
```

# Inputs

严格按顺序读取：

1. `AGENTS.md`
2. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/26-smooth-open-v1-d17-d19-plan-review-kimi.dispatch.md`
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`，只定位首笔 smooth 页面验收事实与当前运行服务禁区
5. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json`，核对 revision `43`、本 task、固定 SHA
6. `agents/roles.md` 的 Shared Rules、Task Handoff Evidence Contract、Reviewer 段
7. `agents/skills/code-reviewer.md`
8. 固定计划增量：
   - `git diff bae72f6c76545424d90aae97a4f872381bc2c303..fea5e34485750372179aeff36987a5a52dbf68d3 -- docs/planning/smooth-open-orders-v1.md docs/planning/smooth-open-orders-v1-development-checklist.md`
   - `git show fea5e34485750372179aeff36987a5a52dbf68d3:docs/planning/smooth-open-orders-v1.md`，重点 D12、D15–D19、§6.5–§6.6、§8、§13、§17
   - `git show fea5e34485750372179aeff36987a5a52dbf68d3:docs/planning/smooth-open-orders-v1-development-checklist.md`，只把 §15–§16 当当前活动权威，§1–§14 是历史
9. 只为核验证据锚点，读取固定 delivery 树中的：
   - `backend/hedge_open_tasks/service.py`：`create_task`、`post_start`、`_require_fillable`、`_smooth_eval`、`_wait_for_smooth_gate`、`_worker_round`、`_dispatch_one_for_task`、`_dispatch_live`、task_id `get_logs`
   - `backend/hedge_open_tasks/domain.py`：`PAUSE_REASON_AWAITING_MANUAL_START` 中文
   - `backend/hedge_open_tasks/executor.py::AttemptContext`
   - `backend/hedge_open_tasks/store.py`：`append_log`、task/log 读方法、`prepare_attempt`
   - `backend/services/live_hedge_executor.py`：`dispatch`、`_send_one_leg`
   - `frontend/index.html`：`startHedgeTask`、`renderSmoothTaskExtras`、`renderHedgeTaskCard`、展开日志共享 tick
   - §15 Allowed Files 中列出的既有相关测试；不得扫描无关历史阶段或运行时数据库

# Acceptance Checks

1. **D17 人工启动边界自洽**：计划是否让 smooth create 原子落 `paused + awaiting_manual_start` 且零 worker/订阅/gate/attempt/order，fill-once 不能绕过首次 Start，recovery 不领取；Start 是否只复用既有 `post_start → worker`，D16 杠杆仍早于订阅/gate。确认 immediate 零改动。特别核对计划是否如实保留 create 阶段既有首次 preflight、身份/数量/route 固化和必要的 regular-spot USDT 预划转，没有把“创建暂停”虚假写成“创建绝对无资金副作用”，也没有无授权把这些动作迁到 Start。
2. **D18 展示与刷新不冲突**：计划是否只在 running 卡渲染动态连接/盘口/覆盖率/gate 块，paused/done/stopped/deleted 卡仍保留 threshold、基础信息、按钮、错误原因和展开日志；D12 的“非 running 但已展开仍刷新在途 attempt/腿日志”必须继续成立。不得新增 timer 或让前端自行计算 gate。
3. **D19 同次快照成立**：审计使用产生 market/manual/timeout 放行结论的同一次 provider 读取；不得放行后再 `latest()`、不得用成交均价反推放行盘口。market/manual/timeout 都应有 direction、threshold、两腿 raw Decimal 一档/接收时间、spread/coverage/pass 与 gate identity；无效快照必须以 null/状态如实表示。
4. **时间边界能回答 Human 问题**：monotonic 分段至少覆盖 gate→service dispatch、组参、prepare SQL、executor、两线程启动、两腿各自 `post_*_order` 客户端调用前/返回后、线程/join/executor return；wall clock 只用于事件时刻。字段不得宣称已经发出网络包，只能叫 order-client call started。UM confirm/query 不得混入“开始下单”的数值。
5. **审计无侵入且 fail-open 于观测**：放行到两腿订单客户端调用之前，除原 `prepare_attempt` 外不得新增 SQL、网络、sleep、print 或锁；audit 必须在 executor 返回后才 best-effort append 到既有 `hedge_open_log`，写失败不改变订单 verdict、resolve、次数、状态或单腿处置。不得新 schema、新端点、新 watcher、新状态机，immediate/close 不生成 smooth audit。
6. **Allowed Files 与验收足够**：核对 §15 文件联集足以把可选 audit context 传到真实 executor、读取按 task+kind 的既有 log、更新 additive API 字段和 running-only DOM；无需 `server.py`/live client/provider/preflight/scheduler。测试必须能在二次读盘口、POST 前审计 SQL、串行两腿、错计 confirm GET、audit 写失败改变业务、或 immediate 被波及时稳定变红。
7. **冻结语义未重开**：D15 删除每轮 fresh preflight、D16 杠杆前移、两腿并发、prepare 原子门、查单/结算/单腿链、L1/L2/L3 接受限制保持不变。Reviewer 不得以要求恢复二次滑点复核或修 L1/L2/L3 判 REWORK；若发现计划确实会改这些语义，须给固定代码链和最小修复要求。
8. **Verdict 与交接**：每条发现按 `AGENTS.md` §8 分类并给当前证据。无 in-range 阻塞则 `ACCEPT`；`REWORK` 只针对 §15–§16 的可执行缺口。创建唯一 handoff，包含 Source Report、Required Reading、Human Brief 与 marker，固定 SHA 不得用 moving HEAD。返回合规 `[TASK_RESULT v2]`，明确评审结论、问题记录、修复要求。

# Stop

完成窄计划复核、唯一 handoff 和正式 verdict 后停止。`ACCEPT` 只允许 Bookkeeper 准备原 gpt-5.6-sol/xhigh Implementer 的修复 dispatch，不授权任何代码、环境、服务、资金或发布动作。最后一个非空白输出必须是 `[/TASK_RESULT]`。
