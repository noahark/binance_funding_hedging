# 借币任务卡「行情 ↗」反向定位方案

## 1. 目标与边界

在每张借币任务卡的 `.borrow-task-head` 右上角增加轻量 `btn compact` 按钮「行情 ↗」。有对应市场行时，点击后回到市场表并定位该币种；当前筛选已让目标可见时完整保留用户筛选，目标被筛掉时才放开所有实际阻塞条件并同步控件，保证行进入 DOM，随后平滑居中并提供约 1.5 秒聚焦反馈。

本轮是一个不可拆分的纯前端任务，仅修改 `frontend/index.html` 与 `frontend/self-check.js`。不改后端 API、store、schema、数据库、任务状态、借币执行、订单、资金、配置或部署；不新增依赖、网络请求、轮询或通用导航框架。

## 2. 当前实现证据

- `renderBorrowTaskCard(task, intervalText)` 生成 `.borrow-task-card`；`.borrow-task-head` 当前依次包含资产标题、状态徽标和最近结果徽标，适合在末尾追加按钮。
- `bindBorrowTaskControls()` 在每次 `renderBorrowTasks()` 重建列表后绑定卡片控件，新增按钮应沿用这里，不另设全局事件委托。
- `state.snapshot.rows` 是市场行当前快照；`filteredRows()` 的实际隐藏条件有搜索、`assetTag`、`routeClass`、`showPerpOnly`、`hideLowDailyRate`、`hideLowNetYield` 六项。
- `displayRows()` 在 `filteredRows()` 之后只按 `preferOpenable` 重排，不新增隐藏条件；`showHl` 也只控制子行显示。因此这两项不应在导航时重置。
- `renderTable()` 通过现有 `captureMarketOpInputs()` / `restoreMarketOpInputs()` 保留市场操作格输入，可安全用于筛选放开后的单次重绘。
- `setActiveView('market')` 同步显示市场视图并先滚到页面顶部，不会自己重置筛选或重绘市场表；具体目标滚动必须在它之后执行。
- 市场行根节点是 `tr.selectable[data-symbol="..."]`；现有 `patchRow()` 已证明 `CSS.escape(symbol)` 可用于安全选择，self-check mock 也支持同形选择器。
- 上一轮已有 `borrowTaskFocusId + 单 timer + render 时带 class` 的 1.5 秒聚焦模式。本轮平行增加市场行自己的短生命周期状态即可，不抽象成跨视图框架。

## 3. 冻结设计

### D1. 资产到市场行的唯一解析规则

新增纯函数（建议名 `marketRowForBorrowAsset(asset)`）：

```js
return (state.snapshot && Array.isArray(state.snapshot.rows)
  ? state.snapshot.rows : []).find(row => row && row.base_asset === asset) || null;
```

- 匹配严格为 `row.base_asset === task.asset`，不做大小写转换、symbol 拼接或别名推断。
- 如果快照中意外出现同一 `base_asset` 多行，按 `state.snapshot.rows` 当前顺序取第一行；这是 `Array.find` 的确定性结果，不引入第二套排序。
- 无匹配、快照缺失或 rows 非数组时返回 `null`。

### D2. 精确 DOM、可访问性和右上角布局

`renderBorrowTaskCard()` 在最近结果徽标后追加按钮：

```html
<div class="borrow-task-head">
  <h3>BTC</h3>
  <span class="badge ...">借币中</span>
  <span class="badge ...">...</span>
  <button class="btn compact borrow-market-nav" type="button"
          data-borrow-market-asset="BTC"
          aria-label="查看 BTC 行情">行情 ↗</button>
</div>
```

- `data-borrow-market-asset` 与 `aria-label` 中的资产继续经 `escapeHtml()` 输出；点击时按资产从当前快照重新解析，避免闭包或旧 symbol。
- 匹配行存在时按钮可用。无匹配时仍保留同位置按钮，增加原生 `disabled`、`aria-disabled="true"` 与 `title="当前行情快照无对应币种"`；用户能看到能力但不会跳到错误位置，复用既有 `.btn:disabled` 样式。
- CSS 只加 `.borrow-task-head .borrow-market-nav { margin-left:auto; flex:0 0 auto; }`，利用现有 flex header 将按钮推到最右，不改变其他徽标和任务控制区。

### D3. 智能按需放开与 100% 可见

新增导航函数（建议名 `viewBorrowAssetInMarket(asset)`），固定顺序如下：

