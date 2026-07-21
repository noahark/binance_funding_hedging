[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于
   claude-glm -p、kimi -p、codex exec、grok）。需要其他模型时，输出
   ESCALATED 及原因并停止。
2. 禁止编造未实际执行的命令结果或未实际读取的文件内容；你写下的每一条
   执行记录都必须对应你本会话内真实发生的动作。
3. 你的评审/实现依据只能是本 prompt 列出的 raw artifact 路径与你自己
   实际读取的文件。

# Opus 4.8 Design Adjudication Round 2 — Boundary C

你正在对仓库第一条真实、会产生债务的 Binance 借币路径做第二轮只读设计
裁决。第一轮 Opus 4.8、Grok 4.5、GLM-5.2、Kimi 四份独立 review 全部返回
`REWORK`；bookkeeper 已保留四份原始输出，并把共识、分歧与建议裁决整理到
`14-design-review-synthesis.md`。

本轮目标不是再做一份从零开始的 review，而是：

1. 检查综合稿有没有错误吸收、遗漏或把偏好误升格为正确性要求；
2. 对综合稿列出的少数分歧给出精确冻结；
3. 判断冻结后是否足以修订设计并交给注册 breakdown author；
4. 产出可直接被 bookkeeper 落入 `00-task.md` / `10-design.md` /
   `11-adr.md` 的 replacement intent。

## Hard restrictions

- 只读；不要编辑产品代码或 stage 文件。
- 不要执行任何模型/adapter dispatch。
- 不读取 `.env`、密钥、cookie 或私有原始 payload。
- 不发送 Binance 认证请求或 POST。
- 不从记忆补 Binance 合约事实；仓库没有归档的事实一律写成 evidence gap。
- 这不是正式 review-1/review-2，也不是 implementation authorization。

## Required read set

先读综合稿，再按需回查四份 raw review；不得只依据综合稿：

1. `AGENTS.md`
2. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/14-design-review-synthesis.md`
3. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/13-design-review.md`
4. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/design-review.raw-output.md`
5. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/design-review.claude-glm.raw-output.md`
6. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/design-review.raw-output-kimi.md`
7. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/00-task.md`
8. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/10-design.md`
9. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/11-adr.md`
10. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/12-development-breakdown.draft.md`
11. 仅为核验争议所需的当前源码：
    `backend/borrow_tasks/{domain,scheduler,service,store}.py`、
    `backend/tests/test_private_client.py`、
    `backend/tests/test_borrow_executor.py`、`frontend/self-check.js`、
    `backend/config.py`、`backend/app/server.py`

不要递归读取其他 stage 或任何 `history/` 目录。

## User decisions that remain frozen

- 保留现有 frontend 入口；Confirm 即任务授权。
- 用户用账户本金、单次 amount、成功 count 管理普通 exposure。
- 不新增 app-level USDT cap、asset allowlist、`maxBorrowable` preflight。
- borrow-only；不扩 repay/hedge/order/transfer/close。
- 后端权威；浏览器不签名、不调度、不重试。
- 一个串行 backend-dominant implementation task；parallel/embedded review 关闭。

## Required adjudications

请逐项给出一个明确决定，不要只写“实现时决定”：

1. **Single execution owner**：选择 DB-path advisory process lock，还是
   SQLite boot-token/lease，或证明不需要；冻结 second-process、crash recovery、
   status projection 与 deterministic test 语义。
2. **Routes**：在 3/4 reviewers 保留的
   `/api/borrow-execution-status|start|stop` 与 Kimi 的统一前缀方案之间裁决。
3. **Missing credentials**：在 blocked-but-service-starts（3/4）与 hard startup
   failure（Kimi）之间裁决；invalid mode 仍应单独处理。
4. **Retry-After / 418**：60s missing/invalid fallback 已有 4/4 共识；请冻结
   valid-value lower/upper bounds、418 自动恢复还是人工确认，以及 cooldown
   是否阻断 reconciliation GET。
5. **Reconciliation**：冻结有限重试次数与 delay 序列；说明 Global Stop 下
   是否继续安全 GET；耗尽后的状态必须可见且绝不授权第二次 POST。
6. **Cadence**：确认“永不补发历史 tick”；判断是否需要基于已验证 weight/limit
   的最小 interval。若需要，不能选一个刚好吃满候选预算而不给 GET/其他 IP
   流量留余量的值。
7. **Resolve matrix**：成功发生于 `borrowing`、`paused`、`deleted` 时分别如何
   更新 status/count；特别说明 paused 已达到 target 后再 Start，如何保证零额外
   POST。
8. **Status semantics**：确认 transient `in_flight_attempt_id` 与 durable
   `unresolved_attempt_id` 的分工；确认是否必须公开
   `global_cooldown_until`，以及 cooldown 是否折入 `can_execute`。
9. **Security/file boundary**：确认 live client + live executor 都落在
   `backend/services/`，通过现有 seam 注入，并且四个 static guard 只能精确
   扩文件名，不能通配豁免。
10. **Consolidated freezes**：逐条检查 `14-design-review-synthesis.md`
    “Consolidated Outcome” 1–14；标记 `ADOPT / AMEND / DROP` 并说明理由。

## Required output

返回 Markdown，严格包含以下章节：

1. `Verdict: PASS_TO_DESIGN_AMENDMENT | REWORK_SYNTHESIS`
2. `Synthesis corrections` — 综合稿错误/遗漏；没有则写 `None`
3. `Adjudication table` — 对 Required adjudications 1–10 每项给出 exact decision
4. `Freeze matrix` — 对综合稿 1–14 逐项 `ADOPT | AMEND | DROP`
5. `Exact document amendments` — 按 `00-task.md`、`10-design.md`、`11-adr.md`、
   `12-development-breakdown.md` 分组写 replacement intent
6. `Evidence gate` — 哪些字段/常量必须等待 stage public API archive，若证据
   不足时的 fail-closed default 是什么
7. `Lean-scope check` — 是否仍是一任务串行、是否有新增组件属于多余复杂度

若 verdict 是 `REWORK_SYNTHESIS`，请给出 bookkeeper 可直接执行的修订清单。
结束后停止；不要实现、不要修改文件、不要转派模型。

当前 Session ID: unavailable (prompt prepared by bookkeeper; Opus reviewer must report its own verified ID if available)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/design-review-round-2.opus.prompt.md
本地北京时间: 2026-07-20 21:39:03 CST
下一步模型: human operator-selected Claude Opus 4.8 session
下一步任务: adjudicate the multi-review synthesis and return the required read-only Markdown; do not implement
