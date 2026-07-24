# Task B Review-1 REWORK 修复报告 — Frontend Hedge Open Real API v1

修复者：Claude Sonnet 5（用户指定的前端 fallback 修复者），执行本 stage
`frontend-r1-rework-sonnet5.dispatch.md` 中的 REWORK 修复。
分支：`stage/2026-07-hedge-open-real-api-v1`。
范围：仅 `frontend/index.html`、`frontend/self-check.js`（及本报告）。未改
backend、status.json、70-handoff.md、docs 或任何其他路径；未 git commit；未
调用/转派任何其他模型会话。

## 1. 阅读的原始证据

- `AGENTS.md`、`agents/developer-discipline.md`；
- `reports/agent-runs/2026-07-hedge-open-real-api-v1/{00-task.md,10-design.md,
  11-adr.md,12-development-breakdown.md,20-implementation-frontend.md,
  30-review-1-frontend.md,40-fix-backend-r4.md}`；
- `frontend/index.html`、`frontend/self-check.js`（实际改动前后均读取）；
- `backend/hedge_open_tasks/{domain.py,service.py}`（只读核对 `pair_outcome`
  取值集与投影路径，未修改任何字节）。

Review-1（`30-review-1-frontend.md`）裁定 **REWORK**，阻断项 P2-1 与必须修
P3-1；P3-2 为建议项。

## 2. 修改了什么

### 2.1 `frontend/index.html`

1. `HEDGE_PAIR_OUTCOME_LABELS`（原 3275-3277 行）新增 `single_leg: '单腿成交'`；
   `HEDGE_PAIR_OUTCOME_BADGE`（原 3278-3280 行）新增 `single_leg: 'warning'`。
   保留既有 `querying: '查询中'` 映射（无害兼容，未凭空删除）。
2. `renderHedgeAttemptCard`（原 3818-3823 行）的 outcome 取值逻辑：
   - 旧逻辑：`attempt.pair_outcome` 为 falsy（含 `null`）一律显示 `—`。
   - 新逻辑：`attempt.pair_outcome === null` 时显示「查询中」+ `info` 徽标；
     非 null 时按 `HEDGE_PAIR_OUTCOME_LABELS`/`HEDGE_PAIR_OUTCOME_BADGE` 查表，
     未收录取值原样展示英文 key + `muted` 徽标（未改变这一降级语义）。
   - 依据：`normalizeHedgeAttempt`（index.html:3763-3782）已将
     `src.pair_outcome === undefined` 归一为 `null`，因此归一化后的
     `attempt.pair_outcome` 只会是 `null` 或后端真实字符串枚举之一，
     `=== null` 判断精确覆盖"未解析/查询中"这一后端语义，不会误伤真正缺失字段
     （`hedgeText` 对其它字段的 `—` 语义未改动）。
3.（建议项 P3-2，简单且未扩大范围，已顺带做）`extractHedgeAttempts`
   （原 3784-3795 行）：命中 `doc.attempts` 数组后只扫描该数组，不再继续合并
   `fills/logs/entries`；`doc.attempts` 缺失时才回退扫描后三者。当前后端
   `get_logs` 只在 `attempts` 键投影 attempt（`logs` 为 record-transport 形状,
   被 `isHedgeAttemptShaped` 忽略），故此改动对现有行为零影响，仅消除
   P3-2 描述的未来多键重复渲染风险。

### 2.2 `frontend/self-check.js`（断言 85 所在测试块）

1. `attemptB` 的 `pair_outcome` 由 `'querying'`（后端从不产生的取值）改为
   `null`（后端真实的"在途/查询中"投影），断言列表中的「查询中」现在断言的
   是修复后 `pair_outcome===null → '查询中'` 分支，而非死映射。
2. 新增 `attemptC = mockHedgeAttempt({ ..., pair_outcome: 'single_leg', ... })`
   并加入 `hedgeLogsGetResponse.body.logs` 数组，断言时间线渲染中文标签
   「单腿成交」（`第 3 组`、`单腿成交`、其 residual 字面量 `0.00000200`）。
