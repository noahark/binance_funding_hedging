# 05 后端 P1 实现规格（Planner 交付，供 Bookkeeper 组装 dispatch）

本文件是任务内容规格，不是 dispatch packet。Bookkeeper 据此生成 `05-backend-p1.dispatch.md`。

- 目标模型：**GLM 5.3**（provider `zhipu_glm`，Herdr 窗口标签 `claude-glm`，非 review 窗口）
- 需求权威：`docs/planning/smooth-close-orders-v1.md`（r3，第三次跨 provider 计划评审 ACCEPT，零阻塞）
- 前置：`04-fake-frontend` 已交付，Human 页面验收通过（样式与文案结论以该交付为准）
- 本任务**只做后端**。真实前端（P2）在本任务冻结 API 契约后另行派发。

## 1. 范围与不可拆分性

本任务为**单实现者、单提交范围**。设计 §9 的 P1 全部内容归本任务：备料抽函数与 `post_start` 同步执行、方向翻转的后端调用点、gate 与平仓闸门接线、store 侧 gate 解禁与条件写、建卡放行与阈值。

这些改动跨 `service.py` / `store.py` / `domain.py` 且互为前提（例如 store 的 gate 解禁若不配套 service 的方向翻转与 C15 谓词，就是一个能建门但判错方向的中间态），**不得拆给两个实现者并行**，也不得分成两次独立评审的交付。

## 2. 允许修改的文件

- `backend/hedge_open_tasks/service.py`
- `backend/hedge_open_tasks/store.py`
- `backend/hedge_open_tasks/domain.py`
- `backend/tests/` 下的相关测试文件（可新增测试文件）

**不得**修改 `frontend/index.html`（P2 的范围，含 `04-fake-frontend` 已交付的 fake 块）、`backend/app/server.py`（本轮不新增端点）、任何 harness 文件与设计文档。

## 3. 实现清单

逐条对应设计 r3 的决策编号；**理由与取舍不在此复述，以设计文档为唯一权威**。建议按下列依赖顺序实施。

### 3.1 建卡（C6 / C8 / §6.1）

1. 解除 `create_task` 的 `mode=smooth` open-only 限制；close 分支同样要求公共盘口 provider 可用，否则 400 `smooth_market_unavailable`；
2. close 轻量建卡分支落 `slippage_threshold_pct`（当前该分支未传）；
3. **仅** `smooth + close` 建卡时 `failure_pause_threshold = 1`；immediate close 保持默认 3。

### 3.2 备料抽函数（C4 / C5 / §4.1）

4. 把 `_dispatch_one_for_task` 中的三道门（fresh preflight → `_close_um_position_error` → `_ensure_close_spot_balance`）抽为一个可复用函数；
5. **立即平仓仍在原调用点、每一轮调用它**——这是零回归硬项，抽函数最容易在此处引入回归；
6. `post_start` 对 `smooth + close` 且 `q_common` 为空的任务同步调用它。

### 3.3 启动接口（C5 / C13 / C14 / §6.2）

7. 备料**之前**校验 Start gate 与平仓闸门，任一关闭即返回中文原因、任务保持 `paused`、**零预检/零查仓/零划转**；
8. 备料任一步失败 → `_pause_task_local` 写入既有三条中文原因之一，HTTP 返回该原因，不置 running、不启 worker；
9. 成功收尾是**一次条件写**（store 新增窄方法），语义等价 `WHERE id=? AND status='paused' AND q_common IS NULL`，命中才写 `q_common` / `position_side_mode` / `preflight_snapshot` 并置 `running`；未命中重读任务按当前权威状态返回，**已删除/已完成一律不复活**；
10. `q_common` 非空时跳过备料，仅做置 running（同样带 `paused` 谓词）。

### 3.4 store 侧 gate（C10 / C15）

11. `open_smooth_gate` 与 `force_smooth_gate` 解除 `task_type == open` 硬条件，允许 `close`；
12. 两者同时增加「`q_common` 有效」谓词。

### 3.5 方向翻转（C1 / C16 / §4.2）

