<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status: pending
target_model: claude/Claude Opus 5
adapter_cmd:
executor: human_operator
started_at:
completed_at:
session_id: unavailable:pending human execution
outputs: reports/agent-runs/2026-07-hedge-open-real-api-v1/68-review-1-backend-r5.md
next_dispatch: none
fallback_reason: Kimi remains quota-unavailable by the recorded human quota report (15-kimi-review-1-unavailable.md); Codex is quota-exhausted as of 2026-07-25 (the reason the bookkeeper role changed hands). The packet-67 fix author is Claude-GLM/zhipu_glm, so Claude Opus 5 (anthropic) is provider-isolated from every author of the reviewed code, exactly as in rounds r3 and r4.
session_isolation: MUST be a fresh read-only session. The current bookkeeper session authored 66-review-1-backend-r4.md and must not double as the r5 review session (review_1_requires_fresh_read_only_session).
bookkeeper_disclosure: this stage's bookkeeper is Claude Opus 5 (took over 2026-07-25 after Codex quota exhaustion) and also authored the r2/r3/r4 read-only reviews. Neither role is code or fix authorship. See status.json.bookkeeper.dual_hat_disclosure and 27-user-authorized-r4-repair.md §6.
r10_checklist: task_prompt_path=68-review-1-backend-r5.dispatch.md; self_tests_command per the body; next_dispatch_executor=bookkeeper; pass_branch=write 68-review-1-backend-r5.md ending in a schema-valid JSON verdict and stop; blocker_branch=stop and escalate, the reviewer changes no business file; unavailable_branch failure_classes=[model_unavailable, adapter_missing, command_error, permission_error, timeout] escalating to this dispatch file.
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable） ===== -->

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务唯一的正式 Review-1（第一轮交叉复核）后端审查者。禁止调用、启动或转派任何其他模型会话或 adapter。只读：绝不修改业务文件、绝不 commit、绝不读取凭据、绝不连接 Binance、绝不发送真实 POST、绝不启用 live 或 Start。仅可将评审原始输出写入下方指定报告路径。

审查身份：被审后端代码的实现/返工作者为 Claude-GLM（zhipu_glm）。你是 Claude Opus 5（Anthropic），供应商隔离成立。你未写被审后端代码。JSON 中 `reviewer_prior_involvement` 写 `none`，并在叙述中如实披露：同一模型此前产出过 r2/r3/r4 三轮只读 Review-1，且自 2026-07-25 起兼任本 stage 的 bookkeeper（Codex 无额度后交接）——两者都不是代码或修复作者。不得把上一轮的结论或 bookkeeper 的核对结果当作本轮已经成立的事实，必须重新读代码和固定 diff 并自己跑测试。

固定审查锚点（只审此已提交范围；不要改用移动的 HEAD）：
- base: 28c550d87c1ca90983d5bde9c7102d42cffecd4e
- head: b9e1978eaffd047b7871b8721f511307e75fde68
- fingerprint: b9e1978eaffd047b7871b8721f511307e75fde68:604caada1043e8334f33b1cc73239f1cf6bb19017db1dc68374679cf6ac99ddd

## 必须实际阅读

1. `AGENTS.md`；`workflows/templates/stage-delivery.yaml` 的 Review-1 规则；`schemas/review-verdict.schema.json`；
2. `docs/product/PRD.md`（即时开单、风险、实盘门控段落）；
3. stage 的 `00-task.md`、`06-direction-synthesis.md`、`10-design.md`、`11-adr.md`、`15-immediate-loop-and-open-log-amendment.md`、`16-replacement-development-breakdown.md`；
4. 用户后续运行时权威：`21-task-local-runtime-and-manual-pause-amendment.md`、`24-user-authorized-final-guardian-fix.md`、`26-user-authorized-settlement-and-pause-fix.md`、`27-user-authorized-r4-repair.md`；
5. 原始问题与实现证据：`50-review-2.md`、`58-review-1-backend-r2.md`、`64-review-1-backend-r3.md`、`66-review-1-backend-r4.md`、`40-fix-review-1-backend-r2.md`、`42-final-guardian-scanner-fix.md`、`44-fix-review-1-backend-r3.md`、`46-fix-review-1-backend-r4.md`、`60-test-output.txt`；
6. 实际 `git diff --binary 28c550d87c1ca90983d5bde9c7102d42cffecd4e..b9e1978eaffd047b7871b8721f511307e75fde68`，以及相关 `backend/hedge_open_tasks/**`、`backend/services/live_hedge_executor.py`、`backend/tests/test_hedge_*.py` 源码与测试。

## 用户冻结的业务合同（高于旧草案）