1. 用 `marketRowForBorrowAsset(asset)` 读取当前快照；无匹配则返回 `{ ok:false, reason:'market_row_not_found' }`，不切视图、不改筛选。
2. 取 `targetSymbol = String(targetRow.symbol)`，在任何修改前计算：

   ```js
   const alreadyVisible = displayRows().some(row => row.symbol === targetSymbol);
   ```

3. 记录 `state.marketRowFocusSymbol = targetSymbol`，取消上一次市场行聚焦 timer，然后调用 `setActiveView('market')`。
4. 若 `alreadyVisible === true`：不修改任何 `state.filters`，不修改任何筛选 DOM 控件，不调用 `renderTable()`；沿用当前已渲染市场表。搜索文本、两个下拉框、四个筛选 checkbox，以及纯重排/展示项 `preferOpenable`、`showHl` 均原样保留。
5. 若 `alreadyVisible === false`：一次性放开全部实际隐藏条件并同步相应 DOM 控件，然后调用一次 `renderTable()`：

   | 状态 | 同步控件 | 放开值 |
   |---|---|---|
   | `state.filters.search` | `els.filterSearch.value` | `''` |
   | `state.filters.assetTag` | `els.filterAsset.value` | `''` |
   | `state.filters.routeClass` | `els.filterRoute.value` | `''` |
   | `state.filters.showPerpOnly` | `els.filterShowPerpOnly.checked` | `true` |
   | `state.filters.hideLowDailyRate` | `els.filterHideLowDailyRate.checked` | `false` |
   | `state.filters.hideLowNetYield` | `els.filterHideLowNetYield.checked` | `false` |

   `showPerpOnly=true` 是“保底 100% 可见”的必要部分：当前 `filteredRows()` 在它为 false 时会排除 `PERP_ONLY_EXCLUDED`。`preferOpenable` 只重排、`showHl` 只改子行，均必须保留。

6. 用现有安全模式定位：

   ```js
   const tr = els.tableBody.querySelector(
     `tr.selectable[data-symbol="${CSS.escape(targetSymbol)}"]`
   );
   ```

   找到后显式添加 `market-row-focus`（覆盖 already-visible 未重绘路径），再调用
   `tr.scrollIntoView({ behavior:'smooth', block:'center' })`。

此算法只在“目标当前不可见”这个已证实状态下改筛选；不会逐项猜测哪个条件是根因，也不会漏掉 PERP-only 闸门。放开后目标来自同一快照且六项隐藏条件全解除，因此必在 `displayRows()` 与表格 DOM 中。

### D4. 1.5 秒聚焦及重绘保持

- 在 `state` 增加 `marketRowFocusSymbol: null`，模块级增加唯一 `marketRowFocusTimer`。
- `renderRowHtml(row, umPositions)` 在 `String(row.symbol) === state.marketRowFocusSymbol` 时给根 `<tr>` 追加 `market-row-focus`。这样 60 秒快照刷新或其他已有重绘发生在反馈窗口内时，焦点不会立即消失。
- CSS 新增 `@keyframes market-row-focus-pulse` 与 `tbody tr.market-row-focus`（或其 `> td`）：用现有 `--brand` / `--brand-soft` 做清晰边框/浅背景脉冲，固定 `1.5s ease-out`；结束回到原行视觉，不覆盖持久的 `.selected` 语义。
- `@media (prefers-reduced-motion: reduce)` 下关闭动画并保留静态 outline/内阴影；JS 仍在 1500ms 后清除。
- 重复点击先 `clearTimeout` 旧 timer。新 timer 1500ms 后只在焦点 symbol 仍等于本次目标时清空状态，并用同一安全 selector 从当前 DOM 移除 `market-row-focus`；只有最后一次点击控制反馈。

### D5. 事件绑定与隔离

在 `bindBorrowTaskControls()` 中增加 `[data-borrow-market-asset]` 绑定：

- `click` handler 第一行 `e.stopPropagation()`，再读取资产并调用 `viewBorrowAssetInMarket()`。
- `keydown` handler 对所有按键调用 `e.stopPropagation()`；不调用 `preventDefault()`，保留原生按钮的 Enter/Space 激活，随后产生的 click 仍走同一隔离与导航路径。
- disabled 按钮在浏览器中不会产生用户 click；导航函数本身仍对无匹配 fail-closed。
- 该动作只读本地状态并切换/重绘 DOM，不发 borrow POST、市场刷新或其他网络请求，也不打开市场行抽屉。

