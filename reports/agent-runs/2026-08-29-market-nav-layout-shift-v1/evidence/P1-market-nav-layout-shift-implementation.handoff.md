# Task Handoff: P1-market-nav-layout-shift-implementation

## Source Report (author-only; immutable after task end)

- task_id: `P1-market-nav-layout-shift-implementation`
- role: `Implementer` / target model: `kimi`（provider: `moonshot`）
- stage_id: `2026-08-29-market-nav-layout-shift-v1`
- created_at: `2026-08-29 22:45:01 CST`
- base_sha: `2b1acc35ec0db7ecf8b548bdfb13e01869e5d4cb`（派单/status.json 记录值）
- delivery_sha: `pending`（交付提交由 Bookkeeper 在提交后解析，本文件不重写）

### ⚠️ base_sha 记录值无法在仓库中解析（须 Bookkeeper 裁定）

`git cat-file -t 2b1acc35ec0db7ecf8b548bdfb13e01869e5d4cb` 返回 `fatal: bad object`——
该 SHA 在仓库中不存在。本任务开始时的实际 HEAD 为
`2b1acc36cff97f7dc28e311920178e6b57156eae`（`docs: 记录 2026-08-29-borrow-card-market-nav-v1
stage 完成于 PROJECT_STATE.md`），两者前 7 位相同（`2b1acc3`）、第 8 位起不同，疑为
Bookkeeper 记录时的转写错误或提交被改写。stage_id / task_id / target_model /
status_revision=1 均与 status.json 一致，故按实际 HEAD 为基线执行；基线口径须
Bookkeeper 核验时裁定（勘误 status.json 或拒收）。

### 任务背景与结论

上一 stage 的数学居中方案（`69e5cfa`）已被 `a4003e4` 整体 revert 回 `25cea9d` 稳定版；
本 stage 按独立复核的根因修复：`#pnl-curve-panel`（约 450px）位于 `#market-board` 上方，
「行情 ↗」导航滚动时面板尚未展开（高 0），100–200ms 后 `loadPnlSeries()` 完成才展开，
把市场表整体下移 450px，目标行因此停在视口上方约 450px 处。

结论：三处修复均已实现，自检 185 项全过（0 失败，exit 0），无未完成事项。

### 实际修改范围（仅派单允许的两个文件）

1. `frontend/index.html`
   - `setActiveView`：删除 `else if (els.pnlCurvePanel) els.pnlCurvePanel.style.display = 'none';`
     特判；改为无条件 `renderPnlCurve();` + `if (isMarket) loadPnlSeries();`。
     `renderPnlCurve` 内部 guard（`state.activeView === 'market' && (points.length > 1 ||
     state.pnlError)`）自决显隐：进 market 有缓存即同步展开，切出 market 同步收起——
     收起行为由此保留，既有自检 98d「离开费率行情页应隐藏面板」断言无需修改、仍通过。
     （派单片段只要求 isMarket 分支内调用；无条件调用是最小且保住既有离页契约的形式，
     验收检查 1/2 均满足。）
   - `renderPnlCurve`：面板判定可见后（`if (!visible) return;` 之后、空数据分支之前，
     故错误态展开也覆盖）新增 Layout Shift 校准——`state.marketRowFocusSymbol` 激活时
     用 `marketRowElForSymbol` 安全查行并 `scrollIntoView({behavior:'auto', block:'center'})`
     瞬时再居中，覆盖冷加载/后续异步展开的再校准。
   - `viewBorrowAssetInMarket` 的标准 `scrollIntoView({behavior:'smooth', block:'center'})`
     按派单要求保持不动；本文件未重新引入已 revert 的 `scrollElementToCenter`。

2. `frontend/self-check.js` — 新增 62e 用例块（62d-8 之后、Task B 注释之前）：
   - 62e-1：先 `loadPnlSeries()` 确保缓存；切到 borrow-tasks 断言面板被 guard 同步收起；
     `setActiveView('market')` 后不 await 即断言面板已同步展开（修复核心），await 后断言
     异步 pnl-series GET 仍恰好 1 次。
   - 62e-2：`viewBorrowAssetInMarket('A')` 置焦点后清滚动记录，`renderPnlCurve()` 断言
     AUSDT 行收到 `{behavior:'auto', block:'center'}`；等 1700ms 聚焦清理后再渲染断言
     不再触发滚动。块尾按 ambient 快照恢复八项筛选与 fixture。

### 命令与结果

- `node frontend/self-check.js` → exit 0，`[PASS]` 185 项（含新 62e 块），无 `[FAIL]`，
  末行「全部自检通过」（完整日志在机器临时文件 `/tmp/selfcheck-p1-ls.log`，非仓库证据）。
- `git rev-parse HEAD` → `2b1acc36cff97f7dc28e311920178e6b57156eae`（见上方 base_sha 警示）。
- `git status --short` → 仅 `frontend/index.html`、`frontend/self-check.js` 两个交付文件被修改
  （`ACTIVE.json` 的 M 与本 stage 目录的 `??` 为 Bookkeeper 流程产物，非本任务改动）。