3. 提取计数断言由 `!== 2` 改为 `!== 3`（新增了 `attemptC` 一条真实 attempt，
   非 attempt 日志条目仍被忽略，覆盖不回归）。
4. 未删除 `accepted_pair`/`confirmed_failed`（`attemptA` 默认
   `pair_outcome: 'accepted_pair'`，断言「已受理」仍在列表中）；缺腿降级
   （`attemptB.perp = null` 断言 `订单号 <span class="mono">—</span>`）、空态
   （断言块 86）、503（断言块 86）均未改动，未回归。

## 3. 为何满足 Review-1

- **P2-1（必须，已修）**：`HEDGE_PAIR_OUTCOME_LABELS`/`HEDGE_PAIR_OUTCOME_BADGE`
  已收录 `single_leg` 中文标签「单腿成交」+ `warning` 徽标；
  `pair_outcome===null` 已映射为「查询中」+ `info` 徽标而非 `—`。未改后端、
  未改 API 合同、未引入 JS 浮点格式化。
- **P3-1（必须，已修）**：self-check 在途用例改用 `pair_outcome:null` 并断言
  「查询中」渲染；新增 `single_leg` 用例断言中文标签渲染；不再依赖后端不产生
  的 `querying` 字符串取值做断言。
- **P3-2（建议，已顺带做）**：`extractHedgeAttempts` 命中 `doc.attempts` 后
  即返回（不再继续合并其余候选键），改动简单、未扩大范围、未破坏现有测试。
- P3-3（attempt_id 展示/去重）、P3-4（分页）、P3-5（交易所状态原样展示）
  为观察项/非阻断，dispatch 未要求，本次未处理。

## 4. 实际执行的命令及结果

```text
$ node frontend/self-check.js
...(前置全部区块 [PASS]，与修复前一致，未列出)
[PASS] 任务卡 real-api-v1 新字段：调度/受理/连续失败/阈值渲染 + 暂停原因 + 旧文档逐项降级 —
[PASS] attempt 时间线：logs 取数 + 两腿字段逐字渲染 + payload 内嵌兼容 + 非 attempt 忽略 + 缺腿降级
[PASS] attempt 时间线降级：空态 + 503 错误横幅 + 恢复
[PASS] 开单 API 全部同源、零跨域 fetch
[PASS] fetch 同源白名单（含开单 §3 路由）、零 Binance/外域、零新任务定时器、localStorage 白名单（仅隐私键）

全部自检通过
```

退出码：`0`（实际执行确认，未编造）。全部约 100+ 项断言块无一失败，包括
新增/修改后的断言 85（single_leg + null→查询中）与既有断言 86（空态/503）、
87（同源/禁 Binance/定时器/localStorage 白名单）。

## 5. 未做的建议项

- P3-3（`attempt_id` 用于渲染或去重）：非阻断，本次未处理。
- P3-4（`?limit=100` 分页/加载更多）：非阻断，已知限制，本次未处理。
- P3-5（交易所 leg status 中文映射）：观察项，非缺陷，本次未处理。

## 6. git diff --stat

```text
 frontend/index.html    | 17 ++++++++++-------
 frontend/self-check.js | 18 ++++++++++++------
 2 files changed, 22 insertions(+), 13 deletions(-)
```

未涉及 `backend/**`、`docs/**`、`status.json`、`70-handoff.md`、API 合同、
环境/密钥文件或任何其他路径。未新增签名、调度、定时器、POST、Binance 直连
或 live 开关。未 git commit。完成后停止，等待 bookkeeper。

---

当前 Session ID: unavailable（Claude Code 本次会话未暴露 provider-native Session ID）
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-frontend-r1.md
本地北京时间: 2026-07-24 11:44:52 CST
下一步模型: bookkeeper
下一步任务: verify the bounded frontend rework, commit its evidence, recompute the frontend task fingerprint, and re-enter review
