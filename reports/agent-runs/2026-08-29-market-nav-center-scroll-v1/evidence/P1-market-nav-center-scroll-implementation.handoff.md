# Task Handoff: P1-market-nav-center-scroll-implementation

## Source Report (author-only; immutable after task end)

- task_id: `P1-market-nav-center-scroll-implementation`
- role: `Implementer` / target model: `kimi`（provider: `moonshot`）
- stage_id: `2026-08-29-market-nav-center-scroll-v1`
- created_at: `2026-08-29 21:53:36 CST`
- base_sha: `25cea9db770936e3e896fc71234b39f733f4ad65`（与 `git rev-parse HEAD` 一致）
- delivery_sha: `pending`（交付提交由 Bookkeeper 在提交后解析，本文件不重写）

### 任务背景与结论

借币任务卡「行情 ↗」反向定位（上一 stage `2026-08-29-borrow-card-market-nav-v1` 交付）在真实浏览器中
对长表 `<tr>`（`display: table-row`）调用 `scrollIntoView({behavior:'smooth', block:'center'})` 时，
Chrome/Safari 常算不准垂直居中、目标行停在视口底部；且与 `setActiveView` 同帧的
`window.scrollTo(0,0)` 可能冲突。本任务按派单把该滚动替换为 requestAnimationFrame + 数学坐标居中。

结论：已实现、自检 185 项全过（0 失败，exit 0），无未完成事项。

### 实际修改范围（仅派单允许的两个文件）

1. `frontend/index.html`
   - 新增 `scrollElementToCenter(el)`（借币卡反向定位代码块内，`marketRowElForSymbol` 之后）：
     - 能力判定：缺 `window` / `window.scrollTo` / `el.getBoundingClientRect` 任一即降级为
       `el.scrollIntoView({behavior:'smooth', block:'center'})`（node/mock 与旧行为一致）；
     - 具备能力时用 `requestAnimationFrame`（缺失退回 `setTimeout(cb, 0)`）等布局稳定后计算：
       `targetY = currentY + rect.top - window.innerHeight/2 + rect.height/2`，
       `window.scrollTo({top: Math.max(0, targetY), behavior:'smooth'})`；
     - `currentY = window.pageYOffset || document.documentElement.scrollTop || 0`。
   - `viewBorrowAssetInMarket` 定位到目标 `tr` 后改调 `scrollElementToCenter(tr)`，替换原直接
     `scrollIntoView` 调用；聚焦类、1.5s 定时清理、六项筛选放开逻辑均不动。
   - `__appHelpers` 在反向定位接缝注释下新增暴露 `scrollElementToCenter`（自检最小接缝）。
   - 未改动 `viewBorrowTask` 的借币卡滚动：派单该条为可选（"if appropriate"），借币卡是 `<div>`
     而非 `<tr>`，无底部停靠缺陷证据，按最小改动原则不扩散。

2. `frontend/self-check.js`
   - `_makeTrEl` 新增 `getBoundingClientRect()`，矩形由 `marketRowFocusRegistry[symbol].rect`
     供给（默认零矩形）；仅在测试临时安装 `window` mock 时数学路径才会被走到。
   - `global.document` mock 新增 `documentElement: { scrollTop: 0 }`（`currentY` 回退项）。
   - 新增 62e 用例块（4 条），位于 62d-8 之后、Task B 注释之前：
     - 62e-1 集成：临时安装 `window`（`pageYOffset=1000`、`innerHeight=800`、scrollTo 记录）与
       同步执行的 `requestAnimationFrame`，给 AUSDT 行 `rect={top:500,height:40}`，调用
       `viewBorrowAssetInMarket('A')`：断言收到 `scrollTo({top:1120, behavior:'smooth'})`、
       不再调 `scrollIntoView`、且 `setActiveView` 的 `scrollTo(0,0)` 先于数学居中；随后等
       1700ms 确认聚焦定时器清理。
     - 62e-2 rAF 缺失退回 `setTimeout(0)`：同帧不滚、下一 tick 后 `top=910`。
     - 62e-3 负 `targetY` 经 `Math.max` clamp 为 `top:0`。
     - 62e-4 降级路径：无 `window` 时回退 `scrollIntoView` 居中；`null` 元素安全无操作。
     - 块尾按进入本块前的 ambient 筛选快照逐项恢复（沿用 62d 的教训，不按默认值硬恢复），
       `window`/`requestAnimationFrame`/rect 在 `finally` 中拆除。

### 命令与结果

- `node frontend/self-check.js` → exit 0，`[PASS]` 185 项（含新 62e 块），`[FAIL]` 0 项，
  末行「全部自检通过」（日志：`/tmp/selfcheck-p1.log`，为机器临时文件非仓库证据）。
- `git rev-parse HEAD` → `25cea9db770936e3e896fc71234b39f733f4ad65`（= base_sha，未提交）。
- `git status --short` → 仅 `frontend/index.html`、`frontend/self-check.js` 两个交付文件被修改
  （`ACTIVE.json` 的 M 与本 stage 目录的 `??` 为 Bookkeeper 流程产物，非本任务改动）。
