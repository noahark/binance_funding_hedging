<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status: completed
target_model: claude/Claude Opus 5
adapter_cmd:
executor: human_operator
started_at: 2026-07-25T22:56:03+08:00
started_at_source: first `date` command output recorded in the reviewer session that executed this packet
completed_at: 2026-07-25T23:07:10+08:00
completed_at_source: the "本地北京时间" line in the raw report footer (66-review-1-backend-r4.md:328)
session_id: unavailable:the reviewer report footer records that Claude Code did not expose a provider-native Session ID to that session
outputs: reports/agent-runs/2026-07-hedge-open-real-api-v1/66-review-1-backend-r4.md
verdict: REWORK (schema-valid; zero open P0/P1; two P2; diff_fingerprint matched verbatim)
evidence_commit: e10b395
next_dispatch: reports/agent-runs/2026-07-hedge-open-real-api-v1/67-fix-review-1-backend-r4.dispatch.md (human operator)
receipt_backfilled_by: bookkeeper (Claude Opus 5) on 2026-07-26, after Review-2 finding 6 flagged that packets 66/67/68 were left with unsealed receipts. No timestamp or session id was invented; fields without a recorded source are marked unavailable with the reason.
fallback_reason: Kimi remains unavailable by the recorded human quota report (15-kimi-review-1-unavailable.md). The human operator selected Claude Opus 5 for the prior critical backend Review-1; it remains provider-isolated from the Claude-GLM/zhipu_glm backend implementer and fix author.
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable） ===== -->

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务唯一的正式 Review-1（第一轮交叉复核）后端审查者。禁止调用、启动或转派任何其他模型会话或 adapter。只读：绝不修改业务文件、绝不 commit、绝不读取凭据、绝不连接 Binance、绝不发送真实 POST、绝不启用 live 或 Start。仅可将评审原始输出写入下方指定报告路径。

审查身份：被审后端代码的实现/返工作者为 Claude-GLM（zhipu_glm）。你是 Claude Opus 5（Anthropic），供应商隔离成立。你未写被审后端代码；你上一轮只读 Review-1 的 `REWORK` 及其修复要求是本次被核验的原始证据。JSON 中 `reviewer_prior_involvement` 写 `none`，并在叙述中如实披露这一点。不得把你自己的上一轮结论当作本轮已经成立的事实，必须重新读代码和固定 diff。

固定审查锚点（只审此已提交范围；不要改用移动的 HEAD）：
- base: 28c550d87c1ca90983d5bde9c7102d42cffecd4e
- head: 9d1bac071e30a57fe9c0619fb0c3cd59ccc4ce3c
- fingerprint: 9d1bac071e30a57fe9c0619fb0c3cd59ccc4ce3c:fbf52f40fbebe7018bdf6e460d7f2e4855519c52e3a6403151db420aa13d99db

## 必须实际阅读

1. `AGENTS.md`；`workflows/templates/stage-delivery.yaml` 的 Review-1 规则；`schemas/review-verdict.schema.json`；
2. `docs/product/PRD.md`（即时开单、风险、实盘门控段落）；
3. stage 的 `00-task.md`、`06-direction-synthesis.md`、`10-design.md`、`11-adr.md`、`15-immediate-loop-and-open-log-amendment.md`、`16-replacement-development-breakdown.md`；
4. 用户后续运行时权威：`21-task-local-runtime-and-manual-pause-amendment.md`、`24-user-authorized-final-guardian-fix.md`、`26-user-authorized-settlement-and-pause-fix.md`；
5. 原始问题与实现证据：`50-review-2.md`、`58-review-1-backend-r2.md`、`64-review-1-backend-r3.md`、`40-fix-review-1-backend-r2.md`、`42-final-guardian-scanner-fix.md`、`44-fix-review-1-backend-r3.md`、`60-test-output.txt`；
6. 实际 `git diff --binary 28c550d87c1ca90983d5bde9c7102d42cffecd4e..9d1bac071e30a57fe9c0619fb0c3cd59ccc4ce3c`，以及相关 `backend/hedge_open_tasks/**`、`backend/services/live_hedge_executor.py`、`backend/tests/test_hedge_*.py` 源码与测试。

