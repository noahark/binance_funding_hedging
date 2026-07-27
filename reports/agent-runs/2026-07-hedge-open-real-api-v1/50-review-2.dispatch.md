<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status: superseded
target_model: codex/GPT-5 Codex
adapter_cmd:
executor: human_operator
started_at: n/a:never executed
completed_at: n/a:never executed
session_id: n/a:never executed
outputs: reports/agent-runs/2026-07-hedge-open-real-api-v1/50-review-2.md
next_dispatch: none
superseded_reason: replaced before execution by 51-review-2-rebound.dispatch.md (Harness rebind, 48-review-2-harness-rebind.md); status.json previous_review_2_r1.previous_dispatch_path records 51 as the executed one
receipt_backfilled_by: bookkeeper (Claude Opus 5) on 2026-07-27. This packet was replaced before any execution, so a terminal 'superseded' state — not 'pending' — is the truthful record. Its declared outputs file exists only because a LATER packet produced it.
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable） ===== -->

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务唯一的最终评审者（Review-2，最终复核）。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于 claude-glm -p、
   kimi -p、codex exec、grok）。需要其他模型时，输出 BLOCKED 及原因并停止。
2. 只读审查：绝不修改文件、绝不 commit、绝不发起真实 Binance 网络/私有请求/POST，
   不访问凭据，不启用 Start/live，不下任何订单。
3. 只依据本 prompt 列出的仓库原始文件和你本会话实际读取到的内容作结论；不得把
   bookkeeper 的转述当成证据。

你是 Hedge Open Real API v1 的正式 Review-2 最终评审者。此次使用强评审披露
（strong-reviewer disclosure override）：OpenAI/Codex 参与了本 stage 的 design 和
direction synthesis，但没有写任何交付代码或 fix。Anthropic/Claude provider 因 Sonnet 5
写过前端返工而被硬性排除；zhipu_glm 与 Kimi 分别写过后端/前端代码，也被硬性排除。
完整路由证据在 `46-review-2-routing-disclosure.md`。你的 verdict 必须写
`reviewer_prior_involvement: "design"`，并在 notes 中如实披露上述情况。

审查锚点（只能审这个已提交范围，不能改用移动 HEAD）：
- stage diff: `28c550d87c1ca90983d5bde9c7102d42cffecd4e..820dd1ec88f0d2727bb0bd3cd06bc28d6c4afc55`
- stage fingerprint: `820dd1e:661ce0295bdc625d2f9772328f09bec55c70207bc6289feda6916e06149b09b7`
- backend task Review-1 fingerprint: `d90f2f18acec7fe6286f2ae3fc8e187580bf0793:3f22d26e58e6a0c120d17e1612306413c201c568c6d98463dc91d21b4cc6d843`
- frontend repaired task Review-1 fingerprint: `820dd1e:cd44c9a921e4f6bb21697c1a4c3ab776dc860b2791dd38b887cb5b7dc7f44c6b`

必须实际阅读：
- `AGENTS.md`；`workflows/templates/stage-delivery.yaml` 的 review-2 部分；
  `docs/parallel-development-mode.md` 的 Review-2/R7 规则；
  `schemas/review-verdict.schema.json`；
- `docs/product/PRD.md`、`docs/architecture/ARCHITECTURE.md`；
- `reports/agent-runs/2026-07-hedge-open-real-api-v1/{00-task.md,04-user-execution-policy.md,05-cadence-resolution.md,06-direction-synthesis.md,10-design.md,11-adr.md,12-development-breakdown.md,13-r4-diff-reconciliation.md,14-r4-verification.md,20-implementation.md,20-implementation-backend.md,20-implementation-frontend.md,40-fix-backend-r4.md,40-fix-frontend-r1.md,30-review-1-backend.md,30-review-1-frontend.md,45-review-1-frontend-rfix.md,46-review-2-routing-disclosure.md,60-test-output.txt,status.json}`；
- 实际 `git diff --binary 28c550d..820dd1e`、所有相关 backend/frontend 源码与测试。

