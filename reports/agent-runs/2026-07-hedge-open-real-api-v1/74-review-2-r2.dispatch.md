<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status: completed
target_model: codex/GPT-5 Codex
adapter_cmd:
executor: human_operator
started_at: unavailable:no start timestamp was recorded by the operator or the report
completed_at: 2026-07-27T00:09:51+08:00
completed_at_source: 74-review-2-r2.md:footer
session_id: unavailable:the produced report's footer records that the runtime did not expose a provider-native Session ID
outputs: reports/agent-runs/2026-07-hedge-open-real-api-v1/74-review-2-r2.md
next_dispatch: none
routing_reason: unchanged from packet 69 — Codex is the ONLY provider eligible as final reviewer. The final reviewer may not share provider identity with ANY delivery-code author, with no override: anthropic is hard-barred (Claude Sonnet 5 authored the accepted frontend rework), zhipu_glm is hard-barred (backend author), kimi and grok are quota-unavailable. Codex never wrote delivery or fix code (model_routing.excluded_from_core_implementation_and_fix = ["codex"]). Full analysis: 46-review-2-routing-disclosure.md.
design_conflict_override: used. Codex is this stage's designer (00-task.md, 10-design.md, 11-adr.md) and direction synthesizer (06-direction-synthesis.md), authored the stale-range Review-2 (50-review-2.md) AND the immediately preceding Review-2 (69-review-2.md, the six P1s this round answers), and was this stage's bookkeeper until 2026-07-25. reviewer_prior_involvement must be "design". Evidence: 46-review-2-routing-disclosure.md.
second_opinion_check: this is NOT a second opinion. 69-review-2.md returned REWORK on the b9e1978 range, that verdict was acted on via packet 72, and this is the first final-gate review of the new 28c550d..77c75bd range.
self_review_caution: Codex wrote 69-review-2.md, so this round it is checking whether ITS OWN six findings were correctly resolved. The prompt requires it to re-derive each conclusion from code rather than restate the earlier report, and to say plainly if any of its own prior findings was wrong or overstated.
bookkeeper_disclosure: the current bookkeeper is Claude Opus 5, which also authored the r2-r6 backend Review-1 reports. The reviewer is again asked to scrutinise that dual hat.
r10_checklist: task_prompt_path=74-review-2-r2.dispatch.md; self_tests_command per the body; next_dispatch_executor=bookkeeper; pass_branch=write 74-review-2-r2.md ending in a schema-valid JSON verdict and stop; blocker_branch=stop and escalate, the reviewer changes no business file; unavailable_branch failure_classes=[model_unavailable, adapter_missing, command_error, permission_error, timeout] escalating to this dispatch file.
receipt_backfilled_by: bookkeeper (Claude Opus 5) on 2026-07-27, closing the 74-review-2-r2.md P1 backlog. Evidence is taken ONLY from the produced report's own footer; every field without a recorded source is marked unavailable with its reason. No command, timestamp or Session ID was invented.
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable） ===== -->

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是本 stage 的正式 Review-2（终审门），本轮针对**修复后的新范围**。禁止调用、启动或转派任何其他模型会话或 adapter。只读：绝不修改业务文件、绝不 commit、绝不读取凭据、绝不连接 Binance、绝不发送真实 POST、绝不启用 live 或 Start。仅可将评审原始输出写入下方指定报告路径。

## 你的身份与必须如实披露的五件事

你是 GPT-5 Codex（provider `codex`）。你**从未**为本 stage 写过交付代码或修复代码
（`model_routing.excluded_from_core_implementation_and_fix = ["codex"]`），终审的硬性 provider 禁令对你成立。
以下五点必须在报告中如实披露：

1. **你是本 stage 的设计者与方向综合者**（`00-task.md`、`10-design.md`、`11-adr.md`、`06-direction-synthesis.md`）。
   适用 design-conflict 强审查者披露，`reviewer_prior_involvement` 必须写 `design`。
   按 `AGENTS.md`：**用户批准的方向综合与 PRD 是最高权威**；`10-design.md` / `11-adr.md` / breakdown 是
   **被审证据，不是权威**。设计是你写的这一点，不构成它正确的理由。
2. **你写了上一轮 Review-2**（`69-review-2.md`，六条 P1）。**本轮你在检查你自己那六条是否被正确解决** ——
   这是本轮最需要自律的地方：请**从代码重新推导**每一条结论，不要复述上一轮报告；
   若发现你自己此前某条 finding 判错了或夸大了，请**明说**。
