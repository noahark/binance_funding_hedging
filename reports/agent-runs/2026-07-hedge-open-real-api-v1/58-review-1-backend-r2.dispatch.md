<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status: pending
target_model: claude/Claude Sonnet 5
adapter_cmd:
executor: human_operator
started_at:
completed_at:
session_id: unavailable:pending human execution
outputs: reports/agent-runs/2026-07-hedge-open-real-api-v1/58-review-1-backend-r2.md
next_dispatch: none
fallback_reason: Kimi remains unavailable by the human operator's prior quota report; Claude is provider-isolated from the reviewed claude_glm backend authors.
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable） ===== -->

```text
[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务唯一的正式 Review-1 后端审查者。禁止调用、启动或转派任何其他模型会话或
adapter。只读：绝不修改文件、绝不 commit、绝不读取凭据、绝不连接 Binance、绝不发送
真实 POST、绝不启用 live 或 Start。

审查身份：本次被审后端代码的实现/返工作者为 Claude-GLM（zhipu_glm）。你是 Claude
Sonnet 5（Anthropic），provider 隔离成立。你曾在本 stage 写过前端返工，但没有写过
本次后端代码；只审后端及它暴露的 HTTP/entries 接缝，不审前端视觉实现。JSON 中
`reviewer_prior_involvement` 写 `none`，并在叙述中如实说明“曾写前端、未写被审后端”。

固定审查锚点（只审这个已提交范围；不移动 HEAD）：
- base: 28c550d87c1ca90983d5bde9c7102d42cffecd4e
- head: 8af3f22d92354fdac61a6a057eb25760b924004b
- fingerprint: 8af3f22d92354fdac61a6a057eb25760b924004b:cbd0d92f53cbaaaab444812dd6ce5bd4bcc07aa947a923dd2a33014a74e5d320

必须实际阅读：
- AGENTS.md；workflows/templates/stage-delivery.yaml 的 Review-1 规则；
- docs/product/PRD.md（尤其 §3、§6、§9.2）；
- stage 的 00-task.md、04-user-execution-policy.md、15-immediate-loop-and-open-log-amendment.md、
  16-replacement-development-breakdown.md、17-opening-log-pagination-compatibility.md、
  19-replacement-r4-final-reconciliation.md、50-review-2.md；
- 40-fix-review-2-backend.md、41-fix-open-log-pagination-backend.md、60-test-output.txt；
- 实际 git diff 28c550d..8af3f22、相关 backend 源码与 backend/tests；
- schemas/review-verdict.schema.json。

以用户冻结业务合同为最高权威：每张任务卡独立异步；同一任务严格“第 N 组终态后才可
开始第 N+1 组”；一组内现货与合约仍并发；target_n 是计划尝试组数硬上限；余额不足等
致命业务错误只停止本任务；失败审计日志必须可分页且不重复。默认关闭，实盘授权不在本次。

重点审查：
1. target_n 是否在 scheduler、fill-once 和持久化预留处同时原子限制；单腿/失败绝不补发；
2. 每任务顺序组与跨任务独立性；未终态腿是否继续对账但不阻塞其他任务；
3. 新鲜预检、q_common、数量精度、wire/元数据分离、client-ID 查询、绝不盲重发；
4. 余额/过滤器/账户模式等致命错误是否只停止对应任务，非致命计数和 429 是否正确；
5. `entries_limit` / `entries_cursor` / `entries_next_cursor` 是否保持 legacy logs 分页不变，
   attempt + task_event 跨页不重复不遗漏；
6. 默认 disabled/record 的零真实网络写入、live 闸门、签名器纯度与测试证据。

输出完整原始评审至：
reports/agent-runs/2026-07-hedge-open-real-api-v1/58-review-1-backend-r2.md

先写中文叙述、findings（P0/P1/P2/P3）与可核对证据，再写标准 Session footer。文件最后
一个顶层 JSON 对象必须严格匹配 schemas/review-verdict.schema.json：
role=first_reviewer，model=Claude Sonnet 5，diff_fingerprint 必须逐字等于上面值。
若 verdict=REWORK，必须提供可直接派发的 fix_start_prompt，包含原始证据路径、允许/禁止
文件、精确测试命令与验收条件。完成后停止等待 bookkeeper。

当前 Session ID: report provider-native ID, or unavailable:<reason>
Session ID 来源: runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/58-review-1-backend-r2.md
本地北京时间: obtain from local date command
下一步模型: bookkeeper
下一步任务: validate the backend Review-1 verdict and route it with the frontend verdict
```

当前 Session ID: unavailable (Codex runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/58-review-1-backend-r2.dispatch.md
本地北京时间: 2026-07-24 21:24:42 CST
下一步模型: human operator
下一步任务: run the prompt body in a fresh read-only Claude Sonnet 5 session