## 用户冻结的业务合同（高于旧草案）

- 每张任务卡独立；同一张卡严格先让第 N 组走到终态/对账结束，才可开始第 N+1 组。一组内现货和合约腿仍并发。
- `target_n` 是计划尝试组数硬上限，不因失败或单腿结果补发超出授权数量。
- 不得到 `orderId` 的未知结果必须按 clientOrderId 查询，绝不盲目重发写请求；已受理订单继续查到终态。
- 429、余额/保证金/可用数量不足只暂停当前任务，等待人工恢复；不联动其它任务。其它明确配置错误只停止当前任务。
- 实时模式没有长期全局守护扫描器：启动时可做一次恢复交接；人工 Start/recover 只能启动指定卡；后续下单/查询由各卡自己的有界 worker 完成。
- 默认关闭。没有本次实盘、Start、凭据或真实 Binance 请求授权。

## 本轮必须逐项验证的返工结果

1. **429 → 人工恢复**：进入 RUNNING 必须清 `pause_reason` / `pause_reason_zh`；429 组的“不计失败”必须只来自该 attempt 自身的限频事实。核验恢复后 FILLED 组正确计 accepted/success，恢复后的三次真实确认失败仍触发本卡阈值暂停，且非限频的 fatal 对账不被跳过。
2. **人工 pause/delete 的对账收尾**：已有在飞腿时，暂停或删除不得中断对应任务 worker；它只能查自己的 clientOrderId 至终态、结算这一组、绝不开下一组后退出。确认 DELETED 任务若遗留未终态腿，进程重启时的一次 recovery 也会启动该任务的 drain-only worker；不能借此恢复周期 tick、全局 scanner、timer 或跨卡联动。
3. **429 组的真实结果**：`settle_attempt_no_counters` 必须不增长失败/阈值计数，但仍根据两腿的真实 orderId 得出 accepted_pair、single_leg 或 confirmed_failed；single_leg 必须落 advisory `leg_exposure`。
4. **可观测字段（用户选择 A）**：`worker_active` 在 live 可派发模式是从 worker 注册表派生的 true/false，dry-run 必为 null；`last_worker_exit_reason` 是加性、可空且稳定的机器枚举，worker 的退出/异常路径写入，进入 RUNNING 清除。两字段必须在 task API 字段集内；不新增 entries event、不改前端。
5. **既有底线不回归**：H-1（live start 一次恢复后返回；live tick 安全空操作；手动 Start 只指定卡）、每卡有界 worker、同卡串行/双腿并发、跨卡隔离、target_n 原子上限、clientOrderId-only 查询且不重发、store 锁内不调 executor、preflight price fail-closed、real POST 默认关闭、entries 独立分页兼容旧 logs。
6. **测试与范围**：核对 packet 65 的 229 focused、905 backend、前端 self-check、Harness 55 的原始证据；独立运行足以验证高风险行为的测试，并检查实际差异无越界、无凭据、无实盘激活。

输出完整原始评审到：
`reports/agent-runs/2026-07-hedge-open-real-api-v1/66-review-1-backend-r4.md`

先写中文叙述、findings（P0/P1/P2/P3）与可核对证据，再写标准 Session footer。文件最后一个顶层 JSON 对象必须严格匹配 `schemas/review-verdict.schema.json`：`role=first_reviewer`、`model=Claude Opus 5`、`diff_fingerprint` 必须逐字等于上面值。若 verdict=REWORK，必须提供可直接派发的 `fix_start_prompt`，包含原始证据路径、允许/禁止文件、精确测试命令与验收条件。完成后停止等待 bookkeeper。

当前 Session ID: report provider-native ID, or unavailable:<reason>
Session ID 来源: runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/66-review-1-backend-r4.md
本地北京时间: obtain from local date command
下一步模型: bookkeeper
下一步任务: validate this renewed backend Review-1 verdict and route it with the preserved frontend ACCEPT
```

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/66-review-1-backend-r4.dispatch.md
本地北京时间: 2026-07-25 22:21:14 CST
下一步模型: human operator
下一步任务: run the prompt body in a fresh read-only Claude Opus 5 session
