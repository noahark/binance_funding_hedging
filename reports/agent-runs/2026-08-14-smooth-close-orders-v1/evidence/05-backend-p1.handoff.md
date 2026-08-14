# Task Handoff: 05-backend-p1

## Source Report (author-only; immutable after task end)
- task_id: 05-backend-p1
- role: Implementer
- target model: glm-5.3（provider zhipu_glm）
- stage_id: 2026-08-14-smooth-close-orders-v1
- created_at: 2026-08-14 21:55:42 CST
- base_sha: 7d3fe600bffa642fe9353ab5453cd30cff623851
- delivery_sha: pending（交付 commit 由 Bookkeeper 按 Delivery SHA 规则解析）

### 任务背景与依据

按 dispatch 与 `05-backend-p1-spec.md`（22 条实现项）实现平滑平仓 V1 后端 P1。需求权威
为 `docs/planning/smooth-close-orders-v1.md` r3（第三次跨 provider 计划评审 ACCEPT）。全部
测试使用 fake clock / fake market provider / record executor，未发出任何真实订单或划转，
未启动服务，未连接真实交易所。

### 实际修改范围（与 Allowed Files 一致）

- `backend/hedge_open_tasks/domain.py`：新增纯函数 `evaluation_direction(task)`（C16 方向
  翻转：close 取反，open 原样）。仅此一处新增，`evaluate_smooth_gate` 一行未改。
- `backend/hedge_open_tasks/store.py`：
  - `open_smooth_gate` / `force_smooth_gate` 解除 `task_type == open` 硬条件（C10），同时
    增加 `q_common` 有效谓词（C15）；
  - 新增窄方法 `arm_prepared_close_task`（C14 一次条件写，语义等价
    `WHERE id=? AND status='paused' AND q_common IS NULL`，命中才写 q_common /
    position_side_mode / preflight_snapshot 并置 running）与 `resume_paused_task`
    （C4：q_common 已有的 paused 任务仅带 paused 谓词置 running）。
- `backend/hedge_open_tasks/service.py`：
  - 建卡（C6/C8）：解除 `mode=smooth` open-only；smooth close 同样要求公共盘口 provider，
    否则 400 `smooth_market_unavailable`；close 轻量建卡分支落
    `slippage_threshold_pct`；仅 smooth close `failure_pause_threshold=1`；
  - 备料抽函数（C4/C5）：`_run_close_preparation(task, now_us)` 封装三道门
    （fresh preflight → `_close_um_position_error` → `_ensure_close_spot_balance`），
    失败处置（fatal 停止 / preflight_incomplete / 两条 close 门暂停）逐行等价搬移；
    立即平仓仍在 `_dispatch_one_for_task` 原调用点、每一轮执行（open immediate 的
    fresh preflight 代码原样保留在 else 分支，行为零 diff）；
  - 启动接口（C5/C13/C14）：`post_start` 对 smooth+close 分流到
    `_start_smooth_close`（闸门校验 → 同步备料 → 一次条件写），未命中经
    `_resolve_smooth_close_start_conflict` 裁决（已删除/已完成/已停止冲突不复活、
    running 幂等、paused+q_common 只置 running）；其余任务类型 post_start 原路径零 diff；
  - 方向翻转接线（C16 §4.2 1/2/4/7）：gate 等待循环评估、任务卡读模型"当前方向"选取、
    放行审计新增 `eval_direction` 字段、`_smooth_market_doc` 对 close 卡把 wait_reason
    文案中「开单率」改写为「平仓率」（开单卡零 diff）；§4.2-3（覆盖率）随同一次评估自动
    一致并被测试单独锁住；§4.2-5（`_resolve_fresh_preflight`）已有行为不变；
  - 平仓闸门（C12 五处）：`put_close_gate` 唤醒 + 开闸 ensure_worker；gate 等待循环检查
    `is_close_gate_on()` 关闸清门；`_dispatch_one_for_task` 发单准入要求平仓闸门开启；
    `_worker_round` 因平仓闸门关闭退出时清门；
  - C15 处置：`_worker_round` 对无有效 q_common 的 running smooth close 任务 fail-closed
    落 paused + 既有 `preflight_incomplete` 中文原因（worker 两轮内退出，不忙循环）；
    仅拦 close（open smooth 的 NULL-q_common 历史行走 F-A 既有已接受行为，零回归）；
  - C17：`task_to_doc` 新增派生字段 `close_preparation_state`（不落库）。
- `backend/tests/test_smooth_api.py`：更新被解除的 open-only 断言为新契约
  （smooth close 无 provider → 400 smooth_market_unavailable）。
- `backend/tests/test_hedge_api.py`：`_TASK_KEYS` 冻结字段集合加入
  `close_preparation_state`（C17 新增派生字段导致集合断言更新）。
- `backend/tests/test_smooth_close_p1.py`（新增）：覆盖 spec §5 列表的 21 个验收项
  （1、2、4、6、7、7a、7b、8、9、10、10a、11、12、13、14、15、17、18、19、21、22），
  共 46 条测试。

