# 22 — Frontend Task F2 Implementation Report

Stage `2026-07-borrow-task-ui-fake-v1` · Branch `stage/2026-07-borrow-task-ui-fake-v1`
Role: implementation author (Kimi / `kimi-code/kimi-for-coding`) · Base HEAD `82db8414b97819b72294ba8eee33bd0b7ec0dfd4`（含已提交 B1 依赖 `623d059`）
Dispatch: `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/29-kimi-frontend-f2.dispatch.md`

## 1. Scope delivered

按 dispatch 与 `12-development-breakdown.md` §3 逐条落地，全部为 UI-only、仅内存语义：

1. **任务状态模型**：`state.borrowTasks` 每个任务带 `status ∈ {borrowing, paused, deleted, completed}`，新建任务默认 `borrowing` / 借币中。按钮矩阵逐状态精确执行（borrowing：启动禁/暂停/删除/编辑可用；paused：启动/删除/编辑可用、暂停禁；completed：启动/暂停/编辑禁、删除可用；deleted：全部禁用/只读）。
2. **转换**：`pauseBorrowTask` borrowing→paused，`startBorrowTask` paused→borrowing（互逆纯 UI 转换）；`deleteBorrowTask` 先应用本地 stop 语义（本阶段无调度器，stop 仅为状态语义）再软删除——置 `status:'deleted'`，对象绝不从 `state.borrowTasks` 移除；completed 也可被删除。全部转换零 fetch、零定时器、零进度改动。
3. **标题区筛选**：借币任务 panel-header 的 `#borrow-task-filters` 渲染 全部/借币中/已暂停/已删除/已完成 五个工作筛选（按钮 + 计数 + `aria-pressed`）。`全部` 不是 status，显示含软删除在内的每个任务；计数与成员只从权威数组 `state.borrowTasks` 派生。`已完成` 可渲染/可筛选但无任何生产 UI 动作或 fake 调度器把任务移入该状态（初始恒空，空态 `暂无「已完成」任务`）。
4. **任务内编辑**：每张任务卡有独立的单次数量/成功目标输入（`task-edit-amount-<id>` / `task-edit-count-<id>`，`value` 预填精确当前值）+ 确认修改按钮 + 就近错误容器。校验与创建同规则（数量有限 >0；目标整数 >0）。有效编辑只更新该任务、保留 `successCount`、重算展示目标总量并重渲染；无效值或只读（deleted/completed）编辑不改状态、就近显示局部错误。
5. **最小借币量占位符**：行情表操作列数量输入保持空值（无 `value` 属性），`placeholder` 由 `row.borrow_validation.classic_margin` 派生——双字符串（含 raw `"0"` / `"0.00"`）→ `最小借币量 X (≈ Y USDT)`；raw 有值估值 null → `最小借币量 X (≈ — USDT)`；raw null/缺失 → `最小借币量 —`。经 `escapeHtml` 转义；不影响任务列表编辑输入、用户校验、任务创建，也不暗示当前可借。
6. **v1 行为保留**：13 列/`colspan=13`、通用 `HOME` 路径（不伪造行情行）、操作控件事件隔离、操作格恰好两输入+确认、「已借完」唯一性、侧栏导航与前端演示免责声明，全部经既有 #1–#67 回归验证。
7. **零副作用**：未新增任何 `fetch`、私有 API、借币请求、`setInterval`/重试、`localStorage` 写入、持久化或"模拟成功"入口。

## 2. Changed files

- `frontend/index.html`（+208/-14 区域：状态机与转换函数、筛选渲染、任务卡控件/编辑区、`minBorrowPlaceholder`、占位符接线、helpers 导出、CSS）
- `frontend/self-check.js`（+276：任务卡解析辅助、#68–#74 用例、mock 最小补足）
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/22-implementation-frontend-v2.md`（本文件）
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/62-test-output-frontend-v2.txt`（测试原始输出）

未触碰 `backend/**`、`schemas/**`、api-samples、fixtures、`status.json`、`70-handoff.md`、canonical docs、workflow/agent 文件；未 commit。

## 3. Design decisions

