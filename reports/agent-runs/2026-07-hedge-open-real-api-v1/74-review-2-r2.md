# Review-2 r2（最终审查）

结论：`REWORK`（需要返工）。业务代码的本轮三项修复已经成立，但第 7 次修复所承诺的 F6（派发回执与阶段一致性校验）没有覆盖其自身的当前实现派发。因此该范围不能进入 `stage_accepted_waiting_user`（审查通过、等待用户验收），更不解除 live（真实执行）、Start（启动闸门）或第一笔真实订单的任何独立人工授权。

`rework_count=7/7` 已用尽。下面 P1（最高优先级问题）需要新的书面用户授权后才能修改代码；记账者可先依据真实已有证据补全回执，但不得凭空补造时间、命令或 Session ID（会话编号）。

## 审查身份、固定范围与披露

- 审查者：GPT-5 Codex，provider（模型供应商）为 `codex`；未为本 stage 编写交付或修复代码，满足最终审查与所有代码作者的 provider 隔离。
- 本人曾编写 `00-task.md`、`10-design.md`、`11-adr.md`，并综合 `06-direction-synthesis.md`；曾写旧锚点的 `50-review-2.md` 与紧邻上一轮的 `69-review-2.md`，并曾在 2026-07-25 前担任 bookkeeper（阶段记账者）。因此 `reviewer_prior_involvement=design`。本报告以用户批准的 PRD、方向综合、修正案与用户授权为高于本人设计稿的权威。
- 当前 bookkeeper 是 Claude Opus 5，同时写过后端 Review-1 r2–r6；其双重身份已在 `status.json` 与 `27-user-authorized-r4-repair.md` §6 披露。本次没有把其总结或任何上一轮结论当作事实，而是重新读取固定差异、源码、测试和回执。
- 固定范围：`28c550d87c1ca90983d5bde9c7102d42cffecd4e..77c75bd855c3d1a7a4c91700f9db953919df087f`。独立重算指纹为
  `77c75bd855c3d1a7a4c91700f9db953919df087f:aa0406dae9cb90004d5dd15c2a936ad9a021a0c01a50f985d4efab5900e652dd`，与派发包逐字一致。
- 当前 `HEAD=b1fc7b1` 比固定 head 晚出的仅是 `70-handoff.md`、`73/74` 派发包和 `status.json` 等簿记文件；业务判断没有使用移动的 `HEAD` 替代固定范围。审查输出落盘前工作树干净。

## 独立验证

我已读取 `AGENTS.md`、`workflows/templates/stage-delivery.yaml`、评审 verdict schema（裁决格式）、PRD、用户批准的 `06`、`15`、`21`、`24`、`26`、`27`、`28`，以及设计/ADR、前后端源码、固定 binary diff、`69`、`71`、`73`、`59`、`60`、各回执和 `status.json`。未读取凭据、未连接 Binance、未发送真实 POST、未启用 live 或 Start、未修改业务文件或提交。

独立执行结果如下：

- `.venv/bin/python -m pytest backend/tests -q`：`918 passed in 45.18s`。
- `node frontend/self-check.js`：全部自检通过。
- `.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q`：`67 passed in 1.07s`。
- `.venv/bin/python scripts/validate-stage.py 2026-07-hedge-open-real-api-v1 --phase pre-review`：通过，且指纹一致。
- `git diff --check`：通过。
- 另独立运行 F1/F2/F4 的 13 条定点回归：`13 passed in 0.10s`，包括单腿连续失败、畸形 2xx 查询、查询阶段 429、零重发、崩溃缝隙恢复及幂等性。

## 上一轮六项 P1 的重新推导

F1 已修复。`domain.resolve_status_after_attempt` 与 `store._apply_task_counters` 现在让非限频 `single_leg`（只受理一条腿）增加失败/连续失败计数；低于阈值仍记录敞口并可继续，高于阈值暂停。最后一个已结算的计划组在没有更高优先级终态时转为 `done`，不会突破 `target_n`（计划尝试组数）硬上限。