## 4. 文件级实施清单

### `frontend/index.html`

- 在借币任务 header CSS 旁加入右对齐按钮样式；在市场表行样式旁加入聚焦动画与 reduced-motion fallback。
- 在 `state` 增加 `marketRowFocusSymbol`，在模块作用域增加一个清理 timer。
- 增加 `marketRowForBorrowAsset()`、目标行安全查询和 `viewBorrowAssetInMarket()`。
- 修改 `renderBorrowTaskCard()` 输出可用/disabled 的「行情 ↗」。
- 修改 `bindBorrowTaskControls()` 绑定 click/keydown 并隔离事件。
- 修改 `renderRowHtml()`，让焦点 class 跨现有重绘保持。
- 只向 `window.__appHelpers` 暴露本轮自检所需的最小解析/导航/焦点/筛选读取 seam；生产逻辑不依赖它。

### `frontend/self-check.js`

- 复用现有 task-card HTML 解析；给 mock DOM 最小补足 `[data-borrow-market-asset]` 按钮注册、市场行 `classList` 和 `scrollIntoView` 参数记录。
- 不引入浏览器、依赖或新 fixture 文件。

## 5. 自检用例

1. **DOM/布局**：匹配任务卡 header 中存在 `btn compact borrow-market-nav`，文本/属性/aria 正确，按钮位于徽标之后；CSS 含 `margin-left:auto`。无匹配时同位置按钮为 disabled 并有说明。
2. **资产解析**：`row.base_asset === task.asset` 命中并返回对应 symbol；异资产、空快照返回 null；同资产多行取 snapshot 第一行。
3. **已可见保持**：构造目标仍可见的非默认搜索、资产标签、路由、checkbox、`preferOpenable`、`showHl` 组合；导航后 state 与所有 DOM 控件值逐项不变，视图变为 market，目标行滚动居中并聚焦。
4. **隐藏行放开**：用搜索/下拉/两个低值隐藏条件遮住目标，导航后断言六项 state 与 DOM 完全同步为冻结值、`preferOpenable` / `showHl` 保持，目标行进入 DOM。
5. **PERP-only 保底**：用内存 fixture 把目标设为 `PERP_ONLY_EXCLUDED` 且 `showPerpOnly=false`；导航后断言 checkbox/state 变 true、行实际渲染并滚动，证明不是只靠清搜索的假绿。
6. **缺失目标**：无对应市场行时按钮 disabled；直接调用导航 helper 也不抛错、不切视图、不改筛选、不滚动。
7. **事件隔离与零副作用**：运行真实 click/keydown handler，分别断言 `stopPropagation()`、不 `preventDefault()`；不触发卡片/行抽屉，不新增任何 fetch，尤其零 borrow POST。
8. **聚焦生命周期与全量回归**：断言 1.5 秒动画、reduced-motion 静态反馈、重绘后焦点仍在、重复导航以后一次为准、定时清理；运行 `node frontend/self-check.js`，要求全部通过且请求/定时器白名单无新增失败。

## 6. 验收口径

- 每张借币卡右上角有「行情 ↗」；严格按 `row.base_asset === task.asset` 解析，缺失时明确 disabled。
- 当前已可见时所有筛选 state/控件原样保留；当前隐藏时六项真实隐藏条件全部放开并同步 DOM，包含 `showPerpOnly=true` 的保底，目标 100% 进入表格。
- 切换到市场视图后目标行平滑居中，得到约 1.5 秒可识别聚焦；reduced-motion 下仍有静态反馈，现有抽屉 selected 语义不受破坏。
- click/keydown 都隔离，不发请求、不触发借币/订单/资金动作。
- 只有 `frontend/index.html`、`frontend/self-check.js` 和实现任务交接证据会在后续实现范围内变化；`node frontend/self-check.js` 全量通过。

## 7. 后续路由与停止点

本计划先由 `opus5` / Anthropic 在 `claude` 窗口做独立只读计划评审。只有明确 `ACCEPT` 后，Bookkeeper 才可准备由 `kimi` 实施的前端派单，允许文件仅为 `frontend/index.html`、`frontend/self-check.js` 与实现任务的确定性交接文件。实现后仍按本 stage 的既定 Review-1 / Review-2 路由评审；本计划不授权实现、提交、合并、部署或实盘操作。
