# 评审任务：Review-1 传输层异常证据保全 + 移除 dry-run 假成交模式（03 交付）

阶段：`2026-08-06-hedge-order-close-validation`（验证下单/平仓核心链路 + 修复小 bug）
status.json：`reports/agent-runs/2026-08-06-hedge-order-close-validation/status.json`

背景：本 stage 三个实现任务（01 SPOT_ONLY 路由修复 / 02 set-leverage / 03 传输层证据 +
移除 dry-run 假成交）经 Human 决定**一次性提交**为交付区间
`f153cdc..ee7ec4f`（`git rev-parse` 直取；HEAD 即 `ee7ec4f`）。本评审**聚焦 03
交付**（THE 实盘事件 A/B 两项缺陷修复），01/02 改动在同一提交内，作为同批交付一并核对
但不作为评审主体。

## Identity

- task_id: `2026-08-06-hedge-order-close-validation-review1-transport-evidence-drop-dryrun`
- target_role: `Reviewer`
- target_model: `opus5`（Human 指定；provider=anthropic，与实现作者 deepseek 隔离）
- provider: 按 `agents/roles.md` 模型映射
- status_revision: 4
- required_skill: `agents/skills/code-reviewer.md`

## Goal

对 committed `base_sha..delivery_sha` = `f153cdc..ee7ec4f` 做 review-1：检查代码正确性、
契约、测试、集成接缝。**评审主体是 03 交付**：

### A. 传输层异常证据保全
- A-1 `_send` 三分支（TimeoutError / URLError / 其他）保留异常类型 + 消息，
  格式 `"<分类>:<ExcType>: <msg>"`；分类词仍是前缀；长度 ≤200；脱敏（含 `http`/`?`
  只留类型名）；`HedgeHttpResponse` 字段与 DB schema 未动。
- A-2 `_error_leg` 用 `exc` 构造 raw dict（`leg_send_exception` 分类）并接线
  `raw_response`，异常不再静默；`_run` except 加 `[HEDGE_LEG]` stderr 日志；
  控制流不变（仍 `LEG_UNKNOWN_QUERYING`，绝不重发）。

### B. 移除 dry-run 下单/成交模式
- B-1 `RecordTransportExecutor` 移出生产（默认 `DisabledHedgeExecutor` 零成交；
  `_dispatch_simulated` 只写 `ATTEMPT_DISABLED` + `filled_qty=0`）；生产代码
  grep 无 `RecordTransport`。
- B-2 测试迁移 `backend/tests/fakes.py`（`RecordTransportFake` 逐字搬运）；
  7 个测试文件 import 改指；断言变动逐条有理由；覆盖一条不减。
- B-3 历史 4 笔假成交清理（`scripts/clean-dryrun-fake-fills.py`）：备份 + 前后
  对账 `spot_qty 800→400` / `perp_qty 600→200` / `position_qty -600→-200`；
  attempt 6/7 零改动。
- B-4 disabled 模式启动醒目 stderr 警告（`server.py`）。

## Allowed Files

只读（评审不改任何代码、证据、`status.json`、提交）：

- `reports/agent-runs/2026-08-06-hedge-order-close-validation/status.json`
- `reports/agent-runs/2026-08-06-hedge-order-close-validation/03-transport-evidence-and-drop-dryrun.dispatch.md`
- `reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/2026-08-06-hedge-order-close-validation-transport-evidence-drop-dryrun.handoff.md`
- `reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/2026-08-06-hedge-order-close-validation-dryclean.audit.json`
- `reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/2026-08-06-hedge-order-close-validation-the-single-leg-dryrun-diagnosis.md`
- `reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/2026-08-06-hedge-order-close-validation-glm-diagnosis-crosscheck.md`
- `backend/hedge_open_tasks/executor.py`
- `backend/hedge_open_tasks/__init__.py`
- `backend/hedge_open_tasks/service.py`（:481 默认执行器、`_dispatch_simulated`）
- `backend/services/hedge_open_live_client.py`（`_transport_error_text`、`_send`）
- `backend/services/live_hedge_executor.py`（`_error_leg`、`_run`）
- `backend/services/hedge_preflight_provider.py`（仅注释改动核对）
- `backend/app/server.py`（disabled 警告）
- `backend/tests/fakes.py`
- `scripts/clean-dryrun-fake-fills.py`