F2 已修复。`classify_query_response` 只把明确的 404 或 `-2013` 判为订单不存在；无有效 `orderId` 的 2xx 保持 `UNKNOWN_QUERYING`（未知、继续查询）。查询 429/-1003/418 作为带 `rate_limited` 的信号回传，`_reconcile_own_legs` 不结算、不重发，并由本卡 worker 持久化暂停后退出，等待人工恢复。

F4 已修复。`list_unsettled_terminal_attempts_for_task` 和 `_recover_crash_gaps` 会在同一卡内幂等结算“两腿已终态而 `pair_outcome` 仍为空”的崩溃缝隙；不会新发订单、不会重复计数，也没有引入常驻全局扫描器。

F3（迟到 worker 覆盖人工 pause/delete）和 F5（账户健康与 Spot `MIN_NOTIONAL`）仍未修复，但 `28-user-authorized-r7-repair.md` §3 明确将它们排除。本报告将二者保留为已披露风险，不以其作为本轮返工依据。

安全门仍保持：默认 `APP_HEDGE_EXECUTOR=disabled`、真实 POST 的路径仍受 live + durable Start + 新鲜预检共同约束；七端点 allowlist 未变化；前端自检确认无 Binance/外域 fetch、浏览器签名或开单定时器。

## Findings

### P1 — F6 校验器遗漏当前实现派发，且 packet 72 的正式回执仍未封存

`28-user-authorized-r7-repair.md` §2.4 授权的 F6 要求校验“当前阶段引用的 dispatch（派发）回执”不能在产物已存在时仍为 `pending`（待执行）。当前实现只在 `scripts/validate-stage.py:1008-1034` 收集 `review_1` / `review_2` 的派发引用；它不收集 `status.json:r7_repair_authorization.active_dispatch`。

实际当前引用 `status.json:984-989` 指向 `72-fix-review-2-backend-r7.dispatch.md`，该回执第 2 行仍是 `status: pending`，而第 9 行声明的 `71-fix-review-2-backend-r7.md` 已存在。实现报告本身也没有仓库规则要求的 Session footer（会话页脚），所以 `status.json.session_receipts` 无法从其报告页脚取得执行时间或会话来源。

我以当前 `status.json` 直接调用新增函数进行反向核验，得到：packet 72 为 `pending`、其 output 存在、`_collect_review_dispatch_refs` 仅返回 73、59、74 三个审查包，而 `validate_dispatch_receipt_phase(...) == []`。因此全绿的 67 条 Harness 测试与当前 `pre-review` 通过并不能证明 F6 完成：它们恰好遗漏了第 7 次交付所用的当前实现包。

影响：本轮代码作者/修复作者的执行证据仍未完成封存，且声称修复的流程门禁不能检测相同类型的当前实现漂移。这是 F6 范围内的硬证据链缺口，不是可由前端或业务测试抵消的问题。

建议：先由 bookkeeper 仅用已有原始证据把 packet 72 回执和对应 session receipt 如实封存；随后取得新的书面用户授权，进行第 8 次仅限 Harness 的有界修复，让校验器覆盖当前引用的实现/修复派发并新增“pending + 已存在 output 必失败”的回归。不可修改交易业务代码、前端、live 配置或用户冻结的 F3/F5 排除项。

## 非阻塞与遗留风险

- r6 的“计划已用尽却人工 Start 后卡片留在 `running`”仍是 P2：`target_n` 原子上限仍阻止新单，本轮实测与代码都没有下单扩大风险；但状态/日志会误导。它未升级为 P1。
- validator 的根状态比较仍以“出现 review dispatch”推导阶段，对正常 `REWORK -> fixing`（需要返工）循环并不稳健；当前通过把已完成的上一轮完整保留在 `previous_review_2_r1` 后不再触发。这是 fail-closed（会阻断而非静默放行）的 P2，不升级为本轮 P1。
- `store._apply_task_counters` 的 docstring 仍称 `single_leg` “counts unchanged”，与当前正确代码相反；是 P3 文档漂移。
- 查询阶段 429 退出没有写 `worker_exit_reason`，但 `pause_reason=rate_limited` 已持久化；是 P3 可观测性问题。
- F3/F5、跨进程预留守卫、主动 `X-MBX-ORDER-COUNT-*` 节流和前端文案仍是用户已知后置项；本审查不把它们伪装为已修复。

