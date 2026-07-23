<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status: pending
target_model: claude/opus4.6
adapter_cmd:
executor: human_operator
started_at:
completed_at:
session_id: unavailable:pending human execution
outputs: reports/agent-runs/2026-07-hedge-open-real-api-v1/30-review-1-backend.md
next_dispatch: none
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable） ===== -->

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于 claude-glm -p、
   kimi -p、codex exec、grok）。需要其他模型时，输出 ESCALATED 及原因并停止。
2. 禁止编造未实际执行的命令结果或未实际读取的文件内容；你写下的每一条执行记录都必须
   对应你本会话内真实发生的动作。
3. 你的评审依据只能是本 prompt 列出的 raw artifact 路径与你自己实际读取的文件。

你是正式 Review-1 的 Claude Opus 4.6 后端交叉评审者。仅作只读/plan 审查：绝不修改
文件、绝不 commit、绝不发起真实 Binance 网络/私有请求/POST，也不要运行写入性命令。
你不得评审或改写前端任务。后端实现与 R4 修复作者均为 claude_glm（zhipu_glm），与
Anthropic provider 隔离。

披露：你曾产出本 stage 的 API reconnaissance
`reports/api-samples/2026-07-hedge-open-real-api-v1/order-model-and-live-seams-recon.md`，
但未编写交付代码、未做 direction synthesis 或 development breakdown。必须将该 recon
当作待核对的原始证据；其旧的串行/quoteOrderQty 建议已被用户批准的 fixed-q_common
并发合同覆盖，不能把自己的旧建议当作要求。

审查锚点（只能审这个已提交范围，不用移动 HEAD）：
- backend diff: bf31e8d757aac72c0ca4318ac606893f1af061ad..d90f2f18acec7fe6286f2ae3fc8e187580bf0793
- task fingerprint: d90f2f18acec7fe6286f2ae3fc8e187580bf0793:3f22d26e58e6a0c120d17e1612306413c201c568c6d98463dc91d21b4cc6d843
- overall stage fingerprint: d873699d4c06f8dec343c9a6dcfa5fecc22d74b5:fe8b6dc9349dc4d4f847cdc5e6298e2f4e14b4b2332038bf4911d20377d8099c

必须实际阅读：
- AGENTS.md、workflows/templates/stage-delivery.yaml 中 review-1 相关部分；
- docs/product/PRD.md（§3、§6、§9.2）；
- reports/agent-runs/2026-07-hedge-open-real-api-v1/{00-task.md,05-cadence-resolution.md,06-direction-synthesis.md,10-design.md,11-adr.md,12-development-breakdown.md,13-r4-diff-reconciliation.md,14-r4-verification.md,20-implementation.md,20-implementation-backend.md,40-fix-backend-r4.md,60-test-output.txt}；
- reports/api-samples/2026-07-hedge-open-real-api-v1/order-model-and-live-seams-recon.md；
- 实际 git diff 与相关 backend 源码/测试；
- schemas/review-verdict.schema.json。

冻结产品合同：每张 running task card 独立异步、每秒一组；一组内同 q_common 的
PAPI margin 与 UM 两腿并发；forward=margin BUY + UM SELL，reverse 相反；不用
quoteOrderQty；margin NO_SIDE_EFFECT，UM positionSide=BOTH；orderId 仅受理，模糊结果
用 deterministic client ID 查询且绝不盲目重发；fills/residual 只记录展示，不阻塞下一组；
默认关闭、live 仍需四重门；禁止自动补单/平仓/取消/借还/转账。

重点查：
1. live adapter 的 endpoint、参数、签名复用、filter/Decimal、timeout/5xx 查询与 no-resend；
2. durable-before-send、失败计数只在确认未受理后增加、task-snapshotted 阈值；
3. R4 的 attempts 投影字段、prepared/querying 覆盖、旧 logs/cursor 不退化，以及跨表 cursor 的边界；
4. R4 的每卡并发是否确实避免慢卡阻塞其他卡提交，同时不会导致同一卡重入；
5. disabled/record 不产生网络写入，测试不存在真实 Binance 访问或凭据读取；
6. migration、线程/SQLite 安全、恢复路径和回归测试是否足够；
7. recon 的事实性 endpoint/filter 结论与用户批准的并发 fixed-q_common 合同是否被正确区分。

输出完整原始评审到
reports/agent-runs/2026-07-hedge-open-real-api-v1/30-review-1-backend.md。
先写简洁叙述、findings 和证据（P0/P1/P2/P3），再写 footer；文件最后一个顶层 JSON
对象必须严格匹配 schemas/review-verdict.schema.json，role=first_reviewer，
model=Claude Opus 4.6，diff_fingerprint 必须是上面的 backend task fingerprint，
reviewer_prior_involvement=design，并在 reviewer_prior_involvement_notes 中说明此前仅
有 API recon、没有代码或 synthesis/breakdown 作者身份。若 verdict=REWORK，必须给出
可直接派发的 fix_start_prompt，保留原始证据路径、允许/禁止文件、测试命令和验收条件。

当前 Session ID: report provider-native ID, or unavailable:<reason>
Session ID 来源: runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/30-review-1-backend.md
本地北京时间: obtain from local date command
下一步模型: bookkeeper
下一步任务: validate this Review-1 verdict and route ACCEPT to final Review-2 or REWORK to a bounded human-dispatched fix
```
