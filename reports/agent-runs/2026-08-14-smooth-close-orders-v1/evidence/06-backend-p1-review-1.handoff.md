# Task Handoff: 06-backend-p1-review-1

## Source Report (author-only; immutable after task end)
- task_id / role / target model: 06-backend-p1-review-1 / Reviewer / grok-4.6（xai）
- stage_id / created_at: 2026-08-14-smooth-close-orders-v1 / 2026-08-14 22:33:28 CST
- base_sha / delivery_sha: 7d3fe600bffa642fe9353ab5453cd30cff623851 / c4ae93a48a3c9da528e2a023b34d1e766d8a0802

范围：只读审阅固定区间 `7d3fe60..c4ae93a` 的产品交付 `c4ae93a`（区间内 harness 提交为上下文，非受审交付）。对照 r3 设计、`05-backend-p1-spec.md`、实现者 handoff。未移动 HEAD、未改源码/测试、未启动服务、未下单、未划转。实现者 provider 为 `zhipu_glm`，本评审为 `xai`，隔离成立。本评审不是该交付的作者。

评审结论：**REWORK**。一条 in-range 阻塞发现 F1：`post_start` 同步备料在「预检不完整」时没有写入 §2.4 的对应中文暂停原因，HTTP 仍回显「任务首次执行必须点击启动」。其余 C4/C8/C10/C12/C14/C15/C16/C17 与立即平仓原调用点抽函数，静态路径与验收测试对齐。§5.6 已具名接受的并发双划转不再次阻塞。

### 已核对且不构成 REWORK 的部分

- 建卡：解除 smooth open-only；close 无 provider → 400 `smooth_market_unavailable`；轻量建卡落阈值；仅 smooth close `failure_pause_threshold=1`。
- `arm_prepared_close_task`：`WHERE status='paused' AND q_common IS NULL` 一次写入数量与 running；7b 删除注入测试锁住不复活。
- store gate：去掉 open-only，增加 `q_common` 真值谓词；C15 worker 在建门前对 running+空数量 `pause_preflight_incomplete` 并退出，避免空转。
- 方向翻转：`evaluation_direction` 覆盖等待评估、读模型当前列、审计 `eval_direction`、覆盖率随同一次评估；`evaluate_smooth_gate` 未改判定；close 卡 `wait_reason` 仅 service 层替换「开单率」→「平仓率」。
- 平仓闸门五处：`put_close_gate` 唤醒 + 开闸 `ensure_worker`；等待循环关闸清门；dispatch 发单准入；`_worker_round` 关闸清门退出。
- 立即平仓三道门抽到 `_run_close_preparation` 后仍在 `_dispatch_one_for_task` 原位置每轮调用；open immediate 的 fresh preflight 留在 else。
- 并发双启动重复划转：r3 §5.6 Human 已具名接受，C14 条件写封住双 running / 复活；本轮不据此再阻塞。

### F1 — 启动备料「预检不完整」不写对应暂停原因（in-range，阻塞）

- 范围：`in-range`（本交付在 `_run_close_preparation` + `_start_smooth_close` 引入；立即平仓旧路径靠 worker 收到 `SIGNAL_PREFLIGHT_INCOMPLETE` 后再 `_pause_preflight_incomplete`，启动路径没有这第二步）。
- 证据锚点：
  1. `backend/hedge_open_tasks/service.py::_run_close_preparation`：`fresh is None or not fresh.ok` 且非 fatal 时只调用 `_record_preflight_incomplete`（写 event，不改 `pause_reason`），返回 `SIGNAL_PREFLIGHT_INCOMPLETE`。
  2. 同文件 `_start_smooth_close`：`prep_signal is not None` 时直接 `HedgeError(409, smooth_close_start_failed, current.pause_reason_zh or 通用句)`，**不**调用 `_pause_preflight_incomplete` / `_pause_task_local`。
  3. 建卡后 `pause_reason` 仍是 `awaiting_manual_start`（`任务首次执行必须点击启动`）。
  4. 对比：同函数对 UM / 现货划转失败会 `_pause_task_local`，故 `test_post_start_failure_pauses_with_chinese_reason_no_worker` 只覆盖了已暂停的那一支，预检不完整未被锁住。
  5. 只读复现（交付代码、fake provider `get_snapshot→None`、`last_failed_read=spot_filters`）：`post_start` → HTTP `409 smooth_close_start_failed` detail=`任务首次执行必须点击启动`；事后 `status=paused`、`pause_reason=awaiting_manual_start`、`q_common=None`、无 worker、无 attempt。
