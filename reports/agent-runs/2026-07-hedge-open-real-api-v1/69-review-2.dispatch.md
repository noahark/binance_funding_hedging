<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status: completed
target_model: codex/GPT-5 Codex
adapter_cmd:
executor: human_operator
started_at: unavailable:no start timestamp was recorded by the operator or the report
completed_at: 2026-07-26T14:07:11+08:00
completed_at_source: the "本地北京时间" line in the raw report footer (69-review-2.md:174)
session_id: unavailable:the report footer records that the current Codex runtime does not expose a provider-native Session ID
outputs: reports/agent-runs/2026-07-hedge-open-real-api-v1/69-review-2.md
verdict: REWORK (final gate; six P1; next_action=human_escalation_required; schema-valid; fingerprint matched verbatim)
next_dispatch: reports/agent-runs/2026-07-hedge-open-real-api-v1/72-fix-review-2-backend-r7.dispatch.md (human operator)
receipt_backfilled_by: bookkeeper (Claude Opus 5) on 2026-07-26. The verdict and session receipt were registered in status.json when the report landed, but this RECEIPT header was left at pending — the bookkeeper's own oversight, caught automatically by the new finding-6 validator check delivered in packet 72 on its first run. Evidence is taken only from the report footer; nothing was invented.
routing_reason: Codex is the ONLY provider eligible as final reviewer. AGENTS.md bars the final reviewer from sharing provider identity with ANY delivery-code author, with no override: anthropic is hard-barred (Claude Sonnet 5 authored the accepted frontend rework), zhipu_glm is hard-barred (backend author), kimi and grok are quota-unavailable per recorded operator reports. Codex never wrote delivery or fix code (status.json model_routing.excluded_from_core_implementation_and_fix = ["codex"]). Full analysis: 46-review-2-routing-disclosure.md.
quota_note: Codex quota was exhausted on 2026-07-25 (the reason the bookkeeper role changed hands) and the human operator reported it restored on 2026-07-26. The stage was formally halted at decision_models_exhausted in the interim; this dispatch resumes it.
design_conflict_override: used. Codex is this stage's designer (00-task.md, 10-design.md, 11-adr.md) and direction synthesizer (06-direction-synthesis.md), and authored the earlier Review-2 (50-review-2.md, REWORK, at the stale anchor 01d3a47). reviewer_prior_involvement must be "design". Evidence: 46-review-2-routing-disclosure.md.
second_opinion_check: this is NOT a second opinion on 50-review-2.md. That verdict was valid, was acted on, and covers a stale range. This is the first final-gate review of the current 28c550d..b9e1978 range.
bookkeeper_disclosure: the current bookkeeper is Claude Opus 5, which ALSO authored the r2/r3/r4/r5 backend Review-1 reports. It took over from Codex on 2026-07-25. The reviewer is explicitly asked to scrutinise whether that dual hat damaged the evidence chain.
r10_checklist: task_prompt_path=69-review-2.dispatch.md; self_tests_command per the body; next_dispatch_executor=bookkeeper; pass_branch=write 69-review-2.md ending in a schema-valid JSON verdict and stop; blocker_branch=stop and escalate, the reviewer changes no business file; unavailable_branch failure_classes=[model_unavailable, adapter_missing, command_error, permission_error, timeout] escalating to this dispatch file.
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable） ===== -->

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是本 stage 的正式 Review-2（终审门）。禁止调用、启动或转派任何其他模型会话或 adapter。只读：绝不修改业务文件、绝不 commit、绝不读取凭据、绝不连接 Binance、绝不发送真实 POST、绝不启用 live 或 Start。仅可将评审原始输出写入下方指定报告路径。

## 你的身份与必须如实披露的四件事

你是 GPT-5 Codex（provider `codex`）。你**从未**为本 stage 写过交付代码或修复代码
（`status.json` 的 `model_routing.excluded_from_core_implementation_and_fix = ["codex"]`），
因此终审的「不得与任何交付代码作者同 provider」这条硬禁对你成立。但以下四点必须在报告中如实披露：

1. **你是本 stage 的设计者与方向综合者**：`00-task.md`、`10-design.md`、`11-adr.md`、
   `06-direction-synthesis.md` 都是你写的。因此本次适用 `AGENTS.md` 的
   design-conflict 强审查者披露路径，`reviewer_prior_involvement` 必须写 `design`。
   **关键**：按 `AGENTS.md`，你必须把**用户批准的方向综合与 PRD 当作最高权威**，
   而 `10-design.md` / `11-adr.md` / `12-development-breakdown.md` 是**被审证据，不是权威**。
   不要因为设计是你写的就默认它正确——如果实现暴露了设计缺陷，照实报。