- 未 commit、未动 `status.json`、未触碰后端/配置/git 状态。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-29-market-nav-layout-shift-v1/evidence/P1-market-nav-layout-shift-implementation.handoff.md`
  2. `reports/agent-runs/2026-08-29-market-nav-layout-shift-v1/status.json`
  3. `reports/agent-runs/2026-08-29-market-nav-layout-shift-v1/P1-market-nav-layout-shift-implementation.dispatch.md`
  4. `frontend/index.html`（`setActiveView` 与 `renderPnlCurve`）
  5. `frontend/self-check.js`（62e 用例块）
- 执行：Bookkeeper 先裁定 base_sha 记录值无法解析的勘误（见上方警示），再核验本交接源区
  SHA-256、复跑 `node frontend/self-check.js`，随后提交交付、解析 delivery_sha 写入
  status.json，并准备 Review-1/Review-2 派单。
- 关卡：Review-1/Review-2 双评审；合并与部署须 Human 另行授权。
- 不能假设的事实：
  - 派单/status.json 记录的 base_sha `2b1acc35ec0d...` 在仓库中不存在（bad object）；
    实际基线是 HEAD `2b1acc36cff9...`。未经 Bookkeeper 勘误前，不要把它当作可解析的
    git 引用。
  - `pnl-curve-panel` 的显隐现在唯一由 `renderPnlCurve` 内部 guard 拥有；不要再在
    setActiveView 或其他处加 `display` 特判，否则又回到双写。
  - 上一 stage 的 `scrollElementToCenter`/rAF 方案已被 revert（`a4003e4`），当前代码
    没有该助手；`viewBorrowAssetInMarket` 用标准 `scrollIntoView` smooth 居中，本 stage
    的 auto 再居中 guard 是补丁而非替代。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: P1-market-nav-layout-shift-implementation
执行结果: completed（完成）
结果摘要: Layout Shift 三处修复已落地：setActiveView 改为无条件同步 renderPnlCurve（guard 自决显隐，进 market 有缓存即同步展开、切出同步收起，原 else-if 特判已删）；renderPnlCurve 展开后在行导航焦点激活时 auto 瞬时再居中；导航自身 smooth 居中不动。自检 185 项全过、0 失败。注意：派单记录的 base_sha 在仓库中无法解析（bad object），实际基线为 HEAD 2b1acc36cff9，已写入交接件待 Bookkeeper 勘误裁定。
产物: [reports/agent-runs/2026-08-29-market-nav-layout-shift-v1/evidence/P1-market-nav-layout-shift-implementation.handoff.md]
检查结果: [pass: setActiveView(market) 在 loadPnlSeries 前同步调 renderPnlCurve，面板同步展开; pass: 切出 market 的多余 display=none 特判已删，面板显隐唯一由 renderPnlCurve guard 拥有，离页收起行为保住（98d 旧断言仍过）; pass: renderPnlCurve 含 Layout Shift guard，焦点激活时 scrollIntoView(behavior:auto, block:center) 再居中、焦点清理后不触发; pass: node frontend/self-check.js 185 项全过、0 失败（含新增 62e-1/62e-2 与既有白名单）; pass: 交接文件已建于确定性路径、delivery_sha pending、含 base_sha 解析失败警示]
阻塞项: [none]
本地北京时间: 2026-08-29 22:45:01 CST
下一步模型: Bookkeeper（gemini-3.7-flash，agy 窗口）
下一步任务: 读取：reports/agent-runs/2026-08-29-market-nav-layout-shift-v1/evidence/P1-market-nav-layout-shift-implementation.handoff.md；reports/agent-runs/2026-08-29-market-nav-layout-shift-v1/status.json；reports/agent-runs/2026-08-29-market-nav-layout-shift-v1/P1-market-nav-layout-shift-implementation.dispatch.md；执行：先裁定 base_sha 记录值 bad object 的勘误，再核验交接源区 SHA-256、复跑 node frontend/self-check.js，提交交付并解析 delivery_sha，推进 status.json 并准备 Review-1/Review-2 派单；关卡：Review-1/Review-2 双评审，合并与部署须 Human 另行授权
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- verified_at: `2026-08-29 22:48:32 CST`
- verifier: `gemini-3.7-flash` (Bookkeeper, `agy` window)
- source_sha256: `c33e6e3c860dfb33bdb24ce895b99f7a72dd0faad4c8a254bedc3084e002d946`
- matched_status_revision: `1`
- next_status_revision: `2`
- base_sha: `2b1acc36cff97f7dc28e311920178e6b57156eae`
- delivery_sha: `8f4b891741b29194d35b213b5f7968ae9f501c61`
- verification_verdict: `VERIFIED_PASS`
- checks:
  1. Errata ruling: Base SHA recorded in dispatch as `2b1acc35ec0d...` corrected to exact HEAD `2b1acc36cff97f7dc28e311920178e6b57156eae` per errata rule (packet text transcription correction, does not consume rework budget).
  2. Delivery commit `8f4b891741b29194d35b213b5f7968ae9f501c61` sealed with product changes strictly confined to `frontend/index.html` and `frontend/self-check.js`.
  3. `node frontend/self-check.js` independently executed: 185 tests passed, 0 failures.
  4. Handoff file created at deterministic path with complete source report, Human brief, and valid marker.

## Errata (append-only)

- base_sha record correction: status.json and dispatch recorded `2b1acc35ec0d...`; corrected to verified commit `2b1acc36cff97f7dc28e311920178e6b57156eae`.