- 未 commit、未动 `status.json`、未触碰后端/配置/git 状态。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-29-market-nav-center-scroll-v1/evidence/P1-market-nav-center-scroll-implementation.handoff.md`
  2. `reports/agent-runs/2026-08-29-market-nav-center-scroll-v1/status.json`
  3. `reports/agent-runs/2026-08-29-market-nav-center-scroll-v1/P1-market-nav-center-scroll-implementation.dispatch.md`
  4. `frontend/index.html`（`scrollElementToCenter` 与 `viewBorrowAssetInMarket`）
  5. `frontend/self-check.js`（62e 用例块与 `_makeTrEl`/`document` mock 增量）
- 执行：Bookkeeper 核验本交接源区 SHA-256 与 base_sha，复跑 `node frontend/self-check.js`，
  随后提交交付、解析 delivery_sha 写入 status.json，并准备 Review-1/Review-2 派单。
- 关卡：Review-1/Review-2 双评审；合并与部署须 Human 另行授权。
- 不能假设的事实：
  - node/mock 环境下 `window` 不存在，运行时永远走降级 `scrollIntoView` 分支；62e-1/62e-2/62e-3
    的数学路径断言依赖测试临时安装的全局 `window`/`requestAnimationFrame` mock，且已在
    `finally` 拆除——下游用例若发现 `window` 残留，那是新增 bug 而非既有行为。
  - `setActiveView` 在真实浏览器会先 `window.scrollTo(0,0)`，数学居中在其后的 rAF 帧执行，
    该次序是正确性的前提，不要在 `scrollElementToCenter` 外再叠加即时滚动。
  - `viewBorrowTask` 的借币卡滚动保持原 `scrollIntoView`（div 无 tr 底部停靠缺陷），这是
    有意不扩散，不是遗漏。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: P1-market-nav-center-scroll-implementation
执行结果: completed（完成）
结果摘要: 「行情 ↗」定位的滚动已由 tr.scrollIntoView(block:center) 改为 scrollElementToCenter：requestAnimationFrame 等布局稳定后按 targetY=currentY+rect.top-innerHeight/2+rect.height/2 数学居中平滑滚动，负值 clamp 为 0；rAF 缺失退回 setTimeout(0)，node/mock 缺 window 时降级原 scrollIntoView。已接入 viewBorrowAssetInMarket；借币卡 div 路径无缺陷证据、按最小改动不动。自检 185 项全过、0 失败。
产物: [reports/agent-runs/2026-08-29-market-nav-center-scroll-v1/evidence/P1-market-nav-center-scroll-implementation.handoff.md]
检查结果: [pass: 居中助手在 rAF 内用 rect.top-innerHeight/2+rect.height/2 数学计算并 window.scrollTo 平滑滚动; pass: viewBorrowAssetInMarket 的目标 tr 改走该助手居中; pass: 缺 window/scrollTo/getBoundingClientRect 时降级 scrollIntoView(block:center)，rAF 缺失退回 setTimeout(0); pass: node frontend/self-check.js 185 项全过、0 失败（含新增 62e-1..62e-4 与既有白名单）; pass: 交接文件已建于确定性路径、delivery_sha pending、含源报告与 Human 简报]
阻塞项: [none]
本地北京时间: 2026-08-29 21:53:36 CST
下一步模型: Bookkeeper（gemini-3.7-flash，agy 窗口）
下一步任务: 读取：reports/agent-runs/2026-08-29-market-nav-center-scroll-v1/evidence/P1-market-nav-center-scroll-implementation.handoff.md；reports/agent-runs/2026-08-29-market-nav-center-scroll-v1/status.json；reports/agent-runs/2026-08-29-market-nav-center-scroll-v1/P1-market-nav-center-scroll-implementation.dispatch.md；执行：核验本交接源区 SHA-256 与 base_sha、复跑 node frontend/self-check.js，提交交付并解析 delivery_sha，推进 status.json 并准备 Review-1/Review-2 派单；关卡：Review-1/Review-2 双评审，合并与部署须 Human 另行授权
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- verified_at: `2026-08-29 21:55:52 CST`
- verifier: `gemini-3.7-flash` (Bookkeeper, `agy` window)
- source_sha256: `3985debd29326dc542434ab64b38824a4197a8e3ad133c3db3ab0fc49be1bef6`
- matched_status_revision: `1`
- next_status_revision: `2`
- base_sha: `25cea9db770936e3e896fc71234b39f733f4ad65`
- delivery_sha: `69e5cfa5f0d6764fb20452035ce18b63fc043875`
- verification_verdict: `VERIFIED_PASS`
- checks:
  1. Base SHA `25cea9db770936e3e896fc71234b39f733f4ad65` verified.
  2. Delivery commit `69e5cfa5f0d6764fb20452035ce18b63fc043875` sealed with product changes strictly confined to `frontend/index.html` and `frontend/self-check.js`.
  3. `node frontend/self-check.js` independently executed: 185 tests passed, 0 failures.
  4. Handoff file created at deterministic path with complete source report, Human brief, and valid marker.

## Errata (append-only)

None at task verification.
