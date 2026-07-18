# Implementation Report — frontend-borrow-task-fake

## Task

执行 `15-kimi-implementation.dispatch.md`：在 `frontend/index.html` 与
`frontend/self-check.js` 内实现纯前端、仅内存的 fake 借币任务原型。分支
`stage/2026-07-borrow-task-ui-fake-v1`，未提交（按 dispatch 要求保留 worktree 给
bookkeeper 做 review-gate commit）。

## Changed Files

- `frontend/index.html`（+/- 见 diff）
- `frontend/self-check.js`
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/60-test-output.txt`（测试原始输出）
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/20-implementation.md`（本文件）
- `reports/agent-runs/2026-07-borrow-task-ui-fake-v1/status.json`、`70-handoff.md`（检查点更新）

未触碰 `backend/**`、`schemas/**`、`docs/**`、`workflows/**`、`agents/**`、fixture 或任何
API 契约。

## What Was Implemented

1. **第 13 列「操作」**：表头在「借贷状态 / 资产」右侧新增 `<th>操作</th>`；
   `renderRowHtml` 每行输出 13 个 `td`；`renderTable` 的阻塞态与空态 `colspan` 全部
   改为 13。
2. **操作单元格**：恰好两个可编辑输入（`borrow-amount-<symbol>` 单次借币数量、
   `borrow-count-<symbol>` 成功借币次数，均有 `<label for>` 关联与按钮
   `aria-label`）+ 一个「确认」按钮 + 就近错误容器
   `borrow-error-<symbol>`（`role="alert"`）。`attachRowHandlers` 对操作单元格绑定
   `stopPropagation`（click 与 keydown），控件不会触发行点击抽屉；mock DOM 的 tr 无
   `querySelector`，绑定处做了特性守卫，自检经 `__appHelpers` 直测（design Risk 2）。
3. **校验**：`parseBorrowAmount` 只接受 > 0 的有限数值（拒绝空串/0/负数/非数值/
   Infinity/NaN）；`parseSuccessTarget` 只接受 > 0 的整数（拒绝小数等）。非法输入经
   `submitBorrowTask` 在单元格错误容器就近显示，不创建任务。
4. **fake 任务**：`createBorrowTask` 仅向 `state.borrowTasks`（会话内存数组）追加
   `{id, asset: row.base_asset, amountPerAttempt, successTarget, successCount: 0}`。
   无 `fetch`、无私有 API、无后端改动、无持久化（不写 localStorage）、无
   `setInterval`/重试循环。每次确认独立创建一条任务（design Assumption）。
5. **侧栏导航**：「费率行情」后新增「借币任务」入口并带任务计数徽标
   （`borrow-task-count`，初始化时 `updateBorrowTaskNav()` 置 0）。`setActiveView`
   切换 `market-view` / `borrow-task-view` 容器显示与导航 active/aria-current 状态。
6. **借币任务视图**：空态（「暂无借币任务」+ 创建引导）与任务卡。任务卡含资产、
   `1,000 HOME/次` 样式单次数量、`0 / 10 次成功` 进度、`目标 10,000 HOME` 目标总量、
   「每 30 秒尝试一次，失败等待下次，达到成功次数后停止」策略文案、「前端演示」
   徽标与「未发起真实借币请求」强免责；视图顶部另有 warn 横幅声明仅内存、未发起
   真实请求。`HOME` 走通用 `base_asset` 路径，未伪造任何 `HOMEUSDT` 行情行。
7. **`maxBorrowableSubline`**：删除独立 `已借完` 徽标（`zeroTag`）；状态徽标
   「可借 0(已借完)」保持不变，耗尽文案全行只出现一次。
8. **self-check 扩展**：既有 12 列断言升级为 13 列（表头顺序、行 td 数、
   empty-state colspan）；新增 #62 操作单元格结构/事件隔离、#63 导航切换与空态、
   #64 输入校验、#65 内存 `HOME` 行（1000/10）任务创建 + 展示值 + 零 fetch（经
   `fetchCallLog`）+ 零新定时器（`intervalCalls` 只允许 60000/1000）+ 禁
   `HOMEUSDT`、#66 UI 提交路径与就近错误、#67 「已借完」唯一性。mock 最小补足：
   `getElementById` 对 `borrow-(amount|count|error)-*` 惰性 mock，新增 6 个静态 id，
   `fetchCallLog` 记录全部 fetch URL。既有全部覆盖保持通过。

## Design Decisions

- 视图切换用容器包裹（`#market-view` div）而非逐 section 切换，避免与
  warnings/private 面板的动态 `display` 冲突。
- 金额格式化新增 `formatTaskAmount`（`toPrecision(12)` 消除浮点尾差后整数千分位、
  小数原样），与既有 `formatPrice` 风格一致；目标总量 = 单次数量 × 次数。
- 确认按钮通过 `attachRowHandlers` 内 `tr.querySelector('[data-borrow-confirm]')`
  绑定（真实 DOM）；未引入内联事件属性，保持文件既有 addEventListener 风格。
- 任务在快照刷新后保留（内存会话语义），`ingestSnapshot` 不触碰 `borrowTasks`。

## Test Commands And Results

```bash
$ node frontend/self-check.js
# 全部断言 PASS（含既有全部用例与新增 #62–#67），输出结尾「全部自检通过」
# exit_code=0

$ git diff --check
# 无输出
# exit_code=0
```

完整原始输出见 `60-test-output.txt`。

## Deviations

无。dispatch 八项要求全部实现；未提交 commit（按要求留给 bookkeeper）。

## Known Limitations

- 任务仅存于浏览器会话内存，刷新即失（design Tradeoff，有意为之）。
- 操作控件的真实 DOM 事件绑定在 mock 环境无法执行，自检通过 `__appHelpers`
  直测创建/校验/展示路径，事件隔离以结构断言（`stopPropagation` 存在）覆盖。

当前 Session ID: 83684f19-df9d-44ba-885c-267a01656f75
Session ID 来源: transcript_path
原始输出路径: reports/agent-runs/2026-07-borrow-task-ui-fake-v1/20-implementation.md
本地北京时间: 2026-07-18 19:00:34 CST
下一步模型: bookkeeper (Codex/GPT)
下一步任务: 检查 diff 与测试证据，创建 review-gate commit，然后按 workflow 派发 review-1 (claude_glm)
