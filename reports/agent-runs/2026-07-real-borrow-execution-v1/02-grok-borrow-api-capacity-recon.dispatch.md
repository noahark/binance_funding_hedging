# Dispatch — Read-Only Binance Borrow API Capacity Reconnaissance

## Operator Routing

- Target session: Grok Build `019f778f-4efe-7ce0-ab37-483ed47b51c2`
- Model: `grok-build`
- Mode: read-only research; no code or source edits
- Required raw output: `reports/agent-runs/2026-07-real-borrow-execution-v1/03-grok-borrow-api-capacity-recon.md`

Send the prompt below into the target Grok session. Preserve its response at the required raw-output path without bookkeeper rewriting.

## Prompt Body

You are performing **read-only API-capacity reconnaissance**, not implementation or review, for stage `2026-07-real-borrow-execution-v1`.

First read `AGENTS.md`, `agents/skills/product-strategist.md`, the current stage `00-intake.md`, `06-direction-synthesis.md`, and this dispatch file. Then inspect the exact local evidence needed, including your own established session transcript `019f778f-4efe-7ce0-ab37-483ed47b51c2`, `reports/api-samples/2026-07-private-account-v1/`, `backend/services/private_client.py`, `backend/services/snapshot_service.py`, `backend/config.py`, `docs/product/PRD.md`, and official current Binance developer documentation.

## Goal

Produce an evidence-backed **capacity envelope** for a future Portfolio Margin borrow-task scheduler. The user wants to discuss high-frequency retry when the borrowable balance is zero. Determine what can actually be known today about rate limits, request weights, current read load, and confirmation latency—without creating debt or performing a load test.

## Hard Safety Boundary

- Do **not** send `POST`, `PUT`, `DELETE`, or any write request to Binance, including `marginLoan`, repay, transfer, order, listen-key, or a deliberately invalid signed request.
- Do **not** load, print, inspect, copy, or modify API credentials, `.env`, system keychains, process environments, signed URLs, signatures, cookies, or private full payloads.
- Do **not** call any authenticated live endpoint, including GET. Use existing repository samples, code and public official documentation only.
- Do **not** benchmark by repeated requests, seek a 429/418, run a burst, change source files, write code, change configuration, commit, or push.
- A static sample showing `crossMarginBorrowed` is evidence that the field exists; it is **not** evidence that a particular `marginLoan` attempt changes it in a specified time window.

## Required Investigation

1. Separate four evidence classes and never merge them:
   - documented endpoint limits/weights;
   - observed historical response-header deltas in existing samples;
   - present repository refresh cadence and its estimated papi load;
   - unproven live behavior (write acceptance, propagation delay, idempotency, exact current headroom).
2. For the proposed PM borrow write and its candidate read companions, create an endpoint matrix with method, URL path, security, documented request-weight/rate-limit scope, required parameters, response identifier/record-match capability, and source URL or repository evidence. If an item cannot be found in an official current source, write `UNVERIFIED`; do not fill it from model memory.
3. Recalculate the existing backend’s steady-state and cold-start papi request load from code and captured headers. State assumptions and produce a range, not a fabricated precise current value. Explain why the current application cannot provide a live historical used-weight curve.
4. Analyze the existing `/papi/v1/balance` raw fields `crossMarginBorrowed`, `crossMarginInterest`, and `updateTime` for reconciliation:
   - what balance-delta signal they could provide;
   - why they cannot uniquely attribute a change to one task when there is manual/external borrowing or repayment;
   - the freshness mismatch between the current 60-second balance cadence and a potentially high-frequency borrow task;
   - whether balance can be a normal-path confirmation signal and when a loan-history query would still be mandatory.
5. Give a frequency table for 1s, 2s, 5s, 10s, 30s and 60s that distinguishes **documented quota feasibility** from **safe product behavior**. Do not recommend a production frequency without evidence for the write endpoint and reconciliation latency.
6. State the minimum evidence required before any later, separately authorized live-write probe could determine the real write limit. It must be a one-attempt observational protocol, not a stress test.

## Required Output

Use these headings:

1. `Problem And Decision To Support`
2. `Evidence Inventory`
3. `Endpoint And Limit Matrix`
4. `Current Papi Load Envelope`
5. `Balance-Field Reconciliation Assessment`
6. `Frequency Envelope: Quota vs Safety`
7. `Unknowns That Cannot Be Solved Read-Only`
8. `Recommended Inputs For The User Frequency Discussion`
9. `Non-goals And Safety Compliance`

Every numeric or endpoint-semantics claim must have a direct official-URL citation or exact local evidence path. Clearly label every calculation as an inference. Do not claim “production ready,” do not choose the final retry frequency, and do not create a review verdict JSON. End with the repository execution footer.

当前 Session ID: unavailable (prepared by Codex; current runtime does not expose provider-native session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-execution-v1/02-grok-borrow-api-capacity-recon.dispatch.md
本地北京时间: 2026-07-19 12:29:24 CST
下一步模型: Grok Build
下一步任务: 执行只读借币 API 容量摸排并保存原始报告
