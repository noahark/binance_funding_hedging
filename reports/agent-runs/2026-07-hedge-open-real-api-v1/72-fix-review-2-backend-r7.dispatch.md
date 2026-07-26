<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status: completed
target_model: claude_glm/glm-5.2[1m]
adapter_cmd: claude-glm --model glm-5.2 --permission-mode acceptEdits -p "$(cat <prompt-file>)"
executor: human_operator
started_at: unavailable:no start timestamp was recorded by the operator or the report
completed_at: 2026-07-26T22:56:00+08:00
completed_at_source: filesystem mtime of 71-fix-review-2-backend-r7.md — NOT model-reported; its footer carries only a date
session_id: unavailable:the produced report's footer records that the runtime did not expose a provider-native Session ID
outputs: reports/agent-runs/2026-07-hedge-open-real-api-v1/71-fix-review-2-backend-r7.md
next_dispatch: none
authorization: user-authorized SEVENTH bounded backend change; 28-user-authorized-r7-repair.md (scope = Review-2 F1 + F2 + F4 + the finding-6 validator coverage ONLY)
routing_reason: Claude-GLM has owned the backend across all six prior rounds. Routing the fix to zhipu_glm also keeps Claude Opus 5 (anthropic) provider-isolated and therefore eligible for the next backend Review-1.
bookkeeper_note: the PROMPT BODY below is Review-2's verbatim fix_start_prompt from 69-review-2.md, with a clearly marked bookkeeper preamble that applies the user's scope decision (three of the six P1s are excluded by the user; the finding-6 validator item is added; the allowed-file list is adjusted accordingly). No reviewer evidence was summarized, reordered, or deleted — the excluded items remain readable in the body and in 69-review-2.md.
r10_checklist: task_prompt_path=72-fix-review-2-backend-r7.dispatch.md; self_tests_command per 28-user-authorized-r7-repair.md §5; next_dispatch_executor=bookkeeper; pass_branch=write 71-fix-review-2-backend-r7.md with real self-test output and stop for bookkeeper; blocker_branch=stop and escalate, packet 72 may not expand beyond the four authorized items; unavailable_branch failure_classes=[model_unavailable, adapter_missing, command_error, permission_error, timeout] escalating to this dispatch file.
receipt_backfilled_by: bookkeeper (Claude Opus 5) on 2026-07-27, closing the 74-review-2-r2.md P1 backlog. Evidence is taken ONLY from the produced report's own footer; every field without a recorded source is marked unavailable with its reason. No command, timestamp or Session ID was invented.
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable） ===== -->