- 实际影响：实盘启动时预检读失败（网络/过滤器/价格）是三道门的第一道。人已经点了启动，卡片和弹窗却说「必须点击启动」，看不到「预检数据不完整（spot_filters）…」。C6 把失败展示绑在既有暂停原因上，这一支落空。不发单（fail-closed 的资金面仍在），但验收 7 / spec 3.3.8 / 设计 §2.4 要求的「对应中文原因」失败。
- 为何必须本轮修：不是偏好；是本交付新启动链相对立即平仓 worker 收口的遗漏，且现有测试全绿会掩盖。

fatal 预检走 `_stop_task_fatal_preflight`（paused 可命中），卡片能看到 `stop_reason`；HTTP 仍可能误用旧 `pause_reason_zh`。修复 F1 时一并让 HTTP 带上权威中文，但不另开第二条发现。

### 观察（不阻塞、不进 Human 摘要）

- 验收 7b 写的「注入 post_pause」在首次启动时任务本就是 paused，`arm_prepared_close_task` 谓词仍会命中；取消启动的有效注入是 `post_delete`（测试已覆盖）。不是资金缺口。
- 无 provider 时 400 文案从「平滑开单…立即开单」改成「平滑开平仓…立即开单/立即平仓」，open 共享该字符串。行为与错误码未变。
- `open_smooth_gate` 的有效性判断是 Python 真值（`not task["q_common"]`），不是 `Decimal>0`。正常写入路径是 `fmt_decimal` 正数；与 C15 worker 的 `not task.get("q_common")` 一致。

### Required Reading for the Next Task
- 读取路径及顺序：reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/06-backend-p1-review-1.handoff.md；docs/planning/smooth-close-orders-v1.md；reports/agent-runs/2026-08-14-smooth-close-orders-v1/05-backend-p1-spec.md；backend/hedge_open_tasks/service.py
- 执行：Bookkeeper 核验本 handoff 为 REWORK；原实现者按下方修复要求做最小修复并补测
- 关卡：修复提交后重新 Review-1；通过前不得派发 Review-2 / P2 / 联调
- 不能假设的事实：未启动服务、无实盘证据；§5.6 并发双划转已被 Human 接受；不得借修复扩大范围（不加互斥、不改立即平仓每轮三道门、不改 L1–L3）

## Human Brief / Console Receipt Source (author-only; immutable after task end)
[TASK_RESULT v2]
任务 ID: 06-backend-p1-review-1
执行结果: completed（完成）
结果摘要: Review-1 结论 REWORK。启动同步备料在预检读失败时不写「预检数据不完整」暂停原因，弹窗仍说「必须点击启动」；只读复现已钉死。其余备料条件写、闸门、方向翻转、C15 退出与立即平仓每轮三道门静态对齐。并发双划转按 §5.6 不阻断。
产物: [reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/06-backend-p1-review-1.handoff.md]
检查结果: [pass：区间 7d3fe60..c4ae93a 与 isolation；pass：只读未改源码/HEAD；fail：F1 预检不完整启动原因（验收 7 / spec 8 / §2.4）；pass：C14 条件写与 7b 不复活；pass：C15 空数量暂停且不忙循环；pass：C12 五处闸门接线；pass：方向翻转与立即平仓原调用点；pass：§5.6 已接受风险不重开]
阻塞项: [F1：_start_smooth_close 对 SIGNAL_PREFLIGHT_INCOMPLETE 必须先 _pause_preflight_incomplete 再返回 HTTP，detail 用新写入的中文原因；补测 get_snapshot=None 不得再回显 awaiting_manual_start]
本地北京时间: 2026-08-14 22:33:28 CST
下一步模型: gemini-3.1-pro（Bookkeeper，核验本 REWORK）
下一步任务: 读取：reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/06-backend-p1-review-1.handoff.md；docs/planning/smooth-close-orders-v1.md；reports/agent-runs/2026-08-14-smooth-close-orders-v1/05-backend-p1-spec.md；backend/hedge_open_tasks/service.py；执行：核验 REWORK 并准备原实现者最小修复 dispatch；关卡：修复后重新 Review-1，通过前不派发 Review-2/P2/联调
评审结论: REWORK（返工）
问题记录: reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/06-backend-p1-review-1.handoff.md
修复要求: reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/06-backend-p1-review-1.handoff.md
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)
- source_sha256: 0ec492e4427702a6399b96965cf578f14730e6e604626e7075ef9293a7d91302
- 核验时间: 2026-08-14 22:45:00 CST
- 核对 status revision: 9
- 依据: Review-1 handoff 格式合规且结论明确为 REWORK。阻塞发现 F1 符合 Scenario Admission 要求（附带静态路径证据，确认属于 in-range 的启动备料遗漏）。未借修复扩大范围或引入被 Human 接受的风险。
- 后续状态: 验证通过（verified）。依规推进状态，按 AGENTS.md §8 递增 rework_count，并向原实现者（GLM / zhipu_glm）派发第一轮最小修复任务 07-backend-p1-repair-1。

## Errata (append-only)