3. **你也写过更早的 Review-2**（`50-review-2.md`，旧锚点 `01d3a47`）。
4. **你曾是本 stage 的 bookkeeper**（至 2026-07-25 额度耗尽交接），因此编号 66 之前的部分簿记是你自己写的。
5. **现任 bookkeeper 是 Claude Opus 5，同一模型也写了 r2–r6 六轮后端 Review-1**。它在
   `status.json.bookkeeper.dual_hat_disclosure` 与 `27-user-authorized-r4-repair.md` §6 做了披露。
   **请你独立判断这个双重身份是否损害了证据链**：Review-1 的 ACCEPT 是否被簿记方不当影响、
   bookkeeper 的"独立复核"是否实际构成自证、reviewer 的 `fix_start_prompt` 是否被摘要替换、
   `status.json` 的多轮降级/重锚是否掩盖了任何证据。这是终审的正当职责。

## 固定审查锚点（只审此已提交范围；不要改用移动的 HEAD）

- base: 28c550d87c1ca90983d5bde9c7102d42cffecd4e
- head: 77c75bd855c3d1a7a4c91700f9db953919df087f
- fingerprint: 77c75bd855c3d1a7a4c91700f9db953919df087f:aa0406dae9cb90004d5dd15c2a936ad9a021a0c01a50f985d4efab5900e652dd

`77c75bd..HEAD` 只含簿记文件（`70-handoff.md`、`73`/`74` dispatch、`status.json`），零业务文件 ——
r6 已核过这一点，请自行复核后再决定是否在工作树上跑测试。

## 必须实际阅读

1. `AGENTS.md`；`workflows/templates/stage-delivery.yaml`；`schemas/review-verdict.schema.json`；
2. **最高权威**：`docs/product/PRD.md`、用户批准的 `06-direction-synthesis.md`，以及用户冻结的运行时合同
   `15-immediate-loop-and-open-log-amendment.md`、`21-task-local-runtime-and-manual-pause-amendment.md`、
   `24-user-authorized-final-guardian-fix.md`、`26-user-authorized-settlement-and-pause-fix.md`、
   `27-user-authorized-r4-repair.md`、**`28-user-authorized-r7-repair.md`（本轮范围与用户排除项的权威）**；
3. **被审证据（非权威）**：`00-task.md`、`10-design.md`、`11-adr.md`、`16-replacement-development-breakdown.md`；
4. 评审与修复链：**`69-review-2.md`（你自己的上一轮）**、`73-review-1-backend-r6.md`（本轮 Review-1 ACCEPT）、
   `71-fix-review-2-backend-r7.md`（本轮实现报告）、`68-review-1-backend-r5.md`、`66-review-1-backend-r4.md`、
   `59-review-1-frontend-r2.md`（前端 ACCEPT）、`60-test-output.txt`；
5. 实际 `git diff --binary 28c550d87c1ca90983d5bde9c7102d42cffecd4e..77c75bd855c3d1a7a4c91700f9db953919df087f`，
   以及 `backend/hedge_open_tasks/**`、`backend/services/**`、`backend/app/server.py`、`backend/config.py`、
   `frontend/index.html`、`frontend/self-check.js`、`backend/tests/**`、`scripts/validate-stage.py` 源码。

## 用户冻结的业务合同（高于旧草案与你自己的设计稿）

- 每张任务卡独立；同一张卡严格先让第 N 组走到终态/对账结束，才可开始第 N+1 组。一组内现货和合约腿仍并发。
- `target_n` 是计划尝试组数硬上限，不因失败或单腿结果补发超出授权数量。
- 不得到 `orderId` 的未知结果必须按 clientOrderId 查询，绝不盲目重发写请求；已受理订单继续查到终态。
- 429、余额/保证金/可用数量不足只暂停当前任务，等待人工恢复；不联动其它任务。其它明确配置错误只停止当前任务。
- 实时模式没有长期全局守护扫描器：启动时可做一次恢复交接；人工 Start/recover 只能启动指定卡。
- 固定 base `quantity=q_common` 并发两腿；本 stage 不用 `quoteOrderQty`；常规统一账户，PM-Pro 不在范围。
- 默认关闭。没有本次实盘、Start、凭据或真实 Binance 请求授权。

## 用户对本轮的范围裁定（`28-user-authorized-r7-repair.md`，必须遵守）

用户产品方向原话：「我们的目标是尽快上线验证，在实盘中再发现问题做优化。不要在设计阶段太关注低概率场景发生的事情」。

packet 72 只授权修**你上一轮六条 P1 中的三条 + finding-6 的 validator 剩余项**（F1 / F2 / F4 / F6）。
用户**明确排除**以下各项，**不得**因其未修而给出 P0/P1 或据此 REWORK；若认为风险被低估，
写入 `residual_risks` 或 P3 并说明理由：

- **你上一轮的 F3**（人工 delete/pause 被迟到 worker 结果覆盖）—— 用户裁定暂不修。
  连带：不引入命令队列、不改 API 语义、`frontend/**` 零改动。
