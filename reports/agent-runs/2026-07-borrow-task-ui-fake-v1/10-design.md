# Stage Design

## Summary

在 `frontend/index.html` 内维持一个仅会话内存在的 `borrowTasks` 数组和 `activeView`。表格操作单元使用所在行的 `base_asset` 创建任务；借币任务导航用同一状态渲染任务列表。UI 只表达未来后台策略，不执行网络调用或定时重试。

## Assumptions

- 当前公开样例没有 `HOME` 行；该事实不应被前端改写。
- 后端接口、重试间隔配置和真实任务生命周期尚未定义，故固定为清晰标注的 30 秒 fake 展示值。
- 每次确认独立创建一条任务，即使资产相同；任务 ID 可只在浏览器会话内使用。

## Design Decisions

- Decision 1: 把“操作”作为第 13 列，不修改“借贷状态 / 资产”合并列的既有状态含义。
- Decision 2: 使用事件隔离（例如 `stopPropagation` / `preventDefault`）防止点击输入或确认按钮触发行点击抽屉。
- Decision 3: 以任务资产、单次数量、目标成功次数、成功进度 `0/N`、目标总量和固定 30 秒展示任务。不可声称已调度、已请求或已借到资产。
- Decision 4: `HOME` 支持是泛化的 `base_asset` 路径；自检以纯内存方式把一行改为 `HOME`，避免污染 API fixture 或伪造行情。
- Decision 5: 删除 max-borrowable 额度子行的冗余“已借完”标签，唯一保留的耗尽文案是状态徽标“可借 0(已借完)”。

详细理由、替代方案和 reviewer context 见 `11-adr.md`。

## Task Breakdown

- Task `frontend-borrow-task-fake`: Kimi 修改 `frontend/index.html` 与 `frontend/self-check.js`，实现、验证和记录 raw output。

## Test Strategy

- Unit tests: `frontend/self-check.js` 断言表格 13 列、任务输入/按钮、输入校验、HOME 任务信息、导航切换、无真实借币 fetch/interval，以及“已借完”不重复。
- Integration tests: 不适用；本阶段没有 API 或后端改动。
- Replay/backtest checks: 不适用。
- Manual checks: 在浏览器中输入 `1000` 和 `10` 并确认，切换“借币任务”，确认任务卡明确为前端演示。

## Risks

- Risk 1: 现有表格行可点击打开抽屉；操作控件必须阻断事件传播。
- Risk 2: 自检 mock DOM 对新增选择器支持有限；测试优先通过公开 helper 验证任务状态，并补足最少 mock 能力。
- Risk 3: fake UI 容易被误认作已发起借币；任务视图和状态必须显式声明未发起真实请求。

## Raw Artifact Requirements For Review

- `00-task.md`
- `10-design.md`
- `11-adr.md`
- git diff or patch
- implementation report
- test output
- `frontend/index.html`
- `frontend/self-check.js`

## Amendment v2 Design

Replace the borrow-task cards with an accessible task list/table layout that can show state, progress, lifecycle controls, task-parameter edit controls, and list filters without altering market data. Each in-memory task gains `status` with one of `borrowing`, `paused`, `deleted`, or `completed`; new tasks default to `borrowing`.

- Lifecycle transitions are local functions: `startBorrowTask`, `pauseBorrowTask`, and `deleteBorrowTask`. Delete first invokes the same local stop semantics when needed, then assigns `deleted`; it never removes the task object.
- The page stores `borrowTaskFilter`. A title-level filter control derives the displayed list and selected-filter count from the canonical `state.borrowTasks` array. 全部 is not a status; it displays all task objects, including soft-deleted ones.
- Task edit controls use separate per-task IDs/data attributes and exact current values. Confirm validates with the existing positive finite amount / positive integer target rules, updates the selected task only, retains `successCount`, and re-renders task view/count/filter UI. No edit path calls `fetch`, localStorage, or a timer.
- `completed` is a supported display/filter state but has no UI transition in this fake. Tests may construct a pure in-memory completed task through a test-only helper or a bounded state fixture; production UI must not add an unrequested simulated-success button.
- Lifecycle and edit controls must be disabled according to frozen semantics in `13-scope-amendment-v2.md`; deleted and completed items remain inspectable, not mutable.

Review focus: correct state transition/button enablement, soft-delete visibility, filter membership, preservation of amount/target validation, explicit fake disclosures, no external side effects, and no regressions to existing market drawer event handling.

## Amendment v3 Design — Minimum Borrow Guidance

The existing classic-margin reference already fetches `allAssets`. Add a parallel `user_min_borrow_by_name` map keyed by `assetName`, then project it through `assemble_borrow_validation` exactly where `asset_borrowable_by_name` is projected. Do not reuse `max_borrowable`: the former is a minimum request amount; the latter is current account/pool capacity.

The contract field is a raw decimal string or null, not a JavaScript/float value. The frontend derives an amount-input placeholder only; it does not write the value into the input. This keeps the existing user-confirmation semantics and avoids treating a minimum as a recommendation, available amount, or a real borrow instruction.

Backend and frontend are separable but contract-dependent: Claude-GLM lands the map/assembly/schema/raw sample/tests first; Kimi then consumes the additive field in the existing market operation-cell placeholder while implementing the v2 task UI state work. The development breakdown must make that dependency explicit and keep both tasks within the same stage.

当前 Session ID: unavailable (current runtime does not expose provider-native session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-borrow-task-ui-fake-v1/10-design.md
本地北京时间: 2026-07-18 18:26:49 CST
下一步模型: Kimi
下一步任务: 实现前端 fake 借币任务 UI