权威顺序：用户批准的 PRD、用户执行政策和 direction synthesis 高于
`00-task.md`/`10-design.md`/`11-adr.md`/breakdown；后几份只是需要被你复核的设计证据。

冻结业务合同（不得用旧的 quoteOrderQty/串行方案推翻）：
- 每个 running（运行中）任务卡是独立异步 worker（工作单元），每秒提交一组；不同卡可同秒提交。
- 每组两腿并发、同一个 base quantity（基础币数量）`q_common`：forward（正向）= PAPI margin BUY + UM SELL；reverse（反向）相反；不用 `quoteOrderQty`。
- margin 使用 `NO_SIDE_EFFECT`，UM 使用 `positionSide=BOTH`，不带 `reduceOnly`。
- 返回 `orderId` 仅表示受理；模糊响应使用确定性 client ID 查询，绝不盲目重发 write POST。
- 成交量、均价、partial（部分成交）和 residual（两腿数量差）只记录/展示，不阻断下一秒；只有确认两腿都未受理的整组失败才计数，默认连续 3 次暂停。
- 不自动补单、取消、平仓、借币、还币、转账或新增数值风险上限；smooth/WebSocket 属下一阶段。
- 默认 disabled（关闭）；真实 POST 仍须 live 配置 + durable Start（持久化启动开关）+ 新鲜预检，且本评审绝不触发它。

重点复核：
1. 后端真实 PAPI/UM adapter 是否被默认关闭门控，参数、Decimal/filter、签名复用、timeout/5xx 查询与 no-resend 是否符合合同；不得有测试里的真实 Binance 请求或凭据读取。
2. durable-before-send（先持久化再发送）、受理态/失败计数、重启恢复、每卡并行调度，是否确实保证慢任务不会挡住其他卡，而同一卡不会重入。
3. backend R4 的 attempts 时间线投影，与 frontend 字段消费/中文状态/Decimal 原样显示是否一致；前端修复是否完整闭合 Review-1 的 REWORK。
4. migration、SQLite/线程安全、API 兼容、disabled/record 零网络写入与测试覆盖；是否有会改变用户已冻结风险规则的隐藏行为。
5. 逐份复核 Review-1 结论是否有遗漏或错误：后端 ACCEPT、前端返工后的 ACCEPT。历史执行回执的完整性可以如实记为流程风险，但不得把它误报成交易业务代码缺陷。

可以执行与本次审查直接相关的只读测试和静态检查；如执行，必须如实记录命令与结果。不要为了凑测试而联网。

将完整原始终审写到：
`reports/agent-runs/2026-07-hedge-open-real-api-v1/50-review-2.md`

先写简洁叙述、findings（P0/P1/P2/P3）和证据，再写 footer；文件最后一个顶层 JSON 对象必须严格匹配 `schemas/review-verdict.schema.json`：
- `role: "final_reviewer"`
- `model: "GPT-5 Codex"`（或本次实际 Codex 模型标识）
- `diff_fingerprint` 必须等于上述 stage fingerprint；
- `reviewer_prior_involvement: "design"`；
- 若 `REWORK`，必须提供可直接派发、保留原始路径与精确测试命令的 `fix_start_prompt`；
- 若 `ACCEPT`，`next_action` 必须为 `stage_accepted_waiting_user`，不得自行 merge 或声称用户验收。

当前 Session ID: report provider-native ID, or unavailable:<reason>
Session ID 来源: runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/50-review-2.md
本地北京时间: obtain from local date command
下一步模型: bookkeeper
下一步任务: validate the final verdict, run pre-accept only on ACCEPT, then wait for explicit user acceptance
```

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/50-review-2.dispatch.md
本地北京时间: 2026-07-24 12:25:24 CST
下一步模型: human operator
下一步任务: run the prompt body in a fresh read-only Codex session after the pre-review gate is green