```text
[BOOKKEEPER SCOPE PREAMBLE — 用户 2026-07-26 的第 7 次授权裁定，权威文件 28-user-authorized-r7-repair.md]

下面紧接着的是 Review-2（69-review-2.md）的**逐字原始 fix_start_prompt**，未做任何摘要或改写。
但用户已对其 6 条 P1 做了范围裁定，**本 packet 只执行下列 4 项**：

必做（对应下文原文的第 1、2、4 条 + 本前言新增的第 7 条）：
  1. 原文第 1 条 —— 非限频 single_leg 计入连续失败 + 计划组数用尽转 done。
  2. 原文第 2 条 —— classify_query_response 只认显式 404/-2013 为 absent；2xx 缺 orderId 保持
     UNKNOWN_QUERYING；查询阶段 429/-1003/418 保留 typed rate-limit signal 并暂停本卡、零重发。
     **这是本轮风险最高项：实盘限频必然触发，误判会把可能已成交的单当成未成交并继续开下一组。**
  4. 原文第 4 条 —— 消除"最后一腿 terminal 已提交、pair_outcome 仍 NULL"的崩溃缝隙；不得忙循环、
     不得新增周期性 guardian/scanner/timer、不得开新组或重复计数。
  7. **【本前言新增，原文没有】** finding 6 的 validator 覆盖：让 scripts/validate-stage.py 能自动检出
     (a) 当前阶段引用的 dispatch 回执仍是 pending 却已有产出；(b) 根 status 与所处工作流阶段不一致
     （例如派发 Review-2 时根状态仍为 review_1）。为这两项各加确定性测试到
     scripts/tests/test_validate_stage_dispatch_protocol.py。
     背景：该 finding 的簿记部分已由 bookkeeper 于 2026-07-26 提交 faa33b9 修复完毕（回执封存 +
     根状态推进），**你不需要也不允许再改 status.json / 70-handoff.md / 任何 dispatch 回执**；
     你只做 validator 与其测试。

用户明确**不做**（下文原文中出现也一律跳过，不得实现）：
  - 原文第 3 条（人工 delete/pause 被迟到 worker 结果覆盖的状态守卫）——用户裁定暂不修。
    连带：**不引入 requested_action/命令队列，不改 API 语义，frontend/** 零改动**。
  - 原文第 5 条（账户健康 accountStatus/uniMMR + 现货 MIN_NOTIONAL）——用户裁定不做。
    **七端点 allowlist 保持冻结，hedge_open_live_client.py 与 hedge_preflight_provider.py 禁止修改。**
  - 原文第 6 条中与上述被排除项相关的回归，相应不做；其余回归照做。

允许修改的文件以 28-user-authorized-r7-repair.md §4 为准（**覆盖下文原文的允许清单**）：
  backend/hedge_open_tasks/{domain.py,service.py,store.py}
  backend/services/live_hedge_executor.py
  scripts/validate-stage.py                                   ← 仅上述第 7 条
  backend/tests/{test_hedge_task_local.py,test_hedge_review2_regressions.py,test_hedge_service.py,
                 test_hedge_store.py,test_hedge_domain.py,test_live_hedge_executor.py}
  scripts/tests/test_validate_stage_dispatch_protocol.py      ← 仅上述第 7 条
  reports/agent-runs/2026-07-hedge-open-real-api-v1/60-test-output.txt（仅追加真实输出）
  reports/agent-runs/2026-07-hedge-open-real-api-v1/71-fix-review-2-backend-r7.md（新建实现报告）

禁止修改：frontend/**、docs/**、PRD、10-design/11-adr、backend/services/hedge_open_live_client.py、
backend/services/hedge_preflight_provider.py、backend/hedge_open_tasks/scheduler.py、
backend/app/server.py、reports/api-samples/**、status.json、70-handoff.md、
任何契约文档（15/16/17/19/21/23/24/25/26/27/28）与评审报告（30/42/45/50/58/59/64/66/68/69）、
环境/凭据/网络配置。

用户的产品方向（逐字）：「我们的目标是尽快上线验证，在实盘中再发现问题做优化。不要在设计阶段太关注
低概率场景发生的事情」。因此**不要**顺手加固被排除项，不要扩大范围，不要重构。

前置条件已满足：用户已书面授权第 7 次有界变更（max_rework 6→7），并已就账户健康端点作出「不做」的
决定 —— 下文原文开头那句"在用户书面授权前不得执行"的前置门**已解除**。

[以下为 Review-2 原始 fix_start_prompt 逐字原文]

[HARNESS-EXECUTOR-CONTRACT v1]
你是 2026-07-hedge-open-real-api-v1 的后端返工实现者候选人。禁止调用、启动或转派任何其他正式模型会话或 adapter。当前 rework_count=6/max_rework=6；在用户以书面形式同时授权“第 7 次有界代码变更”并决定账户健康端点/政策之前，本 prompt 不得执行，必须停止并报告 human authorization missing。bookkeeper 也必须先依据真实 operator 记录修复或重跑 66/67/68 的正式回执，不得编造命令、时间或 Session ID。

授权满足后，先逐字读取：reports/agent-runs/2026-07-hedge-open-real-api-v1/69-review-2.md（本评审全文和末尾 JSON）、15-immediate-loop-and-open-log-amendment.md、16-replacement-development-breakdown.md（I-2/A-3/A-5）、21-task-local-runtime-and-manual-pause-amendment.md、24-user-authorized-final-guardian-fix.md、26-user-authorized-settlement-and-pause-fix.md、27-user-authorized-r4-repair.md、68-review-1-backend-r5.md、固定源码和测试。起点指纹是 b9e1978eaffd047b7871b8721f511307e75fde68:604caada1043e8334f33b1cc73239f1cf6bb19017db1dc68374679cf6ac99ddd；bookkeeper 会在修复后创建新的 committed 指纹。绝不读取凭据、绝不连接 Binance、绝不发送真实 POST、绝不启用 live/Start、绝不 commit、绝不修改 status.json/70-handoff.md/评审报告/用户授权文件。

必须修复：
1. 非限频、非致命 single_leg 按用户批准的连续提交失败规则增加 fail/consecutive 计数，达到任务快照阈值即暂停；429 attempt 继续免计数。最后一笔计划 attempt 结算后，若没有 paused/stopped/deleted 等更高优先级状态，将 task 与 entries.next_action 一致标为 done/completed。
2. classify_query_response：仅 HTTP 404 或 Binance -2013 确认 absent；2xx 缺少有效 orderId 保持 UNKNOWN_QUERYING。查询阶段 429/-1003/418 必须保留 typed rate-limit signal，由该任务 worker 持久化 paused+rate_limited、保留未决腿、退出等待人工恢复；绝不重发 POST。
3. 给 worker 驱动的 pause/fatal-stop 写入增加原子状态守卫：迟到的 429、insufficient/fatal 或其它结果不得覆盖 deleted/done/stopped 等高优先级状态，也不得清空人工原因；可记录 attempt/event，但受保护 task 状态保持不变。新增真实线程竞态回归，至少覆盖人工 delete 与迟到 rate-limit/fatal。
4. 消除“最后一腿 terminal 已提交、pair_outcome 仍 NULL”的崩溃缝隙：采用可重入原子 store 操作，或一次性恢复扫描该任务的 terminal-but-unsettled attempt 并幂等 finalize。不得新增周期性全局 guardian/scanner/timer；不得忙循环；不得开新组或重复计数。
5. Spot filter 同时解析 NOTIONAL 与 MIN_NOTIONAL，二者均缺失/畸形时 preflight_incomplete，零 attempt/POST/count。账户健康按用户书面选择执行：若选择新增端点，只能把精确只读 GET /papi/v1/account 加入 allowlist，要求 accountStatus literal NORMAL，uniMMR 存在且可解析，并只应用用户明确批准的政策；不得自行发明风险阈值。若用户选择合同豁免，implementer 不得改合同，由 bookkeeper 先落盘批准的修正案后再重出 packet。
6. 增加确定性反向回归：连续 single_leg 触发阈值；计划数耗尽转 completed；畸形 2xx 不闭合；query 429 暂停且零重发；delete 与迟到 rate-limit/fatal 不复活任务；terminal legs + NULL outcome 的重启恢复覆盖 running/paused/stopped/deleted/done 与 429 免计数；Spot MIN_NOTIONAL；账户健康缺失/异常 fail closed。每条先证明缺陷代码会失败，再验证修复转绿。

允许修改仅限 backend/hedge_open_tasks/{domain.py,service.py,store.py}、backend/services/{live_hedge_executor.py,hedge_preflight_provider.py,hedge_open_live_client.py}、直接相关 backend/tests/test_hedge_*.py 与 test_live_hedge_executor.py，以及新实现报告 reports/agent-runs/2026-07-hedge-open-real-api-v1/71-fix-review-2-backend-r7.md 和 60-test-output.txt（只追加真实输出）。frontend/**、docs/**、PRD、设计/ADR、用户修正案、reports/api-samples/**、scheduler.py、环境/凭据/网络配置禁止修改；若账户健康选择需要合同修订，由 bookkeeper 另行处理，implementer 停止。

精确自测：
.venv/bin/python -m pytest backend/tests/test_hedge_task_local.py backend/tests/test_hedge_review2_regressions.py backend/tests/test_hedge_service.py backend/tests/test_hedge_store.py backend/tests/test_hedge_domain.py backend/tests/test_hedge_api.py backend/tests/test_hedge_open_live_client.py backend/tests/test_live_hedge_executor.py backend/tests/test_hedge_purity.py -q
.venv/bin/python -m pytest backend/tests -q
node frontend/self-check.js
.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q
git diff --check

把 changed files、每条修复前反向失败/修复后证据、零网络/零凭据、H-1 无全局 guardian 回归、剩余风险写入 71-fix-review-2-backend-r7.md，原始输出追加到 60-test-output.txt，然后停止等待 bookkeeper；不 commit、不派发评审、不自行宣称验收。
```

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/72-fix-review-2-backend-r7.dispatch.md
本地北京时间: 2026-07-26 CST
下一步模型: human operator
下一步任务: deliver this prompt body to a fresh write-capable Claude-GLM session; GLM writes 71-fix-review-2-backend-r7.md and stops for the bookkeeper