- **你上一轮的 F5**（账户健康 `accountStatus`/`uniMMR` + 现货 `MIN_NOTIONAL`）—— 用户裁定不做；
  七端点 allowlist 保持冻结。用户以「输入端自行保证数量足够」作为操作约定
  （bookkeeper 已提示：输入的是数量、交易所卡的是名义金额＝数量×价格，需留余量；用户接受）。
- 排队期间取消删除、`aggregate_positions` 过滤 `deleted`、既有 P3、跨进程预留守卫、
  `X-MBX-ORDER-COUNT-*` 节流、前端展示 `worker_active` —— 全部后置 follow-up。

**`rework_count` 已 7/7 用尽**：若 verdict=REWORK，任何代码变更都需用户**新的书面授权**，
bookkeeper 不能自行派发；请在报告中明说。

## 终审必须覆盖的范围

1. **交付是否满足用户批准的方向与 PRD**（不是满足你的设计稿）：即时开单闭环、开单日志/entries 分页、
   持仓面板、风险与实盘门控。
2. **你上一轮六条 P1 的处置是否正确**：F1/F2/F4/F6 是否**真的**修好（请自己从代码与探针验证，
   不要采信 `71` 或 `73` 的声称）；F3/F5 被用户排除是否被**如实记录**而非悄悄掩盖。
3. **安全门**：默认关闭；七端点冻结 allowlist；签名前置门；凭据绝不出现在日志/响应/前端；
   real POST 在未授权时不可达；`frontend/` 无跨域、无外域 fetch、无 Binance 直连。
4. **交易正确性**：两腿并发与同卡串行；`target_n` 原子硬上限；ADR-2 绝不重发；clientOrderId-only 查询；
   对账绝不放弃；429 / 余额不足只暂停本卡；fatal 只停本卡；单腿敞口如实记录。
5. **本轮引入的语义变更**：`consecutive_submission_failures` 现在对 `single_leg` 也增长。
   r6 判定其与 `16` §I-2 已批准合同一致、前端零改动前提成立、仅文案可能误导（记 P3）。请独立复核该判断。
6. **证据链与治理**：七次用户授权是否都有落盘证据；`rework_count` 7/7 是否如实；
   reviewer 的 `fix_start_prompt` 是否被 bookkeeper 摘要替换（`AGENTS.md` 禁止）；
   packet 66/67/68/59/69/73 的回执封存是否只用真实来源（bookkeeper 声称对无记录字段一律
   `unavailable`+原因、从未发明时间或 Session ID —— 请抽验）；
   多轮 `status.json` 降级/重锚是否保全了旧轮证据；上文第 5 点的双重身份是否造成实质问题。
7. **r6 遗留的两条 P2 是否应升级**：(a) 计划组用尽的卡在人工 Start 后停在 `running`
   （`post_start` 无用尽检查；r6 实测 `dispatch_calls` 不增、`target_n` 硬上限完好，故定 P2）；
   (b) 新 validator 的根状态检查单向，在正常返工环上会误报。请独立判断这两条的定级。
8. **测试**：核对 918 backend / 227 focused / 67 validator / 前端自检 / `git diff --check` 的原始证据，
   并独立运行足以验证高风险行为的测试。

## 自测命令（供你独立复跑）

```bash
.venv/bin/python -m pytest backend/tests -q
node frontend/self-check.js
.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q
.venv/bin/python scripts/validate-stage.py 2026-07-hedge-open-real-api-v1 --phase pre-review
git diff --check
```

输出完整原始评审到：
`reports/agent-runs/2026-07-hedge-open-real-api-v1/74-review-2-r2.md`

先写中文叙述、findings（P0/P1/P2/P3）与可核对证据，再写标准 Session footer。文件最后一个顶层 JSON 对象必须严格匹配 `schemas/review-verdict.schema.json`：`role=final_reviewer`、`model=GPT-5 Codex`、`reviewer_prior_involvement=design`、`diff_fingerprint` 必须逐字等于上面值，并在 `reviewer_prior_involvement_notes` 中写明上文五点披露。

若 verdict=ACCEPT，请明确说明：本次 ACCEPT **不**解除任何实盘门（live 启用、Start、第一笔真实订单仍是三道独立的人类授权），并说明 stage 是否可以进入用户验收。完成后停止等待 bookkeeper。

当前 Session ID: report provider-native ID, or unavailable:<reason>
Session ID 来源: runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/74-review-2-r2.md
本地北京时间: obtain from local date command
下一步模型: bookkeeper
下一步任务: validate this final-gate verdict and route the stage to user acceptance or a newly authorized fix
```

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/74-review-2-r2.dispatch.md
本地北京时间: 2026-07-26 CST
下一步模型: human operator
下一步任务: run the prompt body in a fresh read-only Codex session