评审完成后**创建唯一写**（Task Handoff Evidence Contract 的 create-only 例外）：
`reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/2026-08-06-hedge-order-close-validation-review1-transport-evidence-drop-dryrun.handoff.md`
（Bookkeeper 预检 `test ! -e` 通过，路径不存在；已存在则任务失败）。

禁止：修改任何交付代码/测试/证据、改 `status.json`、提交、移动 HEAD、
对实盘发单/划转/设杠杆、访问凭证。

## Inputs

按 `AGENTS.md` §4 顺序读取：

1. `AGENTS.md`
2. 本 dispatch
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-06-hedge-order-close-validation/status.json`
6. `agents/roles.md` 的 `Reviewer` 段 + `Task Handoff Evidence Contract` 段
7. `agents/skills/code-reviewer.md`
8. `reports/agent-runs/2026-08-06-hedge-order-close-validation/03-transport-evidence-and-drop-dryrun.dispatch.md`（验收基线）
9. 03 handoff + `dryclean.audit.json` + 两份取证报告（背景事实）
10. 按需读 Allowed Files 中的代码文件

评审区间：`git rev-parse f153cdc` 与 `git rev-parse ee7ec4f` 直取核对；diff 用
`git diff f153cdc..ee7ec4f`（或 `git show ee7ec4f`）。本区间含 01/02 同批提交，
针对它们的发现按 `AGENTS.md` §8 范围三分类标注。

## Acceptance Checks

1. **A-1 契约**：`_send` 三分支 `transport_error` 均为 `<分类>:<ExcType>: <msg>`、
   分类词在最前、长度 ≤200；脱敏负路径（含 `http`/`?` 只留类型名）正确；
   `HedgeHttpResponse` 字段与 DB schema 未变；落库通路（`_raw_response_dict` →
   `hedge_open_raw_response.transport_error`）未破坏。
2. **A-2 契约**：`_error_leg` 的 raw dict 形状与 `_raw_response_dict` 一致、
   分类 `leg_send_exception`、`exc is None` 时 `unknown`；`raw_response` 已设
   （不再被 `if raw is None: return` 跳过）；`dispatch_state` 仍
   `LEG_UNKNOWN_QUERYING`；`_run` except 有 stderr 日志。
3. **B-1 纯度**：`backend/hedge_open_tasks/` + `backend/services/` grep 无
   `RecordTransport`（评审者自行复跑 `grep -rn` 验证）；`service.py:481` 默认
   `DisabledHedgeExecutor`；非 live 模式不产生 `filled_qty>0` 的 leg 行。
4. **B-2 覆盖**：7 个测试文件 import 均指向 `backend.tests.fakes`；断言变动与
   handoff 说明逐条对应；单腿暴露/连续失败暂停/qty_mismatch 等端到端场景一条未删。
5. **B-3 对账**：audit 前后计数与 `before/after` 位置数据自洽；备份路径存在；
   attempt 6/7 数据前后计数一致；脚本逻辑（dry-run 默认、`--apply` 先备份、
   写前核验 dry 前缀、单事务）无破坏性缺陷。
6. **B-4**：disabled 模式启动打醒目警告；live 分支未受影响。
7. **测试**：评审者可不重跑全量（Bookkeeper 已实测 1446 passed + self-check 全绿），
   但须核对测试断言与实现一致；若发现测试与实现不符须记录。
8. **范围**：交付 diff 无 03 范围外改动（01/02/frontend 提前量检测为 Human 决定
   同批提交，不算越界）；无未授权提交/实盘写。
9. 输出 `[TASK_RESULT v2]` 含 `评审结论: ACCEPT（接受）| REWORK（返工）`、
   `问题记录`、`修复要求`；每条 `REWORK` 发现按 `AGENTS.md` §8 范围三分类标注
   （`in-range` / `pre-existing-independent` / `pre-existing-release-critical`）。

## Stop

按 `AGENTS.md` §7 返回完整中文 `[TASK_RESULT v2]`（含三行中文交接 + 评审闭线字段），
先完成唯一 handoff 创建，再以其中 Human Brief 生成控制台回执。`下一步任务` 用
可执行形式 `读取：<路径或 none>；执行：<立即动作>；关卡：<下一验证>`。

下一关卡：review-1 结论返回 Bookkeeper（deepseek）核验；`ACCEPT` 后由 Human 决定
是否 review-2 与实盘复测（面板 400/200 + disabled 无假成交）。
