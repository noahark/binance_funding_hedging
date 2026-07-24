<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status: pending
target_model: claude/Claude Sonnet 5
adapter_cmd:
executor: human_operator
started_at:
completed_at:
session_id: unavailable:pending human execution
outputs: reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-review-2-frontend.md
next_dispatch: none
supersedes: 53-review-2-rework-frontend.dispatch.md (never executed; do not run it)
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable） ===== -->

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务唯一的前端返工实现者。禁止调用、启动或转派任何其他模型/adapter。
只可在本任务范围内写代码；绝不读取凭据、绝不连接 Binance、绝不发真实 POST，
绝不 commit、绝不改 status.json、70-handoff.md、PRD、设计/ADR 或后端。

这是终审 REWORK（需要返工）的前端子任务，且执行合同已被用户批准的修正案替换。
按顺序逐字阅读：
1. `reports/agent-runs/2026-07-hedge-open-real-api-v1/15-immediate-loop-and-open-log-amendment.md`
   —— 用户批准的修正案，节奏/错误矩阵/开单日志的最高权威；
2. `reports/agent-runs/2026-07-hedge-open-real-api-v1/16-replacement-development-breakdown.md`
   —— 本轮替换拆分（前端需求 B-1..B-4、冻结 entries 契约 §5、任务态 I-4）；
3. `reports/agent-runs/2026-07-hedge-open-real-api-v1/50-review-2.md`
   —— 原始终审 findings（前端为必须项 7，最后 JSON 是原始 verdict）；
4. `{04-user-execution-policy.md,06-direction-synthesis.md,10-design.md,11-adr.md,12-development-breakdown.md}`。
冲突时以 15 号修正案为准：**每任务一个顺序执行的活动组**替换旧的每秒一组节奏；
旧包 53 已作废，不得按它执行。被审历史指纹（仅审计锚点）：
`01d3a4712c89efab79772ce2e5ee2ba415e1e43c:c3368f63670e896cbe585293c4ff7261ba55c165346efd4ea27f672be1b91cff`。

你的必须修复范围 = 16 号拆分 B-1..B-4：
1. 语义返工（终审必须项 7 + 修正案更新）：`target_n` 一律显示"计划尝试次数"，
   不得再写"成功开单次数"。失败计数、暂停/终止原因、按钮状态和阈值只从后端任务
   doc 读取（`failure_pause_threshold`、`consecutive_submission_failures`、
   `status`、`pause_reason`、`stop_reason`）；删除硬编码 `/3`、旧累计失败 `>3`
   推导和任何与后端相反的禁用逻辑。
2. 状态展示：区分渲染 `stopped`（致命错误，任务已终止，需修正后新建任务）与
   `paused`（连续失败暂停/手动暂停）。`single_leg` 显示单腿成交警示 + "任务仍
   继续调度"（除非后端 status 为 paused/stopped）；绝不再显示虚假的"任务已暂停/
   等待人工处理"。查询中的组显示"查询中/等待终态"。
3. 新增「开单日志」页：在「开单任务」旁加独立 tab，交互对齐现有借币日志页
   （newest-first、刷新、加载更多），读取同源 `GET /api/hedge-open-logs` 响应中
   16 号拆分 §5 冻结的 `entries` 数组。每行按修正案字段清单渲染：事件时间
   （创建/提交/终态）、任务 ID、币种、方向、尝试序号、计划 q_common 与预计金额、
   两腿实际 base/quote、每腿 side/orderId/client ID/交易所状态/累计量/均价/
   手续费、整体结果（查询中/双腿受理/已成交/单腿/确认失败/任务终止/任务暂停）、
   安全错误 category/code 与中文原因、任务下一步动作；缺失字段渲染 `—`。
   不加浏览器签名、Binance 直连或任何新的不安全写端点。中文优先；Decimal 字符串
   原样显示。任务内紧凑时间线可保留，但日志页必须是操作者能看到失败的权威位置。
4. 扩展 `frontend/self-check.js`：覆盖计划尝试语义、stopped/paused/single_leg/
   查询中渲染、自定义阈值显示、开单日志 tab（分页、`—` 降级、无 orderId 错误行、
   任务事件行）；不得只测静态文案。

允许修改仅限：
- `frontend/index.html`
- `frontend/self-check.js`
- `reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-review-2-frontend.md`

禁止修改所有 `backend/**`、`docs/**`、`reports/api-samples/**`、`status.json`、
`70-handoff.md`、`50-review-2.md`、`15-immediate-loop-and-open-log-amendment.md`、
`16-replacement-development-breakdown.md`、环境/凭据文件和其他路径。后端字段不足、
改名或与 §5 契约不符时，不得发明字段，写报告并停止让 bookkeeper 协调。mock 中的
`entries` 数据必须逐字段符合 §5 契约。

实际执行并如实记录：
`node frontend/self-check.js`
`.venv/bin/python -m pytest backend/tests -q`
`.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q`
`git diff --check`

把完整原始实现说明、实际命令输出摘要、finding→fix 映射（含修正案条目映射）、
已知剩余风险和 changed files 写到 `40-fix-review-2-frontend.md` 并停止。为避免并行
写同一审计文件，不要修改 `60-test-output.txt`；bookkeeper 会原样汇总你的测试输出。
不要 commit、不要评审、不要派发。

当前 Session ID: report provider-native ID, or unavailable:<reason>
Session ID 来源: runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-review-2-frontend.md
本地北京时间: obtain from local date command
下一步模型: bookkeeper
下一步任务: collect the bounded frontend fix, reconcile its diff, and run integration evidence
```

当前 Session ID: 94305f00-bde4-4d80-a69e-091eddffcbe7
Session ID 来源: runtime_env (harness scratchpad path; navigation only)
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/55-review-2-rework-frontend.dispatch.md
本地北京时间: 2026-07-24 14:55:04 CST
下一步模型: human operator
下一步任务: run the prompt body in a fresh write-capable Claude Sonnet 5 session (after bookkeeper records this packet)
