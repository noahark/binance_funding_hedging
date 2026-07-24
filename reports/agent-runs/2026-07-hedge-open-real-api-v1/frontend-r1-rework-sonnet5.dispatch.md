<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status: pending
target_model: Claude Sonnet 5 (user-selected frontend fallback)
adapter_cmd:
executor: human_operator
started_at:
completed_at:
session_id: unavailable:pending human execution
outputs: reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-frontend-r1.md
next_dispatch: none
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable） ===== -->

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是本修复任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于 claude-glm -p、
   kimi -p、codex exec、grok）。需要其他模型时输出 ESCALATED 及原因并停止。
2. 禁止编造未实际执行的命令结果或未实际读取的文件内容；每一条执行记录必须对应本会话
   内真实发生的动作。
3. 修复依据只能是本 prompt 列出的原始证据路径和你实际读取的文件。

你是用户指定的前端 fallback（替补）修复者，执行 Task B 的 Review-1 REWORK（需要返工）。
这是一项很小的页面显示修复：让用户能看懂订单「还在查询」和「只成交一条腿」两种状态。
不要修改下单逻辑、后端、API 合同、风控规则或任何 Binance 访问行为。

先阅读以下原始证据，不要只依赖本任务摘要：
- AGENTS.md、agents/developer-discipline.md；
- reports/agent-runs/2026-07-hedge-open-real-api-v1/{00-task.md,10-design.md,11-adr.md,12-development-breakdown.md,20-implementation-frontend.md,30-review-1-frontend.md,40-fix-backend-r4.md}；
- frontend/index.html、frontend/self-check.js；
- backend/hedge_open_tasks/{domain.py,service.py}（仅用于核对状态取值，严禁修改）。

Review-1 原始裁定在 `30-review-1-frontend.md`，必须逐条遵守。核心事实：
- `single_leg`（只成交一条腿）：需要显示中文「单腿成交」和警示色，不能让用户看到难懂的
  英文代码。
- `pair_outcome: null`（该组订单还在查询、尚无最终结果）：需要显示「查询中」，不能显示
  `—`（没有数据）。
- 保留已有 `querying`（查询中）映射以兼容领域状态；不要凭空删除后端可能使用的状态。

允许修改仅限：
- frontend/index.html
- frontend/self-check.js
- reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-frontend-r1.md

禁止修改：所有 backend/**、docs/**、status.json、70-handoff.md、API contract、环境/密钥
文件及其他任何路径。不得新增签名、调度、定时器、POST、Binance 直连或 live 开关。

必须完成：
1. 在 `HEDGE_PAIR_OUTCOME_LABELS` 和 `HEDGE_PAIR_OUTCOME_BADGE` 中添加 `single_leg` 的
   中文标签「单腿成交」和 warning（警示）徽标。
2. 修改 `renderHedgeAttemptCard`：`pair_outcome === null` 时显示「查询中」和 info（提示）
   徽标；不要把它显示为 `—`。
3. 更新 `frontend/self-check.js`：
   - 将在途 attempt 示例改为 `pair_outcome: null`，断言页面显示「查询中」；
   - 新增 `pair_outcome: 'single_leg'` 示例，断言页面显示「单腿成交」；
   - 已受理、已确认失败、缺腿、空态和 503（服务暂时不可用）检查不能回归。
4. 建议但非硬性：在 `extractHedgeAttempts` 优先使用 `doc.attempts`，或按 `attempt_id`
   去重，避免同一订单尝试在未来被重复显示。仅当改动简单、不会扩大范围时做。

数字纪律不变：所有十进制字符串必须继续原样显示，禁止引入 JavaScript 浮点数格式化。

必须实际运行：
node frontend/self-check.js

验收条件：
- `node frontend/self-check.js` 全部 PASS，退出码 0；
- 页面能把「单腿成交」和「查询中」正确、中文、可见地显示；
- 没有前端直连 Binance、没有新定时器、没有后端/API 合同改动；
- `git diff --stat` 只涉及上述两个前端文件和本修复报告。

将完整、未经编辑的修复报告写到：
`reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-frontend-r1.md`

报告必须包含：修改了什么、为何满足 Review-1、实际执行的命令及结果、未做的建议项、
`git diff --stat`。报告末尾必须带 footer。完成后停止，等待 bookkeeper；不要 commit、
不要改 status.json、不要派发或评审其他模型。

当前 Session ID: report provider-native ID, or unavailable:<reason>
Session ID 来源: runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-frontend-r1.md
本地北京时间: obtain from local date command
下一步模型: bookkeeper
下一步任务: verify the bounded frontend rework, commit its evidence, recompute the frontend task fingerprint, and re-enter review
```

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/frontend-r1-rework-sonnet5.dispatch.md
本地北京时间: 2026-07-24 11:39:01 CST
下一步模型: human operator
下一步任务: run the prompt body in the user-selected Sonnet 5 frontend implementation session
