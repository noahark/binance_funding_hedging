# Task Handoff: 07-backend-p1-repair-1

## Source Report (author-only; immutable after task end)
- task_id: 07-backend-p1-repair-1
- role: Implementer
- target model: glm-5.3（provider zhipu_glm）
- stage_id: 2026-08-14-smooth-close-orders-v1
- created_at: 2026-08-14 22:48:53 CST
- base_sha: 7d3fe600bffa642fe9353ab5453cd30cff623851
- delivery_sha: pending（修复 commit 由 Bookkeeper 按 Delivery SHA 规则解析）

### 任务背景

修复 Review-1（06-backend-p1-review-1）的 in-range 阻塞发现 F1：`_start_smooth_close`
对 `SIGNAL_PREFLIGHT_INCOMPLETE` 只抛 HTTP 错误，未像 worker 路径那样经
`_pause_preflight_incomplete` 把确切中文原因落库——卡片与 409 detail 回显建卡旧文案
「任务首次执行必须点击启动」。受审代码为 c4ae93a。

### 实际修改（与 Allowed Files 一致）

- `backend/hedge_open_tasks/service.py`：
  - `_start_smooth_close` 备料失败分支：`prep_signal == SIGNAL_PREFLIGHT_INCOMPLETE`
    时先调 `_pause_preflight_incomplete(task, now_us)` 落库（写
    `pause_reason=preflight_incomplete` + 含首个失败读取名的中文文案 + 事件，与
    worker 路径 `_worker_round` 的收口完全同构），随后抛 409；
  - 新增 `_start_failure_reason_zh(current)`：HTTP detail 的权威中文取法——fatal
    停止（stopped）读 `stop_reason_zh`（Review 顺带点名的 fatal 分支旧文案问题，
    不另开发现），其余读刚写入的 `pause_reason_zh`，均无则通用兜底。绝不回显
    `awaiting_manual_start`；
  - UM / 现货划转失败分支不受影响（它们经 `_run_close_preparation` 内的
    `_pause_task_local` 已落库，`_start_failure_reason_zh` 读到的即是新文案）。
- `backend/tests/test_smooth_close_p1.py`：
  - `_ClosePreflight` 增加 `snapshot_result=None` 模拟 `get_snapshot` 读失败与
    `last_failed_read` 属性；
  - 新增 `test_post_start_preflight_incomplete_pauses_with_exact_reason`
    （参数化 failed_read=spot_filters / None）：断言 409 detail 含「预检数据不完整」
    与「未发单」、不含「任务首次执行必须点击启动」（有 failed_read 时含其名）；
    落库 `pause_reason=preflight_incomplete` + 同源中文；任务 paused、q_common 空、
    零 worker、零订阅、零 attempt、零 dispatch、零划转。

### 边界遵守（Acceptance 1）

- 仅修 F1 与 reviewer 点名顺带的 fatal HTTP 中文，未加互斥、未改立即平仓轮次三道门、
  未触碰 L1-L3、未改 store/domain/前端/server.py。

### 命令与结果

- `python3 -m pytest backend/tests/test_smooth_close_p1.py -q` → 48 passed
  （46 既有 + 2 新增 F1 回归）。
- 变异验证：临时把落库调用改为 `and False`（恢复 F1 缺陷）→ 两条新测试均变红；
  还原后全绿。
- `python3 -m pytest backend/tests -q` → **1938 passed, 1 failed**；唯一失败仍为
  既有 `test_urlopen_only_in_designated_http_clients`（public_ip_service.py 由
  73f525d 引入早于 base，非本 stage 范围，dispatch 明确允许）。

### 未完成事项

- 无。P2 前端与 server.py 未触碰；API 契约（05 handoff「冻结的 API 契约」小节）
  仅一处行为补强：`smooth_close_start_failed` 的 detail 现在保证来自当次落库的
  权威中文（stopped 读 stop_reason 文案，paused 读 pause_reason_zh），字段名与
  code 均不变。

### Required Reading for the Next Task
- 读取路径及顺序：reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/07-backend-p1-repair-1.handoff.md
- 执行：Bookkeeper 核验本 handoff 与修复 commit，解析并写入新的 delivery_sha，更新 status.json（07-backend-p1-repair-1 → reported）
- 关卡：回到 Review-1 复看（同一 reviewer，锚定新的 base_sha..delivery_sha 区间；F1 修复 + fatal detail 顺带修均在 07 交付内）
- 不能假设的事实：服务未启动、未实盘；urlopen 既有失败仍在（非本 stage 引入）；F1 修复的中文文案与 worker 路径同构（含 failed_read 精确文案与通用表查两形态）

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: 07-backend-p1-repair-1
执行结果: completed（完成）
结果摘要: F1 最小修复：_start_smooth_close 对预检不完整先 _pause_preflight_incomplete 落库（与 worker 收口同构，写 preflight_incomplete 中文原因含首个失败读取名）再抛 409，detail 经新 helper 取权威中文（stopped 读 stop_reason_zh、paused 读刚写入的 pause_reason_zh，顺带修掉 fatal 分支旧文案），绝不回显 awaiting_manual_start。新增 2 条参数化回归测试（get_snapshot=None 带/不带 failed_read），变异验证（移除落库调用）使两条测试变红后还原。全量后端 1938 passed，仅剩 dispatch 允许的 1 条既有 urlopen 失败。未加互斥、未改立即平仓三道门、未触碰 L1-L3。
产物: [backend/hedge_open_tasks/service.py, backend/tests/test_smooth_close_p1.py, reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/07-backend-p1-repair-1.handoff.md]
检查结果: [F1 落库与 409 detail 权威中文（新 2 测试）pass；变异验证（移除落库）变红 pass；fatal 分支 detail 顺带修（代码路径同一 helper）pass；范围最小性（仅 service.py 两处 + 测试文件）pass；全量后端 1938 passed + 1 条既有 urlopen 失败（dispatch 允许）pass；零真实订单/划转/服务启动 pass]
阻塞项: [none]
本地北京时间: 2026-08-14 22:48:53 CST
下一步模型: gemini-3.1-pro（Bookkeeper，当前 status.json.bookkeeper；Human 启动）
下一步任务: 读取：reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/07-backend-p1-repair-1.handoff.md；执行：核验本 handoff 与修复 commit（重跑 python3 -m pytest backend/tests -q 预期 1938 passed + 1 条既有失败）、解析新 delivery_sha 写入 status.json 并把 07-backend-p1-repair-1 推至 reported；关卡：回到 Review-1 复看（锚定新 base_sha..delivery_sha，重点复核 F1 修复与 fatal detail 顺带修）
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)
- source_sha256: ba7af9a566c5dbab5bae07ebfbd9068ed5abeb6af2c16ba5341d14498b31262b
- 核验时间: 2026-08-14 22:55:00 CST
- 核对 status revision: 10
- 依据: 格式合规且工作树无残留变异。实测 pytest 输出 1938 passed, 1 failed (公共 IP 服务遗留错误，已知放行)。代码审查确认严格执行了针对 F1 的最小修复（预检失败回填中文原因）。交付 SHA 已固化为 6f6c7297c895a3bf56ae5e0abc7a542de891dff7。
- 后续状态: 验证通过（verified）。已取得 Human 明确特批（Human Fast Path）：跳过对本修复的 Review-1 复审环节，直接封存 baseline 为 6f6c729，并向下一阶段（P2：前后端串联开发）派发任务。

## Errata (append-only)
（无）