2. **你写过上一轮 Review-2**（`50-review-2.md`，verdict `REWORK`，锚点
   `01d3a4712c89efab79772ce2e5ee2ba415e1e43c`）。那个 verdict 有效且已被执行，覆盖的是**旧范围**。
   本次**不是** second opinion，而是对**当前范围**的首次终审。
   **不得**把你上一轮的结论当作本轮已经成立的事实，必须重新读代码与固定 diff。
3. **你曾是本 stage 的 bookkeeper**，直到 2026-07-25 因额度耗尽交接。因此
   `status.json`、`70-handoff.md` 以及编号 66 之前的 packet 有一部分是**你自己写的簿记**。
   审阅这些证据时请意识到这一点并披露。
4. **现任 bookkeeper 是 Claude Opus 5，同一模型也写了 r2/r3/r4/r5 四轮后端 Review-1**
   （`58` / `64` / `66` / `68`）。这是一个双重身份。它在 `27-user-authorized-r4-repair.md` §6
   与 `status.json.bookkeeper.dual_hat_disclosure` 中做了披露，并声明只做机械簿记与路由。
   **请你独立判断这个双重身份是否损害了证据链**——例如：Review-1 的 ACCEPT 是否被簿记方
   不当影响、bookkeeper 的"独立复核"是否实际构成自证、packet 的 fix_start_prompt 是否被
   摘要替换。这是终审的正当职责，请不要回避。

## 固定审查锚点（只审此已提交范围；不要改用移动的 HEAD）

- base: 28c550d87c1ca90983d5bde9c7102d42cffecd4e
- head: b9e1978eaffd047b7871b8721f511307e75fde68
- fingerprint: b9e1978eaffd047b7871b8721f511307e75fde68:604caada1043e8334f33b1cc73239f1cf6bb19017db1dc68374679cf6ac99ddd

## 必须实际阅读

1. `AGENTS.md`；`workflows/templates/stage-delivery.yaml`；`schemas/review-verdict.schema.json`；
2. **最高权威**：`docs/product/PRD.md` 与用户批准的 `06-direction-synthesis.md`；
   用户后续冻结的运行时合同 `15-immediate-loop-and-open-log-amendment.md`、
   `21-task-local-runtime-and-manual-pause-amendment.md`、`24-user-authorized-final-guardian-fix.md`、
   `26-user-authorized-settlement-and-pause-fix.md`、`27-user-authorized-r4-repair.md`；
3. **被审证据（非权威）**：`00-task.md`、`10-design.md`、`11-adr.md`、
   `16-replacement-development-breakdown.md`、`17-opening-log-pagination-compatibility.md`；
4. 全部 Review-1 与修复报告：`30-review-1-backend.md`、`30-review-1-frontend.md`、
   `45-review-1-frontend-rfix.md`、`58-review-1-backend-r2.md`、`59-review-1-frontend-r2.md`、
   `64-review-1-backend-r3.md`、`66-review-1-backend-r4.md`、`68-review-1-backend-r5.md`、
   `40-*`、`41-*`、`42-final-guardian-scanner-fix.md`、`44-fix-review-1-backend-r3.md`、
   `46-fix-review-1-backend-r4.md`、`50-review-2.md`（你自己的上一轮）、`60-test-output.txt`；
5. 实际 `git diff --binary 28c550d87c1ca90983d5bde9c7102d42cffecd4e..b9e1978eaffd047b7871b8721f511307e75fde68`，
   以及 `backend/hedge_open_tasks/**`、`backend/services/**`、`backend/app/server.py`、
   `backend/config.py`、`frontend/index.html`、`frontend/self-check.js`、`backend/tests/**` 源码。

## 用户冻结的业务合同（高于旧草案与你自己的设计稿）

