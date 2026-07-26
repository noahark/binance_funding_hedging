<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status: pending
target_model: claude/Claude Opus 5
adapter_cmd:
executor: human_operator
started_at:
completed_at:
session_id: unavailable:pending human execution
outputs: reports/agent-runs/2026-07-hedge-open-real-api-v1/73-review-1-backend-r6.md
next_dispatch: none
fallback_reason: Kimi remains quota-unavailable by the recorded operator report (15-kimi-review-1-unavailable.md). The packet-72 fix author is Claude-GLM/zhipu_glm, so Claude Opus 5 (anthropic) is provider-isolated from every author of the reviewed code, exactly as in rounds r3, r4 and r5.
session_isolation: MUST be a fresh read-only session. The current bookkeeper session authored the r2/r3/r4/r5 reviews and must not double as the r6 review session (review_1_requires_fresh_read_only_session).
bookkeeper_disclosure: this stage's bookkeeper is Claude Opus 5 (took over 2026-07-25 after Codex quota exhaustion) and also authored the r2-r5 read-only Review-1 reports. Neither role is code or fix authorship. See status.json.bookkeeper.dual_hat_disclosure and 27-user-authorized-r4-repair.md §6.
r10_checklist: task_prompt_path=73-review-1-backend-r6.dispatch.md; self_tests_command per the body; next_dispatch_executor=bookkeeper; pass_branch=write 73-review-1-backend-r6.md ending in a schema-valid JSON verdict and stop; blocker_branch=stop and escalate, the reviewer changes no business file; unavailable_branch failure_classes=[model_unavailable, adapter_missing, command_error, permission_error, timeout] escalating to this dispatch file.
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable） ===== -->

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务唯一的正式 Review-1（第一轮交叉复核）后端审查者。禁止调用、启动或转派任何其他模型会话或 adapter。只读：绝不修改业务文件、绝不 commit、绝不读取凭据、绝不连接 Binance、绝不发送真实 POST、绝不启用 live 或 Start。仅可将评审原始输出写入下方指定报告路径。

审查身份：被审后端代码的实现/返工作者为 Claude-GLM（zhipu_glm）。你是 Claude Opus 5（Anthropic），供应商隔离成立。你未写被审后端代码。JSON 中 `reviewer_prior_involvement` 写 `none`，并在叙述中如实披露：同一模型此前产出过 r2/r3/r4/r5 四轮只读 Review-1，且自 2026-07-25 起兼任本 stage 的 bookkeeper —— 两者都不是代码或修复作者。不得把上一轮结论、实现报告的声称、或 bookkeeper 的核对结果当作本轮已成立的事实，必须重新读代码、重新算指纹、自己跑测试、自己做反向验证。

固定审查锚点（只审此已提交范围；不要改用移动的 HEAD）：
- base: 28c550d87c1ca90983d5bde9c7102d42cffecd4e
- head: 77c75bd855c3d1a7a4c91700f9db953919df087f
- fingerprint: 77c75bd855c3d1a7a4c91700f9db953919df087f:aa0406dae9cb90004d5dd15c2a936ad9a021a0c01a50f985d4efab5900e652dd

## 必须实际阅读

1. `AGENTS.md`；`workflows/templates/stage-delivery.yaml` 的 Review-1 规则；`schemas/review-verdict.schema.json`；
2. `docs/product/PRD.md`（即时开单、风险、实盘门控段落）；
3. stage 的 `00-task.md`、`06-direction-synthesis.md`、`10-design.md`、`11-adr.md`、`15-immediate-loop-and-open-log-amendment.md`、`16-replacement-development-breakdown.md`；
4. 用户后续运行时权威：`21-task-local-runtime-and-manual-pause-amendment.md`、`24-user-authorized-final-guardian-fix.md`、`26-user-authorized-settlement-and-pause-fix.md`、`27-user-authorized-r4-repair.md`、**`28-user-authorized-r7-repair.md`（本轮范围的最高权威，含用户明确排除项）**；
5. 原始问题与实现证据：`69-review-2.md`（Review-2 的六条 P1 原文）、`68-review-1-backend-r5.md`、`66-review-1-backend-r4.md`、`46-fix-review-1-backend-r4.md`、**`71-fix-review-2-backend-r7.md`（本轮实现报告）**、`60-test-output.txt`；
6. 实际 `git diff --binary 28c550d87c1ca90983d5bde9c7102d42cffecd4e..77c75bd855c3d1a7a4c91700f9db953919df087f`，以及 `backend/hedge_open_tasks/**`、`backend/services/live_hedge_executor.py`、`backend/tests/test_hedge_*.py`、`scripts/validate-stage.py` 源码与测试。

