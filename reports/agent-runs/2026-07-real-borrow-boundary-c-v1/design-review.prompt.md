[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于
   claude-glm -p、kimi -p、codex exec、grok）。需要其他模型时，输出
   ESCALATED 及原因并停止。
2. 禁止编造未实际执行的命令结果或未实际读取的文件内容；你写下的每一条
   执行记录都必须对应你本会话内真实发生的动作。
3. 你的评审/实现依据只能是本 prompt 列出的 raw artifact 路径与你自己
   实际读取的文件。

# Read-Only Design Review Prompt — Boundary C Real Borrowing

You are reviewing a HIGH-risk design for the repository's first live
debt-creating Binance adapter. This is a design review only.

## Hard restrictions

- Do not edit product code or stage files.
- Do not execute any model/adapter dispatch.
- Do not use credentials or read `.env`/key files.
- Do not send any authenticated request or Binance POST.
- Do not invent endpoint facts from memory. Mark unverified exchange semantics
  as evidence gaps.
- Do not treat this as formal Review-1 or Review-2; no implementation exists.

## Required read set

1. `AGENTS.md`
2. `workflows/templates/stage-delivery.yaml` only the stage-design and
   development-breakdown sections
3. `docs/parallel-development-mode.md` only v0.5 R11-R12
4. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/00-intake.md`
5. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/00-task.md`
6. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/10-design.md`
7. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/11-adr.md`
8. `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/12-development-breakdown.draft.md`
9. `reports/agent-runs/2026-07-real-borrow-execution-v1/06-direction-synthesis.md`
10. `reports/agent-runs/2026-07-real-borrow-execution-v1/03-grok-borrow-api-capacity-recon.md`
11. Relevant current source only:
    `backend/borrow_tasks/**`, `backend/services/private_client.py`,
    `backend/config.py`, `backend/app/server.py`, borrow-task schemas,
    `frontend/index.html` borrow sections, and matching tests.

Do not recursively read other stages or any `history/` directory.

## User decisions to respect

- Keep the existing frontend entry and connect the backend directly to real
  borrowing.
- Confirm creates/authorizes an immediately runnable task when global/process
  execution gates permit it.
- User controls ordinary exposure through account principal, per-attempt amount,
  and successful-attempt count.
- Do not add app-level USDT caps, asset allowlists, or maxBorrowable preflight
  unless you identify a concrete correctness/contract blocker; distinguish such
  a blocker from a preferred risk policy.
- Borrow-only scope: no automatic sell, hedge, repay, transfer, or close.
- Keep the Harness flow lean: one serial backend-dominant task, embedded review
  off.

## Review questions

1. Can any response/error/restart/race path create a duplicate borrow after an
   ambiguous request?
2. Does migration reliably prevent old A+B `borrowing` tasks from becoming live?
3. Is signer extraction compatible with the existing single-HMAC and GET-only
   security invariants?
4. Are success, rejection, rate-limit, 5xx, timeout, malformed response, and
   reconciliation classifications precise and fail closed?
5. Can Stop/pause/delete/edit race an in-flight attempt without losing evidence
   or reopening eligibility?
6. Is loan-history matching strong enough to avoid attributing a manual or
   concurrent external loan?
7. Are the execution-control API and minimal frontend changes sufficient for
   supervision without becoming a browser scheduler?
8. Are any proposed components unnecessary complexity for the user's direct
   backend goal?
9. Are file boundaries and deterministic no-network tests complete?
10. Which of the five open items in the draft breakdown should be frozen, and
    with what exact decision?

## Required output

Return Markdown with exactly these sections:

1. `Verdict: PASS | REWORK`
2. `Blocking findings` — P0/P1/P2 findings that must change before
   implementation; write `None` if empty.
3. `Non-blocking findings` — P3 improvements.
4. `Open-item decisions` — answer all five open items from the draft breakdown.
5. `Required amendments` — exact file/section and replacement intent.
6. `Lean implementation assessment` — explicitly state whether the one-task,
   no-parallel route is appropriate.
7. `Evidence gaps` — official exchange facts that must be captured before code.

End after the review. Do not dispatch another model and do not implement fixes.

当前 Session ID: unavailable (prompt prepared by bookkeeper; reviewer must report its own verified ID if available)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/design-review.prompt.md
本地北京时间: 2026-07-20 19:27:29 CST
下一步模型: human-selected independent design reviewer
下一步任务: perform the read-only Boundary C design review and return the required structured Markdown