- 每张任务卡独立；同一张卡严格先让第 N 组走到终态/对账结束，才可开始第 N+1 组。一组内现货和合约腿仍并发。
- `target_n` 是计划尝试组数硬上限，不因失败或单腿结果补发超出授权数量。
- 不得到 `orderId` 的未知结果必须按 clientOrderId 查询，绝不盲目重发写请求；已受理订单继续查到终态。
- 429、余额/保证金/可用数量不足只暂停当前任务，等待人工恢复；不联动其它任务。其它明确配置错误只停止当前任务。
- 实时模式没有长期全局守护扫描器：启动时可做一次恢复交接；人工 Start/recover 只能启动指定卡；后续下单/查询由各卡自己的有界 worker 完成。
- 固定 base `quantity=q_common` 并发两腿；本 stage 不使用 `quoteOrderQty`；常规统一账户，PM-Pro 不在范围。
- 默认关闭。没有本次实盘、Start、凭据或真实 Binance 请求授权。

## 终审必须覆盖的范围

1. **交付是否满足用户批准的方向与 PRD**（不是满足你的设计稿）。包括即时开单闭环、
   开单日志/entries 分页、持仓面板、风险与实盘门控。
2. **安全门**：默认关闭；7 端点冻结 allowlist；签名前置门；凭据绝不出现在日志/响应/前端；
   real POST 在未授权时不可达；`frontend/` 无跨域、无外域 fetch、无 Binance 直连。
3. **交易正确性**：两腿并发与同卡串行；`target_n` 原子硬上限；ADR-2 绝不重发；
   clientOrderId-only 查询；对账绝不放弃；429 / 余额不足只暂停本卡；fatal 只停本卡；
   单腿敞口为 advisory 且如实记录。
4. **本轮新增的两处修复是否真实有效**（packet 67，用户授权的第 6 次变更）：
   `_pump_worker` 的 stop-event 初始化改动、`_recover_workers` 兜底加 `STATUS_DONE`。
   `68-review-1-backend-r5.md` 声称做了四组猴补丁反向验证并额外验了 `aggregate_positions`
   端到端；bookkeeper 也声称独立跑了四个用例。**请自己抽验至少一条**，不要仅凭报告采信。
5. **证据链与治理**：`rework_count` 6/6 是否被如实记录；用户的六次授权是否都有落盘证据；
   reviewer 的 `fix_start_prompt` 是否被 bookkeeper 摘要替换（`AGENTS.md` 禁止）；
   packet 的 RECEIPT 与 `status.json` 是否自洽；上文第 4 条披露的双重身份是否造成实质问题。
6. **剩余风险是否被如实记录而非掩盖**：`68-review-1-backend-r5.md` 列了 12 条 residual_risks
   与 4 条 P3（含一条新发现但声称生产不可达的 `store.pause_task` 无状态守卫）。
   核验"不可达"论证是否成立。
7. **测试**：核对 230 focused / 906 backend / 前端自检 / Harness 55 / `git diff --check`
   的原始证据；独立运行足以验证高风险行为的测试。

## 自测命令（供你独立复跑）

```bash
.venv/bin/python -m pytest backend/tests -q
node frontend/self-check.js
.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q
.venv/bin/python scripts/validate-stage.py 2026-07-hedge-open-real-api-v1 --phase pre-review
git diff --check
```

输出完整原始评审到：
`reports/agent-runs/2026-07-hedge-open-real-api-v1/69-review-2.md`

先写中文叙述、findings（P0/P1/P2/P3）与可核对证据，再写标准 Session footer。文件最后一个顶层 JSON 对象必须严格匹配 `schemas/review-verdict.schema.json`：`role=final_reviewer`、`model=GPT-5 Codex`、`reviewer_prior_involvement=design`、`diff_fingerprint` 必须逐字等于上面值，并在 `reviewer_prior_involvement_notes` 中写明上文四点披露。

**注意 `rework_count` 已达上限 6/6**：若 verdict=REWORK，你必须提供可直接派发的 `fix_start_prompt`，并在报告中明说任何进一步代码变更都需要用户**新的书面授权**，bookkeeper 不能自行派发。若 verdict=ACCEPT，请明确说明本次 ACCEPT **不**解除任何实盘门（live 启用、Start、第一笔真实订单仍是独立的人类授权），并说明 stage 是否可以进入用户验收。完成后停止等待 bookkeeper。

当前 Session ID: report provider-native ID, or unavailable:<reason>
Session ID 来源: runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/69-review-2.md
本地北京时间: obtain from local date command
下一步模型: bookkeeper
下一步任务: validate this final-gate verdict and route the stage to user acceptance or a newly authorized fix
```

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/69-review-2.dispatch.md
本地北京时间: 2026-07-26 CST
下一步模型: human operator
下一步任务: run the prompt body in a fresh read-only Codex session
