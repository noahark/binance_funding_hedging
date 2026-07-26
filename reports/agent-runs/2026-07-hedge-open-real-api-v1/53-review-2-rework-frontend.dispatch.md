<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status: superseded
target_model: claude/Claude Sonnet 5
adapter_cmd:
executor: human_operator
started_at: n/a:never executed
completed_at: n/a:never executed
session_id: n/a:never executed
outputs: reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-review-2-frontend.md
next_dispatch: none
superseded_reason: superseded before execution by 55-review-2-rework-frontend.dispatch.md; status.json scope_amendment.supersedes
receipt_backfilled_by: bookkeeper (Claude Opus 5) on 2026-07-27. This packet was replaced before any execution, so a terminal 'superseded' state — not 'pending' — is the truthful record. Its declared outputs file exists only because a LATER packet produced it.
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable） ===== -->

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务唯一的前端返工实现者。禁止调用、启动或转派任何其他模型/adapter。
只可在本任务范围内写代码；绝不读取凭据、绝不连接 Binance、绝不发真实 POST，
绝不 commit、绝不改 status.json、70-handoff.md、PRD、设计/ADR 或后端。

这是终审 REWORK（需要返工）的前端子任务。完整、未改写的 reviewer fix_start_prompt
和全部 findings 都在 `reports/agent-runs/2026-07-hedge-open-real-api-v1/50-review-2.md`
最后 JSON 中：先逐字阅读它，再阅读
`{04-user-execution-policy.md,05-cadence-resolution.md,06-direction-synthesis.md,10-design.md,11-adr.md,12-development-breakdown.md}`。
本 dispatch 只做文件边界拆分，不改变 reviewer 的要求、测试或验收口径。
固定被审指纹是：
`01d3a4712c89efab79772ce2e5ee2ba415e1e43c:c3368f63670e896cbe585293c4ff7261ba55c165346efd4ea27f672be1b91cff`。

你的必须修复范围是 reviewer 必须项 7：
- `target_n` 必须以“计划尝试次数/组数”解释，不能再写“成功开单次数”。
- 单腿 `single_leg` 必须明确显示“提示，但任务仍继续调度”，绝不再显示“任务已暂停”
  或“等待人工处理”来暗示系统已停止。
- 失败计数、暂停原因、按钮状态和阈值只从后端返回的任务 status 与任务级
  `failure_pause_threshold` 读取；删除硬编码 `/3`、旧累计失败 `>3` 推导和任何与
  后端相反的禁用逻辑。
- 保持中文、Decimal 原样显示、同源 API、零浏览器签名/调度/Binance 直连；不新增自动
  补单、取消、平仓、借还币、转账、smooth/WebSocket、风险上限或真实网络测试。
- 新增 self-check，证明 target 计划语义、single_leg 的真实提示语、后端 paused 状态和
  自定义阈值的降级显示；不得只测静态文案。

允许修改仅限：
- `frontend/index.html`
- `frontend/self-check.js`
- `reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-review-2-frontend.md`

禁止修改所有 `backend/**`、`docs/**`、`reports/api-samples/**`、`status.json`、
`70-handoff.md`、`50-review-2.md`、环境/凭据文件和其他路径。后端字段不足或改名时，
不得发明，写报告并停止让 bookkeeper 协调。

实际执行并如实记录：
`node frontend/self-check.js`
`.venv/bin/python -m pytest backend/tests -q`
`.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q`
`git diff --check`

把完整原始实现说明、实际命令输出摘要、finding→fix 映射、已知剩余风险和 changed files
写到 `40-fix-review-2-frontend.md` 并停止。为避免并行写同一审计文件，不要修改
`60-test-output.txt`；bookkeeper 会原样汇总你的测试输出。不要 commit、不要评审、不要派发。

当前 Session ID: report provider-native ID, or unavailable:<reason>
Session ID 来源: runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-review-2-frontend.md
本地北京时间: obtain from local date command
下一步模型: bookkeeper
下一步任务: collect the bounded frontend fix, reconcile its diff, and run integration evidence
```

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/53-review-2-rework-frontend.dispatch.md
本地北京时间: 2026-07-24 13:49:15 CST
下一步模型: human operator
下一步任务: run the prompt body in a fresh write-capable Claude Sonnet 5 session
