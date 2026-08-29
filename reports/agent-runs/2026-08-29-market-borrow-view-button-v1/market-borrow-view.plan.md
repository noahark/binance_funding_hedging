# 市场表「查看借币」按钮实施方案

## 1. 目标与发布边界

在市场表可创建借币任务的行中，于现有「确认」按钮右侧增加「查看借币」按钮。按钮只由浏览器内最近一次 `GET /api/borrow-tasks` 得到的 `state.borrowTasks` 决定；点击后进入「借币任务」视图、切回任务页签、选中能展示目标卡片的状态筛选，滚动到该卡片并显示约 1.5 秒的聚焦动画。

本轮只有一个不可拆分的前端实现任务：修改 `frontend/index.html` 与 `frontend/self-check.js`。不改后端 API、数据库、schema、任务状态机、借币执行逻辑、路由或部署配置；不发起借币、订单、资金或外部请求。

## 2. 当前代码证据

- `frontend/index.html` 的 `renderBorrowOpCell(row)` 生成市场表「借币」操作格；可操作行当前在 `.borrow-op-inputs` 内渲染两个输入框和一个 `data-borrow-confirm` 按钮。
- `attachRowHandlers(tr)` 给整行绑定抽屉点击/键盘事件，并在真实 DOM 下绑定操作格控件。新增按钮必须在自身的 `click` 与 `keydown` 处理器中都调用 `e.stopPropagation()`，不能只依赖父 `.borrow-op-cell` 的隔离。
- `state.borrowTasks` 是最近一次任务列表 GET 的渲染缓存；`loadBorrowTasks()` 会替换它，但市场视图下目前只更新导航数字，不重绘市场表。`mutateBorrowTask()` 也只重绘任务列表。因此，若不补同步点，启动加载、创建任务、暂停/完成任务或从借币页返回市场页后，按钮可能与缓存不一致。
- `setActiveView('borrow-tasks')` 会同步显示借币视图、把 `borrowTaskFilter` 重置为 `borrowing`、先用缓存渲染任务卡，再异步重拉任务列表；它不会把此前选择的日志页签强制改回任务页签。
- `renderBorrowTasks()` 按筛选状态生成 `.borrow-task-card[data-task-id="..."]`，并复用 `sortTasksNewestFirst()` 按 `created_at` 倒序、同时间按 `id` 倒序排序。
- `renderTable()` 已通过 `captureMarketOpInputs()` / `restoreMarketOpInputs()` 在整表重绘时保留用户正在填写的借币/开单输入，可安全复用来同步按钮投影。

## 3. 冻结设计

### D1. 唯一匹配谓词与 1 对多选择

新增纯前端选择函数（建议名 `latestActiveBorrowTaskForAsset(asset)`）：

1. `renderBorrowOpCell(row)` 以 `row.base_asset` 调用该函数；完整显示谓词严格为
   `task.asset === row.base_asset && (task.status === 'borrowing' || task.status === 'paused')`。
   helper 内部的等价写法是 `task.asset === asset`，其中 `asset` 只能来自该行的
   `row.base_asset`。不做大小写归一化，也不把 `completed`、`deleted` 或未知状态算作可跳转任务。
2. 复用 `sortTasksNewestFirst()` 排序，取第一个任务。因此优先 `created_at` 字符串较新的任务；`created_at` 相同时取 `id` 字符串降序较大的任务。该规则与任务页当前“新在前”规则一致，无第二套排序口径。
3. 无匹配时返回 `null`。`renderBorrowOpCell(row)` 只在返回任务时生成按钮，并把选定任务的 `id` 写入按钮属性；点击时按该 ID 再从当前缓存取任务，避免闭包使用过期对象。

`isBorrowOpDisabledRow(row)` 的既有短路保持不变：这类行本来没有「确认」按钮，继续只显示 `—`，不新增孤立的查看按钮。本功能只增强已有确认操作格。

### D2. 精确 DOM 与布局

把可操作行中原来的单个确认按钮包进一个新容器，并让查看按钮紧跟其后：

```html
<div class="borrow-op-actions">
  <button class="btn compact primary" type="button"
          data-borrow-confirm="AUSDT" aria-label="确认创建 AUSDT 借币任务">确认</button>
  <button class="btn compact borrow-view-task" type="button"
          data-borrow-view-task="<task-id>" aria-label="查看 A 借币任务">查看借币</button>
</div>
```