### 冻结的 API 契约（spec §6，供 P2 接线）

**1. 建卡请求体（smooth close）**：`POST /api/hedge-open-tasks`，键集合不变
（coin / direction / mode / single_amount / target_n / task_type /
slippage_threshold_pct）。`mode=smooth` + `task_type=close` 现在合法；要求公共盘口
provider 可用，否则 400 `smooth_market_unavailable`（detail「平滑开平仓公共盘口不可用；
可继续使用立即开单/立即平仓」）。`slippage_threshold_pct` 服务端独立校验
（`D.validate_slippage_threshold_pct`：带符号十进制字符串、最多两位小数；正/零/负合法；
超两位、科学记数、`%`、空值、非字符串均 400 `invalid_field`；超长合法整数正常规范化）。
smooth close 建卡即固化规范值且 `failure_pause_threshold=1`；immediate close 不收阈值、
阈值 3；建卡后仍 `paused + awaiting_manual_start`，零联网、零 worker。

**2. 任务文档新增派生字段**：`close_preparation_state`，取值：
- `"prepared"`：smooth close 且 `q_common` 有值（已备料）；
- `"unprepared"`：smooth close 且 `q_common` 为空（未备料）；
- `"realtime_per_round"`：immediate close（每轮实时校验，行为不变）；
- `null`：open 任务（两种模式，无此概念）。
由 `q_common` 是否有值派生，不落库、不缓存，无第二处真相。P2 中文映射建议：
已备料 / 未备料 / 每轮实时校验。

**3. 读模型对 close 的语义（P2 两列接线依赖）**：
- **「当前方向」= 任务方向取反**（后端 `D.evaluation_direction`）。
  **forward close 的当前方向是 `reverse_spread_pct` 那一列**，其价格与数量为
  `spot.bid + perp.ask` 与 `spot.bid_qty + perp.ask_qty`；reverse close 的当前方向是
  `forward_spread_pct` 那一列，为 `perp.bid + spot.ask` 与 `perp.bid_qty + spot.ask_qty`。
  `smooth_market` 文档中 `spot_coverage_pct` / `perp_coverage_pct` / `spread_pass` /
  `coverage_pass` / `gate_pass` / `wait_reason` 全部来自当前方向（翻转后）的同一次评估；
  覆盖率分母 = 备料冻结的 `q_common`。
- `wait_reason`：close 卡为「等待当前方向**平仓率**严格大于阈值」（不含「开单率」）；
  开单卡文案逐字不变。
- `smooth_gate_seq` / `smooth_gate_started_at_us` / `smooth_gate_deadline_at_us` /
  `smooth_gate_force_requested` / `smooth_gate_state`：close 与 open 语义相同
  （5 分钟窗口、gate 身份 `(task_id, next_attempt_seq)`、`成交1次` 携带 gate_seq）；
  close 任务额外要求 `q_common` 有效才可建门/强制（C15，空值时 fill-once 409）。
- `smooth_dispatch_audits` payload 新增 `eval_direction` 字段 = 实际参与评估的方向
  （close 为翻转后方向）；`direction` 保持任务方向；其余字段同 open。快照来自产生放行
  结论的同一次读取。

**4. 启动接口（`POST .../start` 对 smooth close）**：成功 200 + 任务 doc（running）；
失败 409，code 与含义：`start_gate_closed` / `close_gate_closed`（闸门关闭，零预检/零查仓/
零划转）、`smooth_close_start_failed`（备料失败，detail 为落库的中文暂停原因）、
`invalid_state`（已删除/已完成/已停止不复活；计划次数已用完）。前端在请求进行中应置灰
该卡全部按钮（C13，P2 范围）。

### 命令与结果

- 全量后端测试：`python3 -m pytest backend/tests -q` → **1936 passed, 1 failed**。
  唯一失败 `test_private_client.py::test_urlopen_only_in_designated_http_clients`
  为**既有失败**：`backend/services/public_ip_service.py` 含 urlopen 但不在 allowed 列表，
  该文件由提交 `73f525d`（2026-08-12-local-ip-display-v1）引入，早于本 stage base
  `7d3fe60`，本轮未触碰该文件与其测试，按边界不修（避免扩大受审范围）。
- 新增测试：`python3 -m pytest backend/tests/test_smooth_close_p1.py -q` → 46 passed
  （连跑三次全绿）。
- **变异验证（spec §5 三条假绿陷阱 + 补充，共 6 种错实现，各自使对应测试变红后已还原）**：
  1. store gate 恢复 open-only 谓词 → 21 项失败，含验收 10a 两条专项（"能启动、能订阅、
     但 gate 永远建不起来、零成交"的实现变红）；
  2. 移除 C15 worker fail-closed 处置 → `test_running_close_without_q_common_...`
     红（轮次跑满 = 忙循环被抓）；
  3. gate 评估不翻转方向（"只翻预检不翻 gate"）→ 两条方向翻转测试红；
  4. 读模型不翻转（"只翻 gate 不翻读模型"）→ `test_direction_flip_covers_read_model_...` 红；
  5. 覆盖率分母改成 `single_amount` → `test_coverage_denominator_...` 红；
  6. 删掉收尾 `_verify_close_flat` 实时核实（"为绿测删收尾"）→
     `test_um_position_query_segmented_by_call_site` 红（分段计数：备料 1 次 + 收尾 1 次）。
  还原后与备份逐一 `cmp` 比对，工作树无任何残留变异改动。