- **状态机为纯 UI 语义**：`borrowing` 不调度任何工作；转换只改 `status` 字段并重渲染，与 ADR「不得误判为后台调度」一致。
- **软删除保对象**：`deleteBorrowTask` 只写字段，保证 已删除 筛选与「全部含 deleted」有真实内容；completed→deleted 走同一路径。
- **筛选计数单一权威源**：`renderBorrowTaskFilters` 每次从 `state.borrowTasks` 现算，不维护第二份列表；`全部` 计数 = 数组长度。
- **编辑/生命周期按钮绑定**：渲染后经 `bindBorrowTaskControls`（真实 DOM `querySelectorAll`）绑定；mock DOM 对该选择器返回空数组，自检经 `__appHelpers` 直测（与 v1 同一 mock 策略，design Risk 2）。筛选按钮用容器事件委托（随重渲染存活）。
- **占位符为纯字符串指引**：`minBorrowPlaceholder` 不解析数值、不做可用性推断，仅按三分支拼接 raw 字符串并转义；`"0"`/`"0.00"` 走双值分支原样展示。
- **test-only completed 构造**：自检通过 `helpers.getBorrowTasks()` 活数组注入 completed 任务，生产代码零新增入口（breakdown §3.4 允许）。

## 4. Self-check coverage added（接续 #67）

- #68 新建默认 `borrowing`；四状态按钮矩阵逐格断言（含编辑输入/确认的 disabled）；非法转换守卫（deleted 不可暂停、borrowing 不可启动、重复删除失败）。
- #69 暂停→启动往返：状态字段、徽标翻转、进度/目标不变。
- #70 软删除：对象保留、全部/已删除可见、借币中排除、completed 删除后变 deleted。
- #71 筛选成员与计数（`全部 (4)` 含 2 个 deleted）、已完成可渲染、已暂停空态不白屏。
- #72 编辑：预填精确当前值；1000/10→250/7 后 `250 HOME/次`、`0 / 7 次成功`、`目标 1,750 HOME`，`successCount` 保留；无效数量/非整数目标值不变 + 就近错误；deleted/completed 只读编辑报错且状态不变。
- #73 占位符三分支 + `"0"`/`"0.00"` 边界；数量输入无 `value` 属性；任务编辑输入预填/无 placeholder 不受影响。
- #74 状态转换/编辑/筛选序列后 `fetchCallLog` 与 `intervalCalls` 零增长、`localStorage` 键数不变。
- 既有 #1–#67 全部保持通过（13 列、HOME 泛化、事件隔离、已借完唯一性等无回归）。

## 5. Test commands and results

```bash
$ node frontend/self-check.js
# 全部断言 PASS（既有 #1–#67 + 新增 #68–#74），结尾「全部自检通过」
# exit_code=0

$ git diff --check
# 无输出
# exit_code=0
```

完整原始输出见 `62-test-output-frontend-v2.txt`。

## 6. Manual visual checks

本执行环境无浏览器，**未执行** `12-development-breakdown.md` §3.8 的浏览器手工视觉检查（含 DevTools Network 面板确认）。对应行为已由 self-check 的 DOM 级断言覆盖（按钮矩阵、筛选计数/成员、编辑往返、占位符三分支、全过程零 fetch/定时器注册）。如需人工目验，建议在 review 阶段由操作员在浏览器中复核。

## 7. Deviations / disclosures

- **P3 类披露（breakdown §0 可选项）**：任务视图在每次状态动作（暂停/启动/删除/编辑/筛选）后整体重渲染任务列表，会重置其他卡片中**未提交**的编辑输入。这与既有 P3-1（60 秒表格重渲染清空未提交输入）同类，仅影响演示中未确认的中间输入，不影响已确认状态；按"与 v1 渲染策略一致 + 最小改动"处理，未做局部补丁渲染。
- 无实现偏差；无新增 fetch/timer/持久化；未 commit（按 dispatch 要求留给 bookkeeper 证据提交与正式交叉评审）。

当前 Session ID: 83684f19-df9d-44ba-885c-267a01656f75
Session ID 来源: transcript_path
原始输出路径: reports/agent-runs/2026-07-borrow-task-ui-fake-v1/22-implementation-frontend-v2.md
本地北京时间: 2026-07-18 23:07:03 CST
下一步模型: bookkeeper (Codex/GPT)
下一步任务: 提交 F2 证据，重算 d9c2772..新 head fingerprint，跑 validate-stage pre-review，按 §1 路由发起全新 review-1（B1→Kimi，F2→Claude-GLM）与 review-2