- `data-borrow-view-task` 的值与 `aria-label` 中的资产继续经 `escapeHtml()` 输出。
- 无匹配任务时 `.borrow-op-actions` 内只有原确认按钮，不保留空占位，两个输入、预览和错误容器均不变。
- CSS 只新增 `.borrow-op-actions { display:flex; align-items:center; gap:var(--space-1); flex-wrap:wrap; }`，保证新按钮位于确认按钮右侧，窄列时允许整组自然换行；不改表格列数或输入框宽度。

### D3. 缓存变化后同步市场按钮

按钮是 `state.borrowTasks` 的投影，因此缓存变化和市场 DOM 必须同时更新：

- `loadBorrowTasks()` 成功替换缓存后，在已有导航/任务列表更新之外，若 `state.snapshot` 存在且未阻塞，调用 `renderTable()`。
- `mutateBorrowTask()` 收到后端返回的任务文档并写入缓存后，也立即在快照可用时调用 `renderTable()`；随后既有 GET 即使失败，POST 返回的权威任务状态仍已投影到市场表。
- 复用 `renderTable()` 现有输入捕获/恢复，不新增局部 patch 协议、不新增轮询、不新增网络请求。

这覆盖启动时行情快照与任务列表的异步先后顺序、市场页创建任务、借币页暂停/完成后返回市场页三条现有可达路径。

### D4. 跳转、页签、筛选、滚动与短暂聚焦

新增一个按任务 ID 执行的函数（建议名 `viewBorrowTask(taskId)`），流程顺序固定：

1. 用 `findBorrowTask(taskId)` 重新读取当前缓存；若不存在或已不再是 `borrowing` / `paused`，直接返回，不跳到一个不存在的目标。
2. 记录 `state.borrowTaskFocusId = String(task.id)`，并清除上一次聚焦清理定时器。
3. 调用 `setActiveView('borrow-tasks')`；随后调用现有 `setBorrowTab('tasks')`，保证用户此前停在「借币日志」时任务卡面板重新可见。
4. 在 `setActiveView` 重置筛选之后调用 `setBorrowTaskFilter(task.status)`：执行中目标使用 `borrowing`，暂停目标使用 `paused`。两者都是现有合法筛选，目标卡必在当前列表，不使用更宽的 `all`。
5. `renderBorrowTaskCard()` 在任务 ID 等于 `state.borrowTaskFocusId` 时，为根节点同时输出 `borrow-task-card borrow-task-focus`。这样，进入视图触发的异步 `loadBorrowTasks()` 即使重建卡片，只要目标仍存在，聚焦类也不会立刻丢失。
6. 从 `els.borrowTaskList.querySelectorAll('.borrow-task-card[data-task-id]')` 中按 `getAttribute('data-task-id') === String(task.id)` 找到目标卡。不要把未转义任务 ID拼进 CSS selector。找到后调用：

   ```js
   card.scrollIntoView({ behavior: 'smooth', block: 'center' });
   ```

7. 以单个模块级清理定时器在 1500ms 后清空仍匹配的 `state.borrowTaskFocusId`，并从当时仍在 DOM 中的目标卡移除 `borrow-task-focus`；重复点击先取消旧定时器，保证只有最后一次点击控制焦点。

CSS 新增 `@keyframes borrow-task-focus-pulse` 和 `.borrow-task-card.borrow-task-focus`：动画时长固定 `1.5s`，使用现有 `--brand`、`--brand-soft`、`--line`、`--surface-2` 做边框、浅背景与轻量阴影脉冲，结束回到原卡片视觉。`prefers-reduced-motion: reduce` 下关闭动画，保留静态 `outline` 约 1.5 秒，仍提供可识别反馈。

### D5. 事件隔离

在 `attachRowHandlers(tr)` 的真实 DOM 分支中查找 `[data-borrow-view-task]`：

- `click`：第一句 `e.stopPropagation()`，再读取按钮上的任务 ID 并调用 `viewBorrowTask()`。
- `keydown`：对所有按键调用 `e.stopPropagation()`；不调用 `preventDefault()`，保留原生按钮的 Enter/Space 激活行为。原生随后产生的 click 仍走上面的隔离与跳转。

父 `.borrow-op-cell` 的既有 click/keydown 隔离继续保留，形成局部控件与行抽屉之间的明确边界。