### 未完成事项 / 边界

- 立即平仓单腿的 advisory 语义未做任何改动（§4.5 既有全局行为）；C8 的阈值 1 经
  R2-F1 既有分支使 smooth close 的一次单腿成交/一次确认提交失败都暂停并记录敞口，
  测试 `test_smooth_close_single_leg_brakes_at_threshold_one` /
  `test_smooth_close_confirmed_failure_brakes_at_threshold_one` 锁定。
- `_start_smooth_close` 对 status=stopped 的 smooth close 返回 409（fatal stop 不自动
  恢复）；设计未规定该分支，fail-closed 取舍已写入代码注释。
- 平仓闸门 C12③ 的 dispatch 准入对 immediate close 同样生效（纵深防御）；worker 轮次
  层的 close gate 检查（功能三既有）仍在，行为无回归（测试
  `test_immediate_close_runs_three_gates_every_round` 锁定每轮三道门）。
- P2 前端（`frontend/index.html`）与 `backend/app/server.py` 未触碰。

### Required Reading for the Next Task
- 读取路径及顺序：reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/05-backend-p1.handoff.md
- 执行：Bookkeeper 核验本 handoff 与交付 commit，固定 base_sha..delivery_sha，写入 status.json 并推进状态
- 关卡：HIGH_RISK 的 Review-1 + Review-2（跨 provider 只读评审，锚定固定 commit 区间）
- 不能假设的事实：服务未启动、未实盘验证；平滑平仓仅有 fake 全链证据；P2 前端契约以本 handoff「冻结的 API 契约」小节为准（尤其 `close_preparation_state` 取值与 close 任务"当前方向"= 翻转后方向、对应另一列 spread）；`test_urlopen_only_in_designated_http_clients` 为既有失败非本轮引入

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: 05-backend-p1
执行结果: completed（完成）
结果摘要: 平滑平仓 V1 后端 P1 按 spec 22 项全部实现：建卡放行 smooth close（阈值落库、刹车 1）、三道门抽函数且立即平仓原调用点每轮执行、post_start 闸门前置+同步备料+一次条件写、store gate 解禁加 q_common 谓词、方向翻转覆盖 gate/读模型/审计/文案、平仓闸门五处接线、C15 fail-closed、C17 备料状态派生字段。新增 46 条 fake 测试覆盖 spec §5 全部 21 个验收项；6 种变异验证均使对应测试变红后还原。全量后端 1936 passed，仅剩 1 条早于 base 的既有失败（public_ip_service urlopen，未触碰）。冻结契约（字段名 close_preparation_state；close 当前方向=翻转后方向，forward close 对应 reverse_spread_pct 列即 spot.bid+perp.ask 组）已写入 handoff。
产物: [backend/hedge_open_tasks/service.py, backend/hedge_open_tasks/store.py, backend/hedge_open_tasks/domain.py, backend/tests/test_smooth_close_p1.py, backend/tests/test_smooth_api.py, backend/tests/test_hedge_api.py, reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/05-backend-p1.handoff.md]
检查结果: [建卡与阈值（验收 4/11）pass；备料与启动链 C4/C5/C13/C14（验收 7/7a/7b/8/9）pass；gate 解禁与 C15 处置（验收 10/10a）pass 且变异验证变红；方向翻转与覆盖率（验收 1/2/6）pass 且四种翻错实现变红；平仓闸门五处（验收 13）pass；5 分钟窗口（验收 12）pass；放行后零联网（验收 14）pass；持仓查询分段（验收 15）pass 且删收尾核实变红；收尾三分支（验收 18）pass；重启缝不 resend（验收 17）pass；模式隔离零回归（验收 19）pass；审计同源+方向（验收 21）pass；派生字段（验收 22）pass；全量后端测试 1936 passed / 1 条既有失败（public_ip_service urlopen，早于 base 7d3fe60，未触碰不修）pass；零真实订单/划转/服务启动 pass]
阻塞项: [none]
本地北京时间: 2026-08-14 21:55:42 CST
下一步模型: gemini-3.1-pro（Bookkeeper，当前 status.json.bookkeeper；Human 启动）
下一步任务: 读取：reports/agent-runs/2026-08-14-smooth-close-orders-v1/evidence/05-backend-p1.handoff.md；执行：核验 handoff 与交付 commit（cmp 工作树与备份无残留变异、重跑 python3 -m pytest backend/tests -q 预期 1936 passed + 1 条既有失败）、解析 delivery_sha 写入 status.json 并把任务推至 reported；关卡：固定 base_sha..delivery_sha 后进入 HIGH_RISK Review-1（跨 provider 只读评审）
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)
（由 Bookkeeper 核验后追加）

## Errata (append-only)
（无）