## 用户冻结的业务合同（高于旧草案）

- 每张任务卡独立；同一张卡严格先让第 N 组走到终态/对账结束，才可开始第 N+1 组。一组内现货和合约腿仍并发。
- `target_n` 是计划尝试组数硬上限，不因失败或单腿结果补发超出授权数量。
- 不得到 `orderId` 的未知结果必须按 clientOrderId 查询，绝不盲目重发写请求；已受理订单继续查到终态。
- 429、余额/保证金/可用数量不足只暂停当前任务，等待人工恢复；不联动其它任务。其它明确配置错误只停止当前任务。
- 实时模式没有长期全局守护扫描器：启动时可做一次恢复交接；人工 Start/recover 只能启动指定卡；后续下单/查询由各卡自己的有界 worker 完成。
- 默认关闭。没有本次实盘、Start、凭据或真实 Binance 请求授权。

## 用户对本轮的范围裁定（`28-user-authorized-r7-repair.md`，必须遵守）

用户产品方向原话：「我们的目标是尽快上线验证，在实盘中再发现问题做优化。不要在设计阶段太关注低概率场景发生的事情」。

**本轮只授权修四项**（Review-2 的 F1 / F2 / F4 + finding-6 的 validator 剩余项）。
用户**明确排除**下列各项，**不得**因其未修而给出 P0/P1 或据此 REWORK；如认为风险被低估，写入 `residual_risks` 或 P3 并说明理由即可：

- **Review-2 F3**（人工 delete/pause 被迟到 worker 结果覆盖的状态守卫）—— 用户裁定暂不修。连带：不引入 `requested_action`/命令队列，不改 API 语义，`frontend/**` 零改动。
- **Review-2 F5**（账户健康 `accountStatus`/`uniMMR` + 现货 `MIN_NOTIONAL`）—— 用户裁定不做；七端点 allowlist 保持冻结，`hedge_open_live_client.py` 与 `hedge_preflight_provider.py` 本轮禁改。用户以「输入端自行保证数量足够」作为操作约定。
- 排队期间取消删除、`aggregate_positions` 过滤 `deleted`、r4/r5 既有 P3、跨进程预留守卫、`X-MBX-ORDER-COUNT-*` 节流、前端展示 `worker_active` —— 全部后置 follow-up。

## 本轮必须逐项验证的返工结果（packet 72）

1. **F1 —— single_leg 计入连续失败刹车 + 计划组用尽转 done**：非限频、非致命的 `single_leg` 必须累加 `fail_count`/`consecutive_submission_failures` 并在达到任务快照阈值时暂停；**429 组必须继续免计数**（不得回归 packet 65 的逐次尝试 `rate_limited` 语义）；单腿敞口的 advisory `leg_exposure` 必须仍然记录且不冻结调度。最后一笔计划 attempt 结算后正确转 `done`。
   **注意一个已知的语义变更**：`consecutive_submission_failures` 是前端冻结字段集内的字段，其**含义**本轮改变了（single_leg 现在也会让它增长）。字段集未变、前端无需改代码，但请判断这是否与已批准的产品语义一致，并评估是否应记前端展示 follow-up。