## 4. 文件级实施清单

### `frontend/index.html`

- 在借币任务卡 CSS 附近加入聚焦动画与 reduced-motion 样式；在借币操作格 CSS 附近加入 `.borrow-op-actions`。
- 在 `state` 增加唯一短生命周期字段 `borrowTaskFocusId`，在模块作用域增加唯一清理 timer。
- 增加活动任务选择函数、目标卡查找函数和 `viewBorrowTask(taskId)`。
- 修改 `renderBorrowOpCell()` 输出动作容器与条件按钮。
- 修改 `attachRowHandlers()`，显式绑定查看按钮 click/keydown。
- 修改 `renderBorrowTaskCard()`，按焦点 ID 输出聚焦类。
- 在 `loadBorrowTasks()` 成功路径和 `mutateBorrowTask()` 返回文档落缓存后同步重绘市场表。
- 只向 `window.__appHelpers` 暴露自检所需的最小函数（活动任务选择、查看动作或事件绑定）；生产逻辑不依赖测试 seam。

### `frontend/self-check.js`

- 更新既有“操作单元格两输入一按钮”断言：无任务时仍是一按钮；有匹配活动任务时为确认 + 查看两按钮，并断言动作容器、按钮顺序、属性与可访问名称。
- 给 mock DOM 补足本轮真实使用的最小能力：任务卡属性查询、`classList`、`scrollIntoView` 参数记录，以及可调用的查看按钮 click/keydown handler；不引入浏览器或新依赖。

## 5. 自检用例

1. **显示谓词**：分别注入同资产 `borrowing`、`paused`，断言显示「查看借币」；空列表、仅 `completed`、仅 `deleted`、仅其他资产时断言隐藏。
2. **1 对多确定性**：同资产同时存在活动任务，断言先选 `created_at` 最新者；时间相同再断言选 `id` 降序较大者。终态任务即使更新也不能抢占目标。
3. **缓存投影及时性**：市场视图中 `loadBorrowTasks()` 成功后按钮立即出现/消失；整表重绘前填入的借币数量与次数保持不变。
4. **执行中跳转**：从市场页点击执行中目标后，`activeView === 'borrow-tasks'`、任务页签可见、筛选为 `borrowing`，目标卡收到 `scrollIntoView({behavior:'smooth', block:'center'})` 和聚焦类。
5. **暂停跳转**：先把借币顶层页签设为日志，再点击暂停目标；断言切回任务页签、筛选为 `paused` 且目标卡实际渲染、滚动、聚焦。
6. **事件隔离**：运行查看按钮的 click 与 keydown handler，分别断言 `stopPropagation()` 被调用；模拟冒泡守卫，确认市场行抽屉处理器未执行。click 只切视图，不产生任何 borrow POST。
7. **聚焦生命周期**：断言 CSS 动画为 1.5 秒、reduced-motion 有静态反馈；重复聚焦以后一次目标为准，清理后焦点字段与当前卡片类消失。
8. **全量回归**：运行 `node frontend/self-check.js`，要求全部通过且同源请求白名单、定时器白名单与既有借币创建/任务动作测试无新增失败。

## 6. 验收口径

- 可操作市场行仅在严格命中活动借币任务时出现「查看借币」，按钮位于「确认」右侧；无任务或任务全为 `completed` / `deleted` 时不存在该按钮。
- 多任务目标始终是 `created_at` 最新、同时间 `id` 降序最大的活动任务。
- 执行中和暂停中目标都能进入任务页签、命中对应筛选、滚动居中并得到约 1.5 秒明确聚焦反馈；此前停在日志页签不影响跳转。
- 查看按钮的 click/keydown 都不会打开市场行抽屉。
- 功能只读取和展示已有任务缓存，不新增后端、schema、存储、外部请求或任何资金动作。
- `node frontend/self-check.js` 全量通过。

## 7. 后续路由与停止点

本计划先由 `opus5` / Anthropic 在 `claude` 窗口做独立只读计划评审。只有明确 `ACCEPT` 后，Bookkeeper 才可准备一个由 `kimi` 实施的前端派单，允许文件仅为 `frontend/index.html`、`frontend/self-check.js` 与该实现任务的确定性交接文件。实现后仍按活动 stage 的既定 Review-1 / Review-2 路由评审；本计划不授权实现、提交、合并、部署或实盘操作。