13. 增加一个纯函数：由任务导出**评估方向**（close 取反，open 原样）；
14. 用它覆盖 §4.2 的第 1–5 项：gate 等待循环的评估、任务卡盘口读模型（含"当前方向"的选取）、覆盖率、放行审计、发单前预检（已有，行为不变）；
15. `wait_reason` 的写死文案（§4.2 第 7 项）改为不含"开单率"的表述，且**开单任务的文案零 diff**。实现方式可在 service 层改写或 domain 层参数化，但不得改变 `evaluate_smooth_gate` 的判定逻辑。

### 3.6 平仓闸门（C12 五处）

16. `put_close_gate` 唤醒等待中的 gate；
17. gate 等待循环检查 `is_close_gate_on()`，关闸时 `clear_smooth_gate`；
18. `_dispatch_one_for_task` 的发单准入同时要求平仓闸门开启；
19. `put_close_gate` 开闸后为 running 的 smooth 任务 `ensure_worker`（对齐 `put_start_gate`）；
20. `_worker_round` 因平仓闸门关闭退出时同样 `clear_smooth_gate`。

### 3.7 拦截处置与展示字段（C15 / C17 / §6.3）

21. 无有效 `q_common` 的 running 任务：fail-closed 落 `paused` + 既有 `preflight_incomplete` 中文原因并退出 worker，**不得只是不建门然后返回**（会形成无节流的紧密循环）；
22. `task_to_doc` 增加一个**派生**字段表达备料状态（由 `q_common` 是否有值决定，不落库、不新增列）。字段名由本任务确定并写入交付说明，P2 据此接线。

## 4. 零回归硬项

以下任一项被改变即为交付失败：

- 立即平仓每轮仍执行三道门，调用点与顺序不变，`failure_pause_threshold` 仍为 3；
- 立即开单、平滑开单的建卡、`post_start`、每轮 fresh preflight、杠杆设置时机、`wait_reason` 文案全部零 diff；
- 借币、还款、划转、资产互转、市场页 REST 开单率零 diff；
- 不新增任务状态、不新增数据库列、不新增端点、不新增第二套下单或备料路径。

## 5. 测试要求

覆盖设计 §8 验收矩阵中属于后端的项，至少包括：1、2、4、6、7、7a、7b、8、9、10、10a、11、12、13、14、15、17、18、19、21、22。

全部使用 fake clock / fake market provider / record executor，**不得发出任何真实订单或真实划转**。特别注意三条容易写成"假绿"的：

- **10a**：必须让"能启动、能订阅、但 gate 永远建不起来、零成交"的实现变红；
- **10**：除断言零 attempt / 零 executor 外，必须断言任务落暂停且 worker 轮次有上限（不得忙循环）；
- **15**：备料段的持仓查询最多一次，收尾的 `_verify_close_flat` 是**独立且必须保留**的一次实时查询，按调用点区分而非全生命周期计数。

交付前跑通仓库既有后端测试全集，不得留下失败或跳过。

## 6. 冻结的 API 契约（供 P2）

交付说明中必须明确列出：

- 建卡请求体对 smooth close 的字段与校验结论；
- 任务文档新增的备料状态派生字段名与取值；
- `smooth_market` / `smooth_gate_*` / `smooth_dispatch_audits` 对 close 任务的语义（尤其"当前方向"对应哪一组价格与数量，P2 的两列接线依赖它）。

P2 在此契约冻结后才会开始。

## 7. 硬禁令

- 不改前端、不改 harness 文件、不改设计文档；
- 不启动服务、不创建任务、不下单、不划转、不连接真实交易所；
- 不 `push`、不 `merge`、不切分支；
- 不为设计中未要求的假设场景增加防御机制（`AGENTS.md` §1）。

## 8. 交付形式

- 在当前 stage 分支本地提交；
- 按 Task Handoff Evidence Contract 创建 handoff；
- 返回 `[TASK_RESULT v2]`，`产物` 含 handoff 路径，`检查结果` 逐项标注 pass/fail/contested。

交付后由 Bookkeeper 固定 `base_sha..delivery_sha`，进入 HIGH_RISK 的 Review-1 + Review-2。