2. **F2 —— 查询分类与查询阶段限频（本轮风险最高项）**：`classify_query_response` 必须只把**显式** 404 / `-2013` 当作确认未受理；2xx 缺有效 `orderId` 必须保持 `UNKNOWN_QUERYING`；查询阶段 429/`-1003`/418 必须产出 typed rate-limit 信号，由该卡 worker 持久化 `paused`+`rate_limited`、保留未决腿、退出等人工恢复，**绝不重发 POST**。请**自己**核验：5xx、transport error、auth 4xx 是否**仍然**返回 `None`（没有矫枉过正把它们变成 absent 或 rate-limited）。
3. **F4 —— 两腿终态但 `pair_outcome` 为 NULL 的崩溃缝隙**：恢复必须能结算该组、把真实成交计回计数器、幂等（重复轮次不重复计数）、零重发、不开新组、不忙循环、**不得新增任何常驻 guardian/scanner/timer**。请覆盖 running/paused/stopped/deleted/done 各状态与 429 免计数路径。
4. **F6 —— validator 覆盖**：`scripts/validate-stage.py` 新增的两项检查（回执 `pending` 但产出已存在、根 `status` 与工作流阶段不一致）是否正确、是否会误报。**事实记录**：该 validator 首次运行即检出两条真实漂移（packet 59 与 69 的回执），均已由 bookkeeper 依据既有报告 footer 证据封存，未发明任何时间或 Session ID。
5. **既有底线不回归**：packet 62/63/65/67 的全部性质（H-1 三防线；每卡有界 worker；同卡串行/双腿并发；跨卡隔离；`target_n` 原子上限；clientOrderId-only 查询且不重发；store 锁内不调 executor；preflight fail-closed；real POST 默认关闭；7 端点冻结 allowlist；签名前置门；`_ENTRY_EVENT_KINDS` 未新增 kind；entries 分页兼容；`R1`–`R9` 回归）必须仍然成立。**`frontend/**` 必须零改动**（前端 Review-1 的 ACCEPT 依赖这一点）。
6. **范围与测试**：核对 227 focused / 918 backend / 前端自检 / validator 67 / `git diff --check` 的原始证据并独立复跑。核查实际差异无越界。
   **一项已由 bookkeeper 裁定的边界事项，请独立复核该裁定是否恰当**：`backend/tests/test_hedge_api.py` 有 4 行改动（冻结断言 `consecutive_submission_failures` 由 `0` 改 `1` + 两行注释），该文件**不在** `28` §4 的允许清单内，但 `28` §5 的强制自测命令又要求它全绿 —— 这是 bookkeeper 所写授权书的内在矛盾。bookkeeper 裁定为「packet 缺陷，非实现者越界，接受该最小改动」，并记录实现者主动披露而非隐瞒是正确行为。请判断该裁定是否成立。

## 自测命令（供你独立复跑）

```bash
.venv/bin/python -m pytest backend/tests -q
node frontend/self-check.js
.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q
.venv/bin/python scripts/validate-stage.py 2026-07-hedge-open-real-api-v1 --phase pre-review
git diff --check
```

输出完整原始评审到：
`reports/agent-runs/2026-07-hedge-open-real-api-v1/73-review-1-backend-r6.md`

先写中文叙述、findings（P0/P1/P2/P3）与可核对证据，再写标准 Session footer。文件最后一个顶层 JSON 对象必须严格匹配 `schemas/review-verdict.schema.json`：`role=first_reviewer`、`model=Claude Opus 5`、`diff_fingerprint` 必须逐字等于上面值。

**注意 `rework_count` 已达上限 7/7**：若 verdict=REWORK，必须提供可直接派发的 `fix_start_prompt`，并在报告中明说任何进一步代码变更都需要用户**新的书面授权**，bookkeeper 不能自行派发。若 verdict=ACCEPT，请说明本次 ACCEPT **不**解除任何实盘门，并说明本 stage 是否可以进入新一轮 Review-2（终审）。完成后停止等待 bookkeeper。

当前 Session ID: report provider-native ID, or unavailable:<reason>
Session ID 来源: runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/73-review-1-backend-r6.md
本地北京时间: obtain from local date command
下一步模型: bookkeeper
下一步任务: validate this renewed backend Review-1 verdict and route it toward a new Review-2 with the preserved frontend ACCEPT
```

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/73-review-1-backend-r6.dispatch.md
本地北京时间: 2026-07-26 CST
下一步模型: human operator
下一步任务: run the prompt body in a FRESH read-only Claude Opus 5 session
