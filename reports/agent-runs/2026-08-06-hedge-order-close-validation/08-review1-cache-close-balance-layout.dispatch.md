# 评审任务：Review-1 本 stage 修复链（task 05 preflight 缓存 / 06 平仓余额 / 07 滚动定位 / HTML 标签修复）

阶段：`2026-08-06-hedge-order-close-validation`（验证下单/平仓核心链路 + 修复小 bug）
status.json：`reports/agent-runs/2026-08-06-hedge-order-close-validation/status.json`

背景：任务 01/02/03 已交付 `ee7ec4f` 并经 review-1 ACCEPT（提交 `56a0c11` 核验）。
其后 Human 实盘复测驱动的修复链已封存，本次 review-1 一次性审 `ee7ec4f..10f1f01`
区间内**四个交付**。Human 决定：**只做一轮 review（review-1），以 Human 显示验收
为准，不安排 review-2**。

## Identity

- task_id: `2026-08-06-hedge-order-close-validation-review1-cache-close-balance-layout`
- target_role: `Reviewer`
- target_model: `opus5`（Human 指定；provider=anthropic，与实现作者 deepseek 隔离）
- provider: 按 `agents/roles.md` 模型映射
- status_revision: 12
- required_skill: `agents/skills/code-reviewer.md`

## Goal

对 committed `base_sha..delivery_sha` = `ee7ec4f..10f1f01` 做 review-1。评审主体为
四个交付（同批提交，Human 决定一次审完）：

### 交付 1 — task 05 `e4d5464`：preflight 改读本地缓存 + 平仓校验简化 + 预检失败可见暂停
- `SnapshotService.get_cached_source`（只读，无刷新副作用）；provider 缓存映射
  （exchangeInfo 2h / price_map·balances·spot 5min / restricted_asset 10min
  fail-closed 不降级）；账户级配置 600s TTL；平完判定收敛（`>=target_n` 时实时一次）；
  划转去复检 + `sleep(100ms)` + 缓存放行/实时确认；预检失败 `_pause_preflight_incomplete`
  （paused + 中文原因含失败读名 + 无重试）；前端徽标 dry-run 警示色 + 演习标注。

### 交付 2 — task 06 `5388938`：close+forward 平仓余额检查补 regular_spot 路由感知
- `compute_preflight` REVERSE 分支：`regular_spot` 路由用普通现货账户该币可用量
  （`spot_account_base_free`），否则 `balances` 逐字不变；FORWARD 分支零改动；
  provider `_read_spot_account_base_free` 形状照抄 `_read_spot_account_usdt`。

### 交付 3 — task 07 `3006db3`：视图切换滚动定位（LOW_RISK 纯前端）
- `setActiveView` 切换后 `window.scrollTo(0, 0)`（typeof 保护兼容 self-check node 环境）。

### 交付 4 — `10f1f01`：删除 `hedge-task-view` 内多余 `</section>`
- `f153cdc`（删除假数据预览探针）残留的孤悬 `</section>`，导致浏览器解析器把
  `#history-view` 移出 `<main>`（历史仓位表单落在页面底部）。删除该行后全文件
  section/div/header/main 配对平衡（Bookkeeper 已用脚本验证：无未闭合、无多余闭合）。
  **这是 Human 显示验收问题的真正根因；交付 3 的滚动定位保留（正确行为），
  但仅治标。**

## Allowed Files

只读（评审不改任何代码、证据、`status.json`、提交）：

- `reports/agent-runs/2026-08-06-hedge-order-close-validation/status.json`
- `reports/agent-runs/2026-08-06-hedge-order-close-validation/05-preflight-local-cache-and-close-simplify.dispatch.md`
- `reports/agent-runs/2026-08-06-hedge-order-close-validation/06-close-forward-regular-spot-balance-fix.dispatch.md`
- `reports/agent-runs/2026-08-06-hedge-order-close-validation/07-history-view-layout-fix.dispatch.md`
- `reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/*.handoff.md`（task 05/06/07 三份）
- `backend/services/snapshot_service.py`
- `backend/services/hedge_preflight_provider.py`
- `backend/hedge_open_tasks/service.py`
- `backend/hedge_open_tasks/domain.py`
- `frontend/index.html`
- 相关测试文件（test_hedge_preflight_provider / test_hedge_task_local /
  test_hedge_cycle_close / test_account_cache_refresh_v1 / test_hedge_review2_regressions /
  test_hedge_domain 等）

评审完成后**创建唯一写**（Task Handoff Evidence Contract 的 create-only 例外）：
`reports/agent-runs/2026-08-06-hedge-order-close-validation/evidence/2026-08-06-hedge-order-close-validation-review1-cache-close-balance-layout.handoff.md`
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
8. 三份 dispatch（05/06/07）+ 三份 handoff（`evidence/` 下 task 05/06/07）
9. 按需读 Allowed Files 中的代码

评审区间：`git rev-parse ee7ec4f` 与 `git rev-parse 10f1f01` 直取核对；diff 用
`git diff ee7ec4f..10f1f01`。区间内 bookkeeper 控制提交（dispatch/status.json 等）为
上下文非受审交付（`AGENTS.md` §8 口径）。

## Acceptance Checks

1. **交付 1（task 05）**：缓存读取只读（不触发刷新）；`restricted_asset` 唯一
   fail-closed 不降级；平完判定仅状态转换点实时一次、三分支语义不变；划转
   `sleep(100ms)` + 去复检后缺 `tranId` 仍暂停；预检失败 paused + 失败读名 + 无重试；
   前端徽标未改数据源。
2. **交付 2（task 06）**：REVERSE 分支 regular_spot 路由感知正确（THE 场景
   600 不再误报可用 0）；非 regular_spot 路径 `balances` 逐字不变；FORWARD 零改动；
   `_read_spot_account_usdt` 函数体零改动。
3. **交付 3（task 07）**：滚动定位在 display 切换后、无副作用；node 环境安全。
4. **交付 4（HTML 标签）**：确认删除后全文件配对平衡（可复跑
   `python3` 标签栈脚本或目视核对）；`#history-view` 在 `<main>` 内；
   无其他残留错位标签。
5. **回归**：评审者复跑 `.venv/bin/python -m pytest backend/tests -q` 与
   `node frontend/self-check.js`（Bookkeeper 已实测 1467 passed + 全绿，评审者至少复跑
   self-check + 抽查关键测试；若全量复跑更佳）。
6. **范围**：`git diff ee7ec4f..10f1f01` 无范围外改动；无未授权提交/实盘写。
7. 输出 `[TASK_RESULT v2]` 含 `评审结论: ACCEPT（接受）| REWORK（返工）`、
   `问题记录`、`修复要求`；每条 `REWORK` 发现按 `AGENTS.md` §8 范围三分类标注。

## Stop

按 `AGENTS.md` §7 返回完整中文 `[TASK_RESULT v2]`（含三行中文交接 + 评审闭线字段），
先完成唯一 handoff 创建，再以其中 Human Brief 生成控制台回执。`下一步任务` 用
可执行形式 `读取：<路径或 none>；执行：<立即动作>；关卡：<下一验证>`。

下一关卡：review-1 结论返回 Bookkeeper（deepseek）核验；`ACCEPT` 后由 Human
显示验收拍板（本 stage Human 已决定只做一轮 review，不安排 review-2）。