- 每张任务卡独立；同一张卡严格先让第 N 组走到终态/对账结束，才可开始第 N+1 组。一组内现货和合约腿仍并发。
- `target_n` 是计划尝试组数硬上限，不因失败或单腿结果补发超出授权数量。
- 不得到 `orderId` 的未知结果必须按 clientOrderId 查询，绝不盲目重发写请求；已受理订单继续查到终态。
- 429、余额/保证金/可用数量不足只暂停当前任务，等待人工恢复；不联动其它任务。其它明确配置错误只停止当前任务。
- 实时模式没有长期全局守护扫描器：启动时可做一次恢复交接；人工 Start/recover 只能启动指定卡；后续下单/查询由各卡自己的有界 worker 完成。
- 默认关闭。没有本次实盘、Start、凭据或真实 Binance 请求授权。

## 本轮必须逐项验证的返工结果（packet 67，用户授权的第 6 次变更，范围仅两项）

1. **P2-1 —— R3/R4 不再是空回归**：`_pump_worker` 现在只在**首次注册**时创建 stop event、已存在则保持原状（不再每次 `ev.clear()`）；R3/R4 各加 `svc._stop_events[tid].is_set() is False` 断言。**你必须自己做反向验证**：把 packet 65 删掉的 `_wake_worker` 中断语义放回 `post_pause` / `post_delete`（只用猴补丁，绝不改仓库文件），确认 R3 与 R4 **确实失败**；再确认当前代码下二者**通过**。同时确认 `ensure_worker` 的生产路径 `ev.clear()` 被保留，`post_pause` / `post_delete` / `_worker_round` 的生产语义**一行未动**。
2. **P2-2 —— DONE 卡的重启恢复**：`_recover_workers` 的只对账兜底元组现为 `(PAUSED, STOPPED, DELETED, DONE)`；新增 `test_r9`。同样**自己反向验证**：去掉 `STATUS_DONE` 后 `test_r9` 必须失败并复现 `66` §4.2 的现象（recovery 不拉 worker、`query_calls=0`、腿永久停在 NEW）；加回后转绿。并确认这条恢复**不会**让 done 卡重新开新组、不会重发写请求（`dispatch_calls` 不增）、`status` 保持 `done` sticky、`finalize_attempt` 幂等不重复计数。
3. **GLM 主动声明的剩余风险是否成立**：`46` §5 自陈"`_pump_worker` 去 clear 后，同实例先 `service.stop()` 再 `_pump_worker` 会短路"。核实当前测试集是否真的没有采用该模式、生产路径是否不受影响，判断它是否构成新缺陷。
4. **reviewer 可选项被拒的合理性**：`66` 的可选 (c)（R3 真实线程版）未实现，GLM 的理由记录在 `46` §2 与 `status.json.r4_repair_authorization.reviewer_optional_item_declined`。判断这个取舍是否可接受，或是否应作为 follow-up。
5. **既有底线不回归**：packet 65 的四项修复（429 恢复清粘滞 + 逐次尝试 `rate_limited` 标记；人工 pause/delete 由本卡 worker drain 后退出且不开新组；`settle_attempt_no_counters` 按两腿真实事实推导并落 `leg_exposure`；`worker_active` 三态 + `last_worker_exit_reason`）必须仍然成立；H-1（live start 一次恢复后返回、live tick 安全空操作、手动 Start 只指定卡）、每卡有界 worker、同卡串行/双腿并发、跨卡隔离、`target_n` 原子上限、clientOrderId-only 查询且不重发、store 锁内不调 executor、preflight price fail-closed、real POST 默认关闭、7 端点冻结 allowlist、签名前置门、`_ENTRY_EVENT_KINDS` 未新增 kind、entries 独立分页兼容旧 logs、`frontend/**` 零改动。
6. **测试与范围**：核对 packet 67 的 230 focused、906 backend、前端自检、Harness 55 的原始证据；独立运行足以验证高风险行为的测试，并检查实际差异无越界（本轮只允许 `service.py` 的两个点 + `test_hedge_task_local.py` + `60-test-output.txt` 追加 + `46` 新建）、无凭据、无实盘激活。

输出完整原始评审到：
`reports/agent-runs/2026-07-hedge-open-real-api-v1/68-review-1-backend-r5.md`

先写中文叙述、findings（P0/P1/P2/P3）与可核对证据，再写标准 Session footer。文件最后一个顶层 JSON 对象必须严格匹配 `schemas/review-verdict.schema.json`：`role=first_reviewer`、`model=Claude Opus 5`、`diff_fingerprint` 必须逐字等于上面值。若 verdict=REWORK，必须提供可直接派发的 `fix_start_prompt`，包含原始证据路径、允许/禁止文件、精确测试命令与验收条件；并注意 `rework_count` 已达上限 6/6，任何进一步代码变更都需要用户新授权，请在报告中明说。完成后停止等待 bookkeeper。

当前 Session ID: report provider-native ID, or unavailable:<reason>
Session ID 来源: runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/68-review-1-backend-r5.md
本地北京时间: obtain from local date command
下一步模型: bookkeeper
下一步任务: validate this renewed backend Review-1 verdict and route it with the preserved frontend ACCEPT
```

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/68-review-1-backend-r5.dispatch.md
本地北京时间: 2026-07-26 CST
下一步模型: human operator
下一步任务: run the prompt body in a FRESH read-only Claude Opus 5 session