## 证据链与最终裁定

我抽验了 59、66、67、68、69、73 的回执：它们均已标为 `completed`，时间与无法获得 Session ID 的原因均指向原始报告或明确来源；未见伪造字段。66 的 `fix_start_prompt` 与 67 的正文保持原始审查要求，仅有已披露并有用户授权的定点路由标注。旧 Review-2 也被保留在 `previous_review_2_r1`，没有被覆写。

因此，Claude Opus 5 的 bookkeeper/Review-1 双重身份本身没有显示出篡改评审证据或代码自审的实质迹象；但 packet 72 的未封存状态意味着这条正当性链在当前一轮仍不能闭合。P1 未解决前，本 stage 不能进入用户验收。

当前 Session ID: unavailable (当前 Codex runtime 未暴露 provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/74-review-2-r2.md
本地北京时间: 2026-07-27 00:09:51 CST
下一步模型: bookkeeper / human operator
下一步任务: 先封存 packet 72 的真实执行回执；任何代码修复前取得用户对第 8 次 Harness-only 有界变更的书面授权

{
  "schema_version": 1,
  "stage_id": "2026-07-hedge-open-real-api-v1",
  "role": "final_reviewer",
  "model": "GPT-5 Codex",
  "verdict": "REWORK",
  "diff_fingerprint": "77c75bd855c3d1a7a4c91700f9db953919df087f:aa0406dae9cb90004d5dd15c2a936ad9a021a0c01a50f985d4efab5900e652dd",
  "reviewer_prior_involvement": "design",
  "reviewer_prior_involvement_notes": "Codex authored this stage's task/design/ADR and direction synthesis, the stale-range Review-2 at 50-review-2.md, the immediately previous Review-2 at 69-review-2.md, and was bookkeeper until 2026-07-25; it authored no delivery or fix code. This review re-derived F1/F2/F4/F6 from the fixed 28c550d..77c75bd range, sources, focused probes and full tests. Claude Opus 5 is the current bookkeeper and authored backend Review-1 r2-r6; its disclosed dual hat was independently audited against the raw reports and receipts.",
  "reviewed_artifacts": [
    "AGENTS.md",
    "workflows/templates/stage-delivery.yaml",
    "schemas/review-verdict.schema.json",
    "docs/product/PRD.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/06-direction-synthesis.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/15-immediate-loop-and-open-log-amendment.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/21-task-local-runtime-and-manual-pause-amendment.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/24-user-authorized-final-guardian-fix.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/26-user-authorized-settlement-and-pause-fix.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/27-user-authorized-r4-repair.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/28-user-authorized-r7-repair.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/69-review-2.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/71-fix-review-2-backend-r7.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/73-review-1-backend-r6.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/59-review-1-frontend-r2.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/60-test-output.txt",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/72-fix-review-2-backend-r7.dispatch.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/status.json",
    "backend/hedge_open_tasks/domain.py",
    "backend/hedge_open_tasks/store.py",
    "backend/hedge_open_tasks/service.py",
    "backend/services/live_hedge_executor.py",
    "backend/services/hedge_open_live_client.py",
    "backend/services/hedge_preflight_provider.py",
    "backend/app/server.py",
    "backend/config.py",
    "frontend/index.html",
    "frontend/self-check.js",
    "backend/tests",
    "scripts/validate-stage.py",
    "scripts/tests/test_validate_stage_dispatch_protocol.py",
    "git diff --binary 28c550d87c1ca90983d5bde9c7102d42cffecd4e..77c75bd855c3d1a7a4c91700f9db953919df087f"
  ],
  "findings": [
    {
      "severity": "P1",
      "title": "F6 校验器遗漏当前第 7 次实现派发，且 packet 72 回执仍为 pending",
      "file": "scripts/validate-stage.py",
      "line": 1008,
      "evidence": "_collect_review_dispatch_refs only collects review_1/review_2 records. status.json:r7_repair_authorization.active_dispatch points to packet 72; its receipt says status: pending while its declared 71-fix-review-2-backend-r7.md output exists. Directly calling validate_dispatch_receipt_phase on the current stage returns [], so the added F6 check does not detect this actual pending-with-output implementation dispatch.",
      "impact": "The seventh code-change execution evidence is not sealed and the newly promised validator cannot detect the same current-stage drift. The final gate therefore lacks a complete auditable implementation chain despite passing business tests.",
      "recommendation": "First seal packet 72 and its status session receipt only from real evidence. After new written user authorization for an eighth bounded Harness-only change, extend validation to the active implementation/fix dispatch reference and add a regression where pending plus an existing output fails."
    }
  ],
  "required_fixes": [
    "Bookkeeper must seal 72-fix-review-2-backend-r7.dispatch.md and status.json.session_receipts from actual available evidence only; unavailable fields must retain their factual reason.",
    "Obtain new written user authorization before any code change because rework_count is 7/7.",
    "With that authorization, implement and test a Harness-only validator repair so the current active implementation/fix dispatch is checked for pending-with-produced-output, without changing business code, frontend, live settings, F3/F5 scope, or user contracts."
  ],
  "residual_risks": [
    "F3 manual pause/delete overwrite and F5 account health plus Spot MIN_NOTIONAL remain deferred by explicit user decision in 28-user-authorized-r7-repair.md and are not this REWORK basis.",
    "Manual Start after target exhaustion may leave a task shown as running but cannot create another attempt; P2 state/UI inconsistency.",
    "The validator's root-status phase comparison is not stable across a normal Review-2 REWORK to fixing loop; P2 fail-closed Harness issue.",
    "single_leg docstring drift and missing rate-limit worker_exit_reason are P3 issues."
  ],
  "fix_start_prompt": "[HARNESS-EXECUTOR-CONTRACT v1]\nThis repair may be dispatched ONLY after the user gives a new written eighth-change authorization; the stage is already at rework_count=7/7. You are the authorized Harness-only fix implementer. Do not invoke another model or adapter. Do not modify business source, frontend, live configuration, credentials, Binance/network code, product contracts, F3/F5 scope, or stage status/handoff.\n\nRead these raw artifacts before editing: reports/agent-runs/2026-07-hedge-open-real-api-v1/74-review-2-r2.md; 28-user-authorized-r7-repair.md; 72-fix-review-2-backend-r7.dispatch.md; 71-fix-review-2-backend-r7.md; status.json; AGENTS.md; workflows/templates/stage-delivery.yaml; scripts/validate-stage.py; scripts/tests/test_validate_stage_dispatch_protocol.py.\n\nRequired repair: the F6 validator currently collects only Review-1/Review-2 dispatch references. It misses status.json:r7_repair_authorization.active_dispatch, even though packet 72 is status=pending and its declared output already exists. Implement the smallest generic, deterministic validation of a current active implementation/fix dispatch reference under the human-operator protocol. A pending receipt with a real declared output must fail; a completed receipt must pass; unrelated historical or absent references must not be falsely rejected. Add focused regression tests that prove the defect fails before the repair and passes after it. Do not paper over the defect by deleting or renaming stage evidence.\n\nAllowed files: scripts/validate-stage.py; scripts/tests/test_validate_stage_dispatch_protocol.py; reports/agent-runs/2026-07-hedge-open-real-api-v1/60-test-output.txt (append only); the new implementation report path authorized by the bookkeeper. Forbidden: backend/**; frontend/**; docs/**; reports/api-samples/**; status.json; 70-handoff.md; existing review reports; dispatch prompt bodies; environment/credential files.\n\nRun: .venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q; .venv/bin/python scripts/validate-stage.py 2026-07-hedge-open-real-api-v1 --phase pre-review; git diff --check. Write the raw implementation report to the bookkeeper-designated stage path with changed files, reverse-test proof, exact outputs, no-network/no-credential confirmation, Session footer, and then stop for the bookkeeper."
  ,
  "next_action": "human_escalation_required"
}
