# Development-Breakdown Dispatch — Hedge Open Real API v1

Human operator: run this prompt in a fresh **Claude Opus 4.8** session. This is
design-only: do not ask it to implement code or launch another model. Save its
complete unedited response as:

`reports/agent-runs/2026-07-hedge-open-real-api-v1/12-development-breakdown.md`

## Prompt body

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于 claude-glm -p、
   kimi -p、codex exec、grok）。需要其他模型时，只输出交接建议，由 human operator 决定。
2. 你只能做本任务要求的只读检查和指定设计输出；不得写产品源码、访问凭据、发起 Binance
   私有请求、启动服务或下单。
3. 输出必须保留事实来源路径、设计判断和未解决风险；不能把未经验证的假设写成事实。

你是本 MILESTONE 的 development-breakdown author。只做详细实现任务拆分，不写任何
产品代码，不修改 status.json、70-handoff.md、PRD 或源码。阅读：

- AGENTS.md；
- docs/product/PRD.md；
- docs/architecture/ARCHITECTURE.md；
- reports/agent-runs/2026-07-hedge-open-real-api-v1/{00-task.md,10-design.md,11-adr.md,06-direction-synthesis.md,04-user-execution-policy.md}；
- reports/api-samples/2026-07-hedge-open-real-api-v1/order-model-and-live-seams-recon.md；
- backend/hedge_open_tasks/{domain.py,store.py,service.py,executor.py,scheduler.py}；
- backend/app/server.py, backend/config.py, frontend/index.html,
  frontend/self-check.js, and relevant hedge tests.

Produce the complete content for
reports/agent-runs/2026-07-hedge-open-real-api-v1/12-development-breakdown.md.

Required content:
1. Restate frozen contract/non-goals and identify dry-run code that must change.
2. Recommend serial versus parallel implementation. If parallel, split backend
   and frontend only at independent boundaries; give dependencies and shared
   contract freeze.
3. For every task: owner model/provider, exact allowed/forbidden files,
   API/data contracts, migration/compatibility plan, deterministic test commands,
   evidence/report paths, risks, and review focus.
4. Make attempt/leg schema, client-ID query behavior, failure counter,
   one-second scheduling, fake/live separation, and live fill-all concrete.
5. State whether docs/parallel-development-mode.md should be enabled. If yes,
   provide R10 checklist inputs and list human-operated dispatch/review packets;
   do not write implementation prompts.
6. Include implementation sequence, integration test plan, and strict
   no-real-POST/no-credential/no-private-request test constraints.
7. End with the mandatory footer below and no code changes.

Current Session ID: report your provider-native ID, or unavailable with reason
Session ID 来源: runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/12-development-breakdown.md
本地北京时间: obtain from local date command
下一步模型: bookkeeper
下一步任务: archive this raw development breakdown; do not implement code
```

Current dispatch executor: **human operator**. The bookkeeper does not execute
Claude commands or relay this prompt to a model.

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/development-breakdown-dispatch.md
本地北京时间: 2026-07-23 19:44:12 CST
下一步模型: human operator
下一步任务: execute this packet in a fresh Claude Opus 4.8 terminal and preserve raw output
