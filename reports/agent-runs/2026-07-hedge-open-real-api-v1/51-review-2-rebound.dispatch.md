<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status: pending
target_model: codex/GPT-5 Codex
adapter_cmd:
executor: human_operator
started_at:
completed_at:
session_id: unavailable:pending human execution
outputs: reports/agent-runs/2026-07-hedge-open-real-api-v1/50-review-2.md
next_dispatch: none
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable） ===== -->

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务唯一的最终评审者（Review-2，最终复核）。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括 claude-glm -p、
   kimi -p、codex exec、grok）。需要其他模型时，输出 BLOCKED（需要人工处理）及原因并停止。
2. 只读：绝不修改/提交文件；绝不发起真实 Binance 网络、私有请求或 POST；不读取凭据，
   不启用 Start/live，不下订单。
3. 只以本 prompt 指定的原始文件和本会话实际读取内容作结论；不得以 bookkeeper 转述代替证据。

这是 Hedge Open Real API v1 的最终 Review-2。OpenAI/Codex 曾写 stage design（阶段设计）和
direction synthesis（方向综合），但没有写交付代码或 fix（修复）；因此 verdict 必须写
`reviewer_prior_involvement: "design"` 并说明此情况。Anthropic/Claude 因 Sonnet 5 写过
前端返工而不可终审；zhipu_glm 与 Kimi 分别写过后端/前端代码，也不可终审。路由依据：
`46-review-2-routing-disclosure.md` 与 `48-review-2-harness-rebind.md`。

唯一有效的审查锚点（不能改用移动 HEAD）：
- stage diff: `28c550d87c1ca90983d5bde9c7102d42cffecd4e..01d3a4712c89efab79772ce2e5ee2ba415e1e43c`
- stage fingerprint: `01d3a4712c89efab79772ce2e5ee2ba415e1e43c:c3368f63670e896cbe585293c4ff7261ba55c165346efd4ea27f672be1b91cff`
- backend task Review-1 fingerprint: `d90f2f18acec7fe6286f2ae3fc8e187580bf0793:3f22d26e58e6a0c120d17e1612306413c201c568c6d98463dc91d21b4cc6d843`
- frontend repaired task Review-1 fingerprint: `820dd1e:cd44c9a921e4f6bb21697c1a4c3ab776dc860b2791dd38b887cb5b7dc7f44c6b`

必须实际阅读：
- `AGENTS.md`；`workflows/templates/stage-delivery.yaml` 的 review-2 部分；
  `docs/parallel-development-mode.md` 的 R7/R9 和 Review-2 规则；
  `schemas/review-verdict.schema.json`；
- `docs/product/PRD.md`、`docs/architecture/ARCHITECTURE.md`；
- `reports/agent-runs/2026-07-hedge-open-real-api-v1/{00-task.md,04-user-execution-policy.md,05-cadence-resolution.md,06-direction-synthesis.md,10-design.md,11-adr.md,12-development-breakdown.md,13-r4-diff-reconciliation.md,14-r4-verification.md,20-implementation.md,20-implementation-backend.md,20-implementation-frontend.md,40-fix-backend-r4.md,40-fix-frontend-r1.md,30-review-1-backend.md,30-review-1-frontend.md,45-review-1-frontend-rfix.md,46-review-2-routing-disclosure.md,47-pre-review-gate-hold.md,48-review-2-harness-rebind.md,60-test-output.txt,status.json}`；
- 实际 `git diff --binary 28c550d..01d3a47`、相关 backend/frontend 源码和测试；
  `scripts/validate-stage.py`、`scripts/tests/test_validate_stage_dispatch_protocol.py`。

权威顺序：用户批准的 PRD、用户执行政策和 direction synthesis 高于 00-task/design/ADR/breakdown；
后四者是需要复核的设计证据，不是覆盖用户决定的依据。

冻结业务合同：每个 running（运行中）任务卡是独立异步 worker（工作单元），每秒一组；
多卡可同秒执行。每组两腿并发，且用相同基础币数量 `q_common`；forward（正向）为 PAPI margin BUY + UM SELL，reverse（反向）相反；不使用 `quoteOrderQty`。margin 使用
`NO_SIDE_EFFECT`，UM 使用 `positionSide=BOTH`，不带 `reduceOnly`。`orderId` 仅为受理，
模糊结果用确定性 client ID 查询且绝不盲目重发。成交、均价、partial（部分成交）和 residual
（两腿数量差）只记录展示，不阻断下一秒；仅确认整组两腿均未受理才计失败，默认连续 3 次暂停。
禁止自动补单、取消、平仓、借还币、转账和新增风险上限；smooth/WebSocket 是下一阶段。默认
disabled（关闭）；真实 POST 还须 live 配置 + durable Start（持久化启动开关）+ 新鲜预检。

重点复核：
1. PAPI/UM adapter 的默认关闭门控、参数、Decimal/filter、签名复用、timeout/5xx 查询、
   no-resend（不盲目重发）和零真实 Binance 测试行为。
2. durable-before-send（先持久化再发送）、失败计数、恢复、每卡异步并发、同一卡防重入。
3. R4 attempt 时间线投影与前端中文状态/Decimal 展示的一致性；前端返工是否闭合 Review-1。
4. migration、SQLite/线程安全、API 兼容、disabled/record 零网络写入、测试覆盖和风险规则。
5. 新 Harness 兼容是否真的只放宽“完全没有回执区块”的历史实现任务：必须有匹配 task、
   provider、已存在原始报告、Session ID（或明确不可得原因）和时间；已有但坏的回执必须仍失败。
6. 两份 Review-1 的 ACCEPT 是否有遗漏。历史回执格式不完整不是交易业务缺陷，但新的
   兼容规则本身必须被严格审查。

可运行与审查直接相关的只读测试/静态检查，必须如实记录。不要为了凑测试联网。

将完整原始终审写入：
`reports/agent-runs/2026-07-hedge-open-real-api-v1/50-review-2.md`

先写叙述、findings（P0/P1/P2/P3）和证据，再写 footer；最后一个顶层 JSON 必须严格匹配
`schemas/review-verdict.schema.json`：role=`final_reviewer`、上述 stage fingerprint、
reviewer_prior_involvement=`design`。若 REWORK（需要返工），必须附保留原始路径与精确测试
命令的 `fix_start_prompt`；若 ACCEPT（通过），next_action 必须为
`stage_accepted_waiting_user`，不得 merge 或声称用户已验收。

当前 Session ID: report provider-native ID, or unavailable:<reason>
Session ID 来源: runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/50-review-2.md
本地北京时间: obtain from local date command
下一步模型: bookkeeper
下一步任务: validate the final verdict, run pre-accept only on ACCEPT, then wait for explicit user acceptance
```

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/51-review-2-rebound.dispatch.md
本地北京时间: 2026-07-24 12:45:15 CST
下一步模型: human operator
下一步任务: run the prompt body in a fresh read-only Codex session
